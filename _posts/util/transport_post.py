#!/usr/bin/env python3
"""Create or update Jekyll transport posts from editor-based forms."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import string
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

try:
    import yaml
except ImportError:  # pragma: no cover - exercised before tests can import us
    yaml = None


UTILITY_DIR = Path(__file__).resolve().parent
DEFAULT_TEMPLATE_DIR = UTILITY_DIR / "templates"
POST_SUFFIXES = {".md", ".markdown"}
SECTION_RE = re.compile(r"^\[([^\]]+)\]\s*$")
FIELD_RE = re.compile(r"^([^:]+):\s*(.*)$")
RECORD_HEADING_RE = re.compile(r"(?m)^###\s+(\d{4}-\d{2}-\d{2})\s*\r?$")
TIME_VALUE_RE = re.compile(r"^(?:[01]\d|2[0-3]):?[0-5]\d$")


class TransportPostError(Exception):
    """Base class for errors that should be shown without a traceback."""


class ValidationError(TransportPostError):
    """The editor form or template is invalid."""


class EditorAborted(TransportPostError):
    """The editor was closed without a usable form."""


class DuplicateRecordError(TransportPostError):
    """A likely duplicate record was found."""


@dataclass
class ParsedForm:
    values: Dict[str, str] = field(default_factory=dict)
    extras: Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)

    def has_content(self) -> bool:
        if any(value.strip() for value in self.values.values()):
            return True
        return any(
            value.strip()
            for entries in self.extras.values()
            for _label, value in entries
        )


@dataclass
class PostInfo:
    path: Path
    text: str
    metadata: Mapping[str, Any]


def require_yaml() -> None:
    if yaml is None:
        raise TransportPostError(
            "PyYAML is required. Install it with "
            "`python -m pip install -r _posts/util/requirements.txt`."
        )


def normalize_identity(value: str) -> str:
    """Normalize a title/model for forgiving identity comparisons."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def slugify(value: str) -> str:
    """Create a Unicode-safe Jekyll filename slug."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    pieces: List[str] = []
    pending_separator = False
    for character in normalized:
        if character.isalnum():
            if pending_separator and pieces:
                pieces.append("-")
            pieces.append(character)
            pending_separator = False
        else:
            pending_separator = True
    slug = "".join(pieces).strip("-")
    if not slug:
        raise ValidationError(
            "The family model does not contain filename-safe characters."
        )
    first_chunk, separator, remainder = slug.partition("-")
    return first_chunk.upper() + separator + remainder


def find_repo_root(start: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(result.stdout.strip()).resolve()
    except (OSError, subprocess.CalledProcessError):
        for candidate in (start.resolve(), *start.resolve().parents):
            if (candidate / "_posts").is_dir():
                return candidate
    raise TransportPostError(
        "Could not find a repository containing an _posts directory."
    )


def _validate_field_definitions(kind: str, definition: Mapping[str, Any]) -> None:
    seen_keys = set()
    seen_labels = set()
    sections = definition.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValidationError(
            f"Template {kind!r} must define at least one form section."
        )
    for section in sections:
        if not isinstance(section, dict) or not section.get("name"):
            raise ValidationError(
                f"Template {kind!r} contains a section without a name."
            )
        for item in section.get("fields", []):
            if (
                not isinstance(item, dict)
                or not item.get("key")
                or not item.get("label")
            ):
                raise ValidationError(
                    f"Template {kind!r} contains a field without a key or label."
                )
            key = str(item["key"])
            label = normalize_identity(str(item["label"]))
            if key in seen_keys or label in seen_labels:
                raise ValidationError(
                    f"Template {kind!r} repeats field key/label {item['label']!r}."
                )
            seen_keys.add(key)
            seen_labels.add(label)


def validate_template(template: Mapping[str, Any], path: Path) -> None:
    required_top_level = {"type", "aliases", "post_markers", "record", "about"}
    missing = sorted(required_top_level.difference(template))
    if missing:
        raise ValidationError(f"{path} is missing template keys: {', '.join(missing)}")
    for kind in ("record", "about"):
        definition = template[kind]
        if not isinstance(definition, dict):
            raise ValidationError(f"{path}: {kind} must be a mapping.")
        _validate_field_definitions(kind, definition)
        if not isinstance(definition.get("output_sections"), list):
            raise ValidationError(f"{path}: {kind}.output_sections must be a list.")


def load_templates(
    template_dir: Path = DEFAULT_TEMPLATE_DIR,
) -> Dict[str, Mapping[str, Any]]:
    require_yaml()
    templates: Dict[str, Mapping[str, Any]] = {}
    for path in sorted(template_dir.glob("*.yml")):
        with path.open("r", encoding="utf-8") as stream:
            value = yaml.safe_load(stream)
        if not isinstance(value, dict):
            raise ValidationError(f"{path} must contain a YAML mapping.")
        validate_template(value, path)
        transport_type = str(value["type"]).casefold()
        if transport_type in templates:
            raise ValidationError(f"More than one template defines {transport_type!r}.")
        templates[transport_type] = value
    if not templates:
        raise ValidationError(f"No YAML templates were found in {template_dir}.")
    return templates


def choose_template(
    entered_type: str, templates: Mapping[str, Mapping[str, Any]]
) -> Mapping[str, Any]:
    wanted = entered_type.strip().casefold()
    for transport_type, template in templates.items():
        aliases = [
            transport_type,
            *[str(alias).casefold() for alias in template["aliases"]],
        ]
        if wanted in aliases:
            return template
    supported = sorted(
        {
            alias
            for transport_type, template in templates.items()
            for alias in [transport_type, *map(str, template["aliases"])]
        }
    )
    raise ValidationError(
        f"Unknown transportation type {entered_type!r}. "
        f"Choose one of: {', '.join(supported)}."
    )


def all_fields(
    definition: Mapping[str, Any],
) -> Iterable[Tuple[str, Mapping[str, Any]]]:
    for section in definition["sections"]:
        section_name = str(section["name"])
        for field_definition in section.get("fields", []):
            yield section_name, field_definition


def render_form(template: Mapping[str, Any], kind: str) -> str:
    definition = template[kind]
    heading = "transport record" if kind == "record" else "transport model information"
    lines = [
        f"# Edit this {heading}, save the file, and close the editor.",
        "# Full-line comments and blank lines are ignored.",
        "# Add extra `Name: value` entries under any existing section.",
        "# Leaving every value blank aborts without changing a post.",
        "",
    ]
    for section in definition["sections"]:
        section_name = str(section["name"])
        required_labels = [
            str(item["label"])
            for item in section.get("fields", [])
            if item.get("required")
        ]
        lines.append(f"[{section_name}]")
        if required_labels:
            lines.append(f"# Required: {', '.join(required_labels)}")
        for item in section.get("fields", []):
            lines.append(f"{item['label']}:")
        lines.append("")
    return "\n".join(lines)


def parse_form(text: str, template: Mapping[str, Any], kind: str) -> ParsedForm:
    definition = template[kind]
    section_names = {
        str(section["name"]).casefold(): str(section["name"])
        for section in definition["sections"]
    }
    fields_by_section: Dict[str, Dict[str, Mapping[str, Any]]] = {}
    for section_name, item in all_fields(definition):
        fields_by_section.setdefault(section_name, {})[
            normalize_identity(str(item["label"]))
        ] = item
        fields_by_section[section_name][normalize_identity(str(item["key"]))] = item

    parsed = ParsedForm(
        extras={str(section["name"]): [] for section in definition["sections"]}
    )
    current_section: Optional[str] = None
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        section_match = SECTION_RE.match(stripped)
        if section_match:
            requested = section_match.group(1).strip().casefold()
            if requested not in section_names:
                raise ValidationError(
                    f"Line {line_number}: unknown section [{section_match.group(1)}]."
                )
            current_section = section_names[requested]
            continue
        if current_section is None:
            raise ValidationError(
                f"Line {line_number}: entries must appear below a [Section] heading."
            )
        field_match = FIELD_RE.match(raw_line)
        if not field_match:
            raise ValidationError(
                f"Line {line_number}: expected a `Name: value` entry."
            )
        label = field_match.group(1).strip()
        value = field_match.group(2).strip()
        known = fields_by_section.get(current_section, {}).get(
            normalize_identity(label)
        )
        if known is not None:
            key = str(known["key"])
            if key in parsed.values and parsed.values[key]:
                raise ValidationError(
                    f"Line {line_number}: {known['label']!r} was entered more than once."
                )
            parsed.values[key] = value
        elif value:
            parsed.extras[current_section].append((label, value))
    return parsed


def normalize_time(value: str, label: str) -> str:
    compact = value.replace(":", "")
    if not TIME_VALUE_RE.fullmatch(value):
        raise ValidationError(f"{label} must use a valid 24-hour HHMM or HH:MM value.")
    return compact


def validate_form(
    parsed: ParsedForm, template: Mapping[str, Any], kind: str
) -> ParsedForm:
    if not parsed.has_content():
        raise EditorAborted("The editor form was left empty; no post was changed.")

    definition = template[kind]
    missing = [
        str(item["label"])
        for _section, item in all_fields(definition)
        if item.get("required") and not parsed.values.get(str(item["key"]), "").strip()
    ]
    if missing:
        raise ValidationError(f"Required fields are blank: {', '.join(missing)}.")

    if kind == "record":
        record_date = parsed.values.get("date", "")
        try:
            date.fromisoformat(record_date)
        except ValueError as error:
            raise ValidationError("Date must use YYYY-MM-DD.") from error

    for key in definition.get("time_fields", []):
        if parsed.values.get(str(key)):
            label = next(
                (
                    str(item["label"])
                    for _section, item in all_fields(definition)
                    if str(item["key"]) == str(key)
                ),
                str(key),
            )
            parsed.values[str(key)] = normalize_time(parsed.values[str(key)], label)

    for pair in definition.get("paired_fields", []):
        keys = [str(value) for value in pair]
        present = [bool(parsed.values.get(key, "").strip()) for key in keys]
        if any(present) and not all(present):
            raise ValidationError(
                f"Fields {', '.join(keys)} must either all be filled or all be blank."
            )
    return parsed


def minutes_since_midnight(value: str) -> int:
    compact = value.replace(":", "")
    return int(compact[:2]) * 60 + int(compact[2:])


def journey_arrival_minutes(departure: str, arrival: str) -> int:
    departure_minutes = minutes_since_midnight(departure)
    arrival_minutes = minutes_since_midnight(arrival)
    if arrival_minutes < departure_minutes:
        arrival_minutes += 24 * 60
    return arrival_minutes


def calculate_status(values: Mapping[str, str], punctuality: Mapping[str, Any]) -> str:
    actual_arrival = journey_arrival_minutes(
        values["actual_departure"], values["actual_arrival"]
    )
    scheduled_arrival = journey_arrival_minutes(
        values["scheduled_departure"], values["scheduled_arrival"]
    )
    difference = actual_arrival - scheduled_arrival
    while difference > 12 * 60:
        difference -= 24 * 60
    while difference < -12 * 60:
        difference += 24 * 60

    labels = punctuality.get("labels", {})
    early_boundary = punctuality.get("early_at_or_before")
    late_boundary = punctuality.get("late_at_or_after")
    late_after = punctuality.get("late_after")
    if early_boundary is not None and difference <= int(early_boundary):
        return str(labels.get("early", "Arriving Early"))
    if late_boundary is not None and difference >= int(late_boundary):
        return str(labels.get("late", "Delayed"))
    if late_after is not None and difference > int(late_after):
        return str(labels.get("late", "Delayed"))
    return str(labels.get("on_time", "on time"))


def _format_keys(format_string: str) -> List[str]:
    return [
        field_name
        for _literal, field_name, _format_spec, _conversion in string.Formatter().parse(
            format_string
        )
        if field_name
    ]


def render_output_item(
    item: Mapping[str, Any],
    parsed: ParsedForm,
    template: Mapping[str, Any],
) -> Optional[str]:
    kind = str(item.get("kind", "field"))
    if kind == "field":
        value = parsed.values.get(str(item["field"]), "")
        if not value:
            return None
        return f"- {item['label']}: {value}"
    if kind == "format":
        format_string = str(item["format"])
        keys = _format_keys(format_string)
        present = [bool(parsed.values.get(key, "")) for key in keys]
        if not any(present):
            return None
        if not all(present):
            missing = [key for key, is_present in zip(keys, present) if not is_present]
            raise ValidationError(
                f"Cannot format {item['label']!r}; missing {', '.join(missing)}."
            )
        value = format_string.format_map(parsed.values)
        return f"- {item['label']}: {value}"
    if kind == "time":
        status = calculate_status(parsed.values, template["punctuality"])
        values = dict(parsed.values)
        values["status"] = status
        value = str(item["format"]).format_map(values)
        return f"- {item['label']}: {value}"
    if kind == "image":
        value = parsed.values.get(str(item["field"]), "")
        return f"![]({value})" if value else None
    raise ValidationError(f"Unknown output item kind {kind!r}.")


def render_sections(
    parsed: ParsedForm,
    template: Mapping[str, Any],
    kind: str,
) -> List[str]:
    rendered_sections: List[str] = []
    for section in template[kind]["output_sections"]:
        source = str(section["source"])
        lines = [
            rendered
            for item in section.get("items", [])
            if (rendered := render_output_item(item, parsed, template)) is not None
        ]
        lines.extend(
            f"- {label}: {value}" for label, value in parsed.extras.get(source, [])
        )
        if not lines:
            continue
        heading = section.get("heading")
        if heading:
            lines.insert(0, f"**{heading}**")
        rendered_sections.append("\n".join(lines))
    return rendered_sections


def render_record(parsed: ParsedForm, template: Mapping[str, Any]) -> str:
    sections = render_sections(parsed, template, "record")
    return f"### {parsed.values['date']}\n\n" + "\n\n".join(sections) + "\n"


def render_about(parsed: ParsedForm, template: Mapping[str, Any]) -> str:
    sections = render_sections(parsed, template, "about")
    return "## Spec\n" + ("\n" + "\n\n".join(sections) if sections else "") + "\n"


def split_frontmatter(text: str) -> Tuple[str, str]:
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, flags=re.DOTALL)
    if not match:
        raise ValidationError("Post does not begin with valid YAML frontmatter.")
    return match.group(1), text[match.end() :]


def read_post(path: Path) -> PostInfo:
    require_yaml()
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValidationError(f"{path} is not valid UTF-8.") from error
    frontmatter, _body = split_frontmatter(text)
    metadata = yaml.safe_load(frontmatter)
    if not isinstance(metadata, dict):
        raise ValidationError(f"{path} frontmatter must be a mapping.")
    return PostInfo(path=path, text=text, metadata=metadata)


def is_transport_post(metadata: Mapping[str, Any]) -> bool:
    categories = metadata.get("categories", [])
    if isinstance(categories, str):
        categories = [categories]
    return any(str(category).casefold() == "transport" for category in categories)


def infer_post_type(
    post: PostInfo, templates: Mapping[str, Mapping[str, Any]]
) -> Optional[str]:
    explicit = post.metadata.get("transport_type")
    if explicit:
        return str(explicit).casefold()
    scores: List[Tuple[int, str]] = []
    for transport_type, template in templates.items():
        score = sum(
            1
            for marker in template.get("post_markers", [])
            if re.search(
                rf"(?mi)^-\s*{re.escape(str(marker))}\s*:",
                post.text,
            )
        )
        scores.append((score, transport_type))
    scores.sort(reverse=True)
    if not scores or scores[0][0] == 0:
        return None
    if len(scores) > 1 and scores[0][0] == scores[1][0]:
        return None
    return scores[0][1]


def find_matching_post(
    posts_dir: Path,
    family_model: str,
    selected_type: str,
    templates: Mapping[str, Mapping[str, Any]],
) -> Optional[PostInfo]:
    wanted = normalize_identity(family_model)
    matches: List[PostInfo] = []
    for path in sorted(posts_dir.iterdir()):
        if not path.is_file() or path.suffix.casefold() not in POST_SUFFIXES:
            continue
        post = read_post(path)
        if not is_transport_post(post.metadata):
            continue
        if normalize_identity(str(post.metadata.get("title", ""))) == wanted:
            matches.append(post)
    if len(matches) > 1:
        paths = ", ".join(str(post.path) for post in matches)
        raise ValidationError(f"More than one post matches {family_model!r}: {paths}")
    if not matches:
        return None
    inferred_type = infer_post_type(matches[0], templates)
    if inferred_type is None:
        raise ValidationError(
            f"Could not verify the transport type of {matches[0].path}."
        )
    if inferred_type != selected_type:
        raise ValidationError(
            f"{matches[0].path.name} appears to be {inferred_type}, "
            f"not {selected_type}."
        )
    return matches[0]


def _record_blocks(text: str) -> Iterable[Tuple[str, str]]:
    matches = list(RECORD_HEADING_RE.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        yield match.group(1), text[match.end() : end]


def _extract_labeled_value(block: str, labels: Sequence[str]) -> Optional[str]:
    for label in labels:
        match = re.search(
            rf"(?mi)^-\s*{re.escape(str(label))}\s*:\s*(.+?)\s*\r?$",
            block,
        )
        if match:
            return match.group(1).strip()
    return None


def _extract_actual_departure(block: str) -> Optional[str]:
    match = re.search(
        r"(?mi)^-\s*Time\s*:\s*((?:[01]\d|2[0-3]):?[0-5]\d)\s*[-–]",
        block,
    )
    return match.group(1).replace(":", "") if match else None


def check_duplicate_record(
    post: PostInfo,
    record_text: str,
    parsed: ParsedForm,
    template: Mapping[str, Any],
    family_model: str,
) -> None:
    if record_text.strip() in post.text:
        raise DuplicateRecordError("This exact formatted record already exists.")

    duplicate = template.get("duplicate", {})
    window = int(duplicate.get("window_minutes", 60))
    model_fields = [str(key) for key in duplicate.get("model_fields", ["model"])]
    model_labels = [
        str(label) for label in duplicate.get("existing_model_labels", ["Model"])
    ]
    new_model = next(
        (parsed.values.get(key, "") for key in model_fields if parsed.values.get(key)),
        family_model,
    )
    new_departure = parsed.values.get("actual_departure")
    if not new_departure:
        return
    new_moment = datetime.combine(
        date.fromisoformat(parsed.values["date"]),
        datetime.strptime(new_departure, "%H%M").time(),
    )

    for record_date, block in _record_blocks(post.text):
        existing_model = _extract_labeled_value(block, model_labels) or family_model
        if normalize_identity(existing_model) != normalize_identity(new_model):
            continue
        existing_departure = _extract_actual_departure(block)
        if not existing_departure:
            continue
        existing_moment = datetime.combine(
            date.fromisoformat(record_date),
            datetime.strptime(existing_departure, "%H%M").time(),
        )
        difference = abs((new_moment - existing_moment).total_seconds()) / 60
        if difference <= window:
            raise DuplicateRecordError(
                "Likely duplicate: model "
                f"{new_model!r} has a record {difference:g} minutes away "
                f"on {record_date} (configured window: {window} minutes)."
            )


def detect_newline(raw: bytes) -> bytes:
    return b"\r\n" if b"\r\n" in raw else b"\n"


def append_record_bytes(raw: bytes, record_text: str) -> bytes:
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValidationError("Existing post is not valid UTF-8.") from error
    if not re.search(r"(?m)^## Records\s*\r?$", decoded):
        raise ValidationError("Existing post does not contain a `## Records` heading.")
    newline = detect_newline(raw)
    if raw.endswith(newline + newline):
        separator = b""
    elif raw.endswith(newline):
        separator = newline
    else:
        separator = newline + newline
    encoded_record = record_text.replace("\n", newline.decode("ascii")).encode("utf-8")
    return raw + separator + encoded_record


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def append_record(path: Path, record_text: str) -> None:
    raw = path.read_bytes()
    atomic_write(path, append_record_bytes(raw, record_text))


def render_new_post(
    family_model: str,
    transport_type: str,
    about_text: str,
    record_text: str,
    now: Optional[datetime] = None,
) -> str:
    timestamp = (now or datetime.now().astimezone()).astimezone()
    title = json.dumps(family_model, ensure_ascii=False)
    return (
        "---\n"
        "layout: post\n"
        f"title: {title}\n"
        f"date: {timestamp.strftime('%Y-%m-%d %H:%M:%S %z')}\n"
        "categories: [transport]\n"
        f"transport_type: {transport_type}\n"
        "---\n"
        f"{about_text.rstrip()}\n\n"
        "## Records\n\n"
        f"{record_text.rstrip()}\n"
    )


def new_post_path(posts_dir: Path, family_model: str, now: datetime) -> Path:
    return posts_dir / f"{now.date().isoformat()}-{slugify(family_model)}.md"


def _git_config_editor(repo_root: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "config", "--get", "core.editor"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def _resolve_windows_editor_shim(command: Sequence[str]) -> List[str]:
    """Prefer a Windows executable sibling over an extensionless shell shim."""
    resolved = list(command)
    if not resolved or Path(resolved[0]).suffix:
        return resolved

    configured = Path(resolved[0])
    for suffix in (".exe", ".com", ".cmd", ".bat"):
        if configured.parent != Path(".") or configured.is_absolute():
            candidate = configured.with_suffix(suffix)
            if candidate.is_file():
                resolved[0] = str(candidate)
                return resolved
        else:
            candidate_on_path = shutil.which(f"{configured.name}{suffix}")
            if candidate_on_path:
                resolved[0] = candidate_on_path
                return resolved
    return resolved


def resolve_editor(repo_root: Path, override: Optional[str] = None) -> List[str]:
    editor = (
        override
        or os.environ.get("GIT_EDITOR")
        or _git_config_editor(repo_root)
        or os.environ.get("VISUAL")
        or os.environ.get("EDITOR")
    )
    if editor:
        parts = shlex.split(editor, posix=os.name != "nt")
        command = [
            part[1:-1] if len(part) >= 2 and part[0] == part[-1] == '"' else part
            for part in parts
        ]
        return _resolve_windows_editor_shim(command) if os.name == "nt" else command
    if os.name == "nt":
        return ["notepad.exe"]
    if sys.platform == "darwin":
        return ["open", "-W", "-t"]
    return [shutil.which("vi") or "vi"]


def _prepare_editor_process(command: Sequence[str]) -> Union[List[str], str]:
    """Return a shell command for Windows batch files and argv otherwise."""
    command_parts = list(command)
    if os.name != "nt" or not command_parts:
        return command_parts
    if Path(command_parts[0]).suffix.casefold() not in {".cmd", ".bat"}:
        return command_parts
    return subprocess.list2cmdline(command_parts)


def run_editor(command: Sequence[str], path: Path) -> None:
    has_placeholder = any("{file}" in part for part in command)
    command_parts = [part.replace("{file}", str(path)) for part in command]
    if not has_placeholder:
        command_parts.append(str(path))
    process_command = _prepare_editor_process(command_parts)
    try:
        result = subprocess.run(
            process_command,
            check=False,
            shell=isinstance(process_command, str),
        )
    except OSError as error:
        raise TransportPostError(
            f"Could not start editor command {process_command!r}: {error}"
        ) from error
    if result.returncode != 0:
        raise EditorAborted(
            f"The editor exited with status {result.returncode}; no post was changed."
        )


def git_edit_path(repo_root: Path, filename: str) -> Path:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--git-path", filename],
            check=True,
            capture_output=True,
            text=True,
        )
        path = Path(result.stdout.strip())
        return path if path.is_absolute() else repo_root / path
    except (OSError, subprocess.CalledProcessError):
        return repo_root / ".git" / filename


def edit_form(
    repo_root: Path,
    editor: Sequence[str],
    template: Mapping[str, Any],
    kind: str,
) -> ParsedForm:
    filename = (
        "TRANSPORT_RECORD_EDITMSG" if kind == "record" else "TRANSPORT_ABOUT_EDITMSG"
    )
    path = git_edit_path(repo_root, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(render_form(template, kind))
    while True:
        run_editor(editor, path)
        try:
            parsed = parse_form(path.read_text(encoding="utf-8-sig"), template, kind)
            parsed = validate_form(parsed, template, kind)
            # Validate template composites while the user can still reopen the draft.
            render_sections(parsed, template, kind)
            return parsed
        except ValidationError as error:
            print(f"Form error: {error}", file=sys.stderr)
            answer = input("Press Enter to edit again, or type q to abort: ").strip()
            if answer.casefold() == "q":
                raise EditorAborted("Aborted; no post was changed.") from error


def parse_arguments(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or append a Jekyll transport record."
    )
    parser.add_argument(
        "--type", dest="transport_type", help="rail/train or aircraft/plane"
    )
    parser.add_argument("--model", dest="family_model", help="family/page model")
    parser.add_argument(
        "--editor", help="editor command; {file} is an optional placeholder"
    )
    parser.add_argument("--repo", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = parse_arguments(argv)
        repo_root = args.repo.resolve() if args.repo else find_repo_root(Path.cwd())
        posts_dir = repo_root / "_posts"
        if not posts_dir.is_dir():
            raise TransportPostError(
                f"{repo_root} does not contain an _posts directory."
            )

        templates = load_templates()
        entered_type = args.transport_type or input(
            "Transportation type (rail/train or aircraft/plane): "
        )
        template = choose_template(entered_type, templates)
        transport_type = str(template["type"]).casefold()
        family_model = (args.family_model or input("Family/page model: ")).strip()
        if not family_model:
            raise ValidationError("Family/page model cannot be blank.")

        existing_post = find_matching_post(
            posts_dir, family_model, transport_type, templates
        )
        editor = resolve_editor(repo_root, args.editor)
        record_form = edit_form(repo_root, editor, template, "record")
        record_text = render_record(record_form, template)

        if existing_post is not None:
            check_duplicate_record(
                existing_post, record_text, record_form, template, family_model
            )
            append_record(existing_post.path, record_text)
            print(f"Updated {existing_post.path}")
            return 0

        about_form = edit_form(repo_root, editor, template, "about")
        about_text = render_about(about_form, template)
        now = datetime.now().astimezone()
        destination = new_post_path(posts_dir, family_model, now)
        if destination.exists():
            raise ValidationError(f"Refusing to overwrite existing file {destination}.")
        post_text = render_new_post(
            family_model, transport_type, about_text, record_text, now
        )
        atomic_write(destination, post_text.encode("utf-8"))
        print(f"Created {destination}")
        return 0
    except KeyboardInterrupt:
        print("\nAborted; no post was changed.", file=sys.stderr)
        return 130
    except TransportPostError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
