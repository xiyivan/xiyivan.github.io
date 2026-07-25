# Transport post generator

Create or update rail and aircraft posts through an editor-based form.

## Quick start

```sh
python -m pip install -r _posts/util/requirements.txt
python _posts/util/transport_post.py
```

Choose the transport type and family model, complete the opened record form,
then save and close the editor. The utility appends to a matching post or opens
a second specification form before creating a new post.

Rail and aircraft use the editable shared templates in `templates/`.

## Test

```sh
python -m unittest discover -s _posts/util/tests -v
```

## Appendix

### Command options

Supply prompt values directly when needed:

```sh
python _posts/util/transport_post.py --type aircraft --model "Boeing 737"
```

Use `--editor "command {file}"` to override the editor. If `{file}` is omitted,
the draft filename is appended to the command.

### Editor and form behavior

The editor preference order is `GIT_EDITOR`, Git's `core.editor`, `VISUAL`, then
`EDITOR`. VS Code should be configured as `code --wait`.

Forms contain `Name: value` entries. Blank lines and full-line comments beginning
with `#` are ignored, while values may contain colons or `#`. Additional fields
placed under an existing section are preserved as Markdown list entries.

Drafts remain inside `.git` as `TRANSPORT_RECORD_EDITMSG` and
`TRANSPORT_ABOUT_EDITMSG`. An empty form or `Ctrl+C` aborts without changing a
post.

### Post creation and formatting

Existing posts receive a new record without reformatting their current content.
A new family opens the second form and produces a new dated Jekyll post.

Actual and scheduled departure and arrival are entered separately as `HHMM` or
`HH:MM`. Overnight journeys are supported. The selected YAML template combines
the values and calculates the punctuality label.

### Duplicate detection

A record is rejected when it has the same normalized specific model and an
actual departure within 60 minutes of an existing record. If no specific model
is present, the family/page model is used. Existing combined `Time:` lines are
also understood.

Adjust this policy through `duplicate.window_minutes`,
`duplicate.model_fields`, and `duplicate.existing_model_labels` in the relevant
template.

### Template customization

`templates/rail.yml` and `templates/aircraft.yml` are canonical and are never
overwritten by the program. They control required fields, aliases,
type-detection markers, form sections, output order, composite formatting,
images, punctuality rules, and duplicate detection. Field keys referenced by
output formats must remain consistent.
