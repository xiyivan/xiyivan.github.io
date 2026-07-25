from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


UTIL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(UTIL_DIR))

import transport_post as subject  # noqa: E402


AIRCRAFT_FORM = """\
[Record]
Date: 2026-07-23
Model: Boeing 737-89P
Registration: B-1754
Flight Number: KN5902
Airline: China United Airlines
Observation: window seat: excellent #2

[Schedule]
Route origin: Beijing Daxing International Airport(PKX)
Route destination: Chizhou Jiuhuashan Airport(JUH)
Actual departure: 23:50
Actual arrival: 01:05
Scheduled departure: 2355
Scheduled arrival: 0110

[Media]
Image URL: https://img.example.test/photo.jpg#large
"""


RAIL_FORM = """\
[Record]
Date: 2026-07-23
Train ID: 1A23
System UID:
Model: Class 801/2
Manufacture:
Operator: Example Rail

[Schedule]
Line: East Coast Mainline
Service route origin: London King's Cross(KGX)
Service route destination: Edinburgh Waverley(EDB)
Travelled segment origin: Peterborough(PBO)
Travelled segment destination: Edinburgh Waverley(EDB)
Departure platform: Plat.4@PBO
Arrival platform: Plat.6@EDB
Actual departure: 0951
Actual arrival: 1325
Scheduled departure: 09:51
Scheduled arrival: 13:32

[Media]
Image URL:
"""


class TransportPostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.templates = subject.load_templates(UTIL_DIR / "templates")
        cls.aircraft = cls.templates["aircraft"]
        cls.rail = cls.templates["rail"]

    def parse_record(self, text: str, template):
        return subject.validate_form(
            subject.parse_form(text, template, "record"), template, "record"
        )

    def test_aliases_and_normalized_identity(self) -> None:
        self.assertIs(subject.choose_template("plane", self.templates), self.aircraft)
        self.assertEqual(
            subject.normalize_identity(" Boeing-737 "),
            subject.normalize_identity("boeing 737"),
        )

    def test_aircraft_record_formats_times_and_extra_fields(self) -> None:
        parsed = self.parse_record(AIRCRAFT_FORM, self.aircraft)
        rendered = subject.render_record(parsed, self.aircraft)
        self.assertIn("### 2026-07-23", rendered)
        self.assertIn("- Observation: window seat: excellent #2", rendered)
        self.assertIn("- Time: 2350-0105/2355-0110 (on time)", rendered)
        self.assertIn("![](https://img.example.test/photo.jpg#large)", rendered)

    def test_rail_record_formats_composites(self) -> None:
        parsed = self.parse_record(RAIL_FORM, self.rail)
        rendered = subject.render_record(parsed, self.rail)
        self.assertIn(
            "- Service route: London King's Cross(KGX) -> Edinburgh Waverley(EDB)",
            rendered,
        )
        self.assertIn("- Platforms: Plat.4@PBO; Plat.6@EDB", rendered)
        self.assertIn("- Time: 0951-1325/0951-1332 (Arriving Early)", rendered)

    def test_punctuality_boundaries(self) -> None:
        base = {
            "actual_departure": "1200",
            "scheduled_departure": "1200",
            "scheduled_arrival": "1300",
        }
        self.assertEqual(
            subject.calculate_status(
                {**base, "actual_arrival": "1255"}, self.rail["punctuality"]
            ),
            "Arriving Early",
        )
        self.assertEqual(
            subject.calculate_status(
                {**base, "actual_arrival": "1304"}, self.rail["punctuality"]
            ),
            "on time",
        )
        self.assertEqual(
            subject.calculate_status(
                {**base, "actual_arrival": "1305"}, self.rail["punctuality"]
            ),
            "Delayed",
        )
        self.assertEqual(
            subject.calculate_status(
                {**base, "actual_arrival": "1315"}, self.aircraft["punctuality"]
            ),
            "on time",
        )
        self.assertEqual(
            subject.calculate_status(
                {**base, "actual_arrival": "1316"}, self.aircraft["punctuality"]
            ),
            "Delayed",
        )

    def test_invalid_time_and_missing_required_field(self) -> None:
        invalid_time = AIRCRAFT_FORM.replace(
            "Actual departure: 23:50", "Actual departure: 29:00"
        )
        with self.assertRaisesRegex(subject.ValidationError, "24-hour"):
            self.parse_record(invalid_time, self.aircraft)
        missing = AIRCRAFT_FORM.replace("Registration: B-1754", "Registration:")
        with self.assertRaisesRegex(subject.ValidationError, "Registration"):
            self.parse_record(missing, self.aircraft)

    def test_empty_form_aborts(self) -> None:
        parsed = subject.parse_form(
            subject.render_form(self.aircraft, "record"), self.aircraft, "record"
        )
        with self.assertRaises(subject.EditorAborted):
            subject.validate_form(parsed, self.aircraft, "record")

    def test_about_extras_and_utf8_are_rendered(self) -> None:
        text = """\
[Spec]
top speed: 400km/h
manufacture: 中车青岛四方
power type: Electric Multiple Unit(EMU)
Formation: 8或16节

[Media]
Image URL:
"""
        parsed = subject.validate_form(
            subject.parse_form(text, self.rail, "about"), self.rail, "about"
        )
        rendered = subject.render_about(parsed, self.rail)
        self.assertIn("- manufacture: 中车青岛四方", rendered)
        self.assertIn("- Formation: 8或16节", rendered)

    def test_match_existing_boeing_post_and_verify_type(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            posts = Path(directory)
            path = posts / "2026-07-15-boeing-737.md"
            path.write_text(
                """---
layout: post
title: "Boeing-737"
categories: [transport]
---
## Records

### 2026-06-23
- Model: Boeing 737-89P
- Flight Number: KN5901
""",
                encoding="utf-8",
            )
            match = subject.find_matching_post(
                posts, "boeing 737", "aircraft", self.templates
            )
            self.assertEqual(match.path, path)
            with self.assertRaisesRegex(subject.ValidationError, "not rail"):
                subject.find_matching_post(posts, "boeing 737", "rail", self.templates)

    def test_ambiguous_titles_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            posts = Path(directory)
            content = """---
title: "CR-400"
categories: [transport]
---
- Train ID: G1
## Records
"""
            (posts / "a.md").write_text(content, encoding="utf-8")
            (posts / "b.markdown").write_text(content, encoding="utf-8")
            with self.assertRaisesRegex(subject.ValidationError, "More than one"):
                subject.find_matching_post(posts, "CR400", "rail", self.templates)

    def test_append_preserves_existing_crlf_bytes(self) -> None:
        original = (
            b'---\r\nlayout: post\r\ntitle: "Boeing-737"\r\n'
            b"categories: [transport]\r\n---\r\n## Records\r\n\r\n"
            b"### 2026-06-23\r\n- Existing: yes\r\n"
        )
        result = subject.append_record_bytes(original, "### 2026-07-23\n\n- New: yes\n")
        self.assertTrue(result.startswith(original))
        appended = result[len(original) :]
        self.assertIn(b"\r\n### 2026-07-23\r\n", appended)
        self.assertNotIn(b"\n", appended.replace(b"\r\n", b""))

    def test_duplicate_uses_model_and_departure_proximity(self) -> None:
        post = subject.PostInfo(
            path=Path("example.md"),
            metadata={"title": "Boeing-737"},
            text="""---
title: Boeing-737
---
## Records

### 2026-07-23
- Model: Boeing 737-89P
- Time: 1200-1300/1200-1300 (on time)
""",
        )
        parsed = self.parse_record(
            AIRCRAFT_FORM.replace("Actual departure: 23:50", "Actual departure: 1245")
            .replace("Actual arrival: 01:05", "Actual arrival: 1400")
            .replace("Scheduled departure: 2355", "Scheduled departure: 1245")
            .replace("Scheduled arrival: 0110", "Scheduled arrival: 1400"),
            self.aircraft,
        )
        rendered = subject.render_record(parsed, self.aircraft)
        with self.assertRaisesRegex(subject.DuplicateRecordError, "45 minutes"):
            subject.check_duplicate_record(
                post, rendered, parsed, self.aircraft, "Boeing 737"
            )

        parsed.values["actual_departure"] = "1301"
        subject.check_duplicate_record(
            post,
            subject.render_record(parsed, self.aircraft),
            parsed,
            self.aircraft,
            "Boeing 737",
        )

    def test_duplicate_falls_back_to_family_model(self) -> None:
        post = subject.PostInfo(
            path=Path("example.md"),
            metadata={"title": "Class 801"},
            text="""## Records

### 2026-07-23
- Train ID: 1A20
- Time: 0951-1200/0951-1200 (on time)
""",
        )
        parsed = self.parse_record(
            RAIL_FORM.replace("Model: Class 801/2", "Model:"), self.rail
        )
        with self.assertRaises(subject.DuplicateRecordError):
            subject.check_duplicate_record(
                post,
                subject.render_record(parsed, self.rail),
                parsed,
                self.rail,
                "Class 801",
            )

    def test_new_post_contains_frontmatter_about_and_record(self) -> None:
        record = subject.render_record(
            self.parse_record(RAIL_FORM, self.rail), self.rail
        )
        about_form = """\
[Spec]
top speed: 200kph
manufacture: 日立
power type: EMU

[Media]
Image URL:
"""
        about_parsed = subject.validate_form(
            subject.parse_form(about_form, self.rail, "about"),
            self.rail,
            "about",
        )
        rendered = subject.render_new_post(
            "新型 801",
            "rail",
            subject.render_about(about_parsed, self.rail),
            record,
            datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc),
        )
        self.assertIn('title: "新型 801"', rendered)
        self.assertIn("transport_type: rail", rendered)
        self.assertIn("## Spec", rendered)
        self.assertIn("## Records", rendered)
        self.assertIn("日立", rendered)
        self.assertEqual(subject.slugify("新型 801"), "新型-801")
        self.assertEqual(subject.slugify("CRH-2A"), "CRH-2a")

    def test_editor_draft_is_retained_and_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / ".git").mkdir()

            def fill_form(_editor, path):
                path.write_text(AIRCRAFT_FORM, encoding="utf-8")

            with mock.patch.object(subject, "run_editor", side_effect=fill_form):
                parsed = subject.edit_form(
                    repo, ["fake-editor"], self.aircraft, "record"
                )
            self.assertEqual(parsed.values["model"], "Boeing 737-89P")
            self.assertTrue((repo / ".git" / "TRANSPORT_RECORD_EDITMSG").exists())

    def test_windows_extensionless_editor_resolves_to_cmd_shim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            editor = Path(directory) / "code"
            editor.write_text("# shell wrapper", encoding="utf-8")
            cmd_shim = editor.with_suffix(".cmd")
            cmd_shim.write_text("@echo off", encoding="utf-8")

            resolved = subject._resolve_windows_editor_shim([str(editor), "--wait"])

            self.assertEqual(resolved, [str(cmd_shim), "--wait"])

    @unittest.skipUnless(sys.platform == "win32", "Windows command wrapping")
    def test_windows_cmd_editor_is_prepared_for_shell(self) -> None:
        command = [
            r"C:\Program Files\Editor\editor.cmd",
            "--wait",
            r"C:\repo\.git\TRANSPORT_RECORD_EDITMSG",
        ]
        prepared = subject._prepare_editor_process(command)

        self.assertIsInstance(prepared, str)
        self.assertIn('"C:\\Program Files\\Editor\\editor.cmd"', prepared)
        self.assertIn("TRANSPORT_RECORD_EDITMSG", prepared)

    def test_main_updates_existing_post(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            posts = repo / "_posts"
            posts.mkdir()
            (repo / ".git").mkdir()
            post_path = posts / "2026-07-15-boeing-737.md"
            original = (
                "---\n"
                'title: "Boeing-737"\n'
                "categories: [transport]\n"
                "---\n"
                "- Flight Number: KN0001\n"
                "## Records\n"
            ).encode()
            post_path.write_bytes(original)
            parsed = self.parse_record(AIRCRAFT_FORM, self.aircraft)
            with mock.patch.object(subject, "edit_form", return_value=parsed):
                result = subject.main(
                    [
                        "--repo",
                        str(repo),
                        "--type",
                        "aircraft",
                        "--model",
                        "Boeing 737",
                        "--editor",
                        "unused",
                    ]
                )
            self.assertEqual(result, 0)
            updated = post_path.read_bytes()
            self.assertTrue(updated.startswith(original))
            self.assertIn(b"### 2026-07-23", updated)

    def test_main_creates_new_post_after_two_forms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            posts = repo / "_posts"
            posts.mkdir()
            (repo / ".git").mkdir()
            record = self.parse_record(RAIL_FORM, self.rail)
            about_text = """\
[Spec]
top speed: 200kph
manufacture: Hitachi Rail
power type: Electric Multiple Unit(EMU)

[Media]
Image URL:
"""
            about = subject.validate_form(
                subject.parse_form(about_text, self.rail, "about"),
                self.rail,
                "about",
            )
            with mock.patch.object(subject, "edit_form", side_effect=[record, about]):
                result = subject.main(
                    [
                        "--repo",
                        str(repo),
                        "--type",
                        "rail",
                        "--model",
                        "British Rail Class 999",
                        "--editor",
                        "unused",
                    ]
                )
            self.assertEqual(result, 0)
            created = list(posts.glob("*-british-rail-class-999.md"))
            self.assertEqual(len(created), 1)
            text = created[0].read_text(encoding="utf-8")
            self.assertIn("transport_type: rail", text)
            self.assertIn("## Spec", text)
            self.assertIn("## Records", text)


if __name__ == "__main__":
    unittest.main()
