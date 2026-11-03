# Diwan

Diwan turns daily work notes into structured timesheet entries for Saviom.

It reads daily Markdown files, classifies work against configured initiatives and tasks, estimates time when needed, and persists the resulting entries to Saviom.

## Setup

Install [uv](https://docs.astral.sh/uv/) and [Ollama](https://ollama.com/download),
then install the project dependencies, Playwright's browser, and the default
local classification model:

```bash
uv sync
uv run playwright install chromium
ollama pull qwen3:8b
```

Make sure Ollama is running before invoking Diwan.

Create `~/diwan/config.yaml` with the **full My Timesheet URL** from your
Saviom installation (not the login URL):

```yaml
saviom_timesheet_url: "https://saviom.example.com/SaviomERMWeb/Timesheet/frmTimesheet.aspx?RequestFrom=MYTIMESHT&IsMDIChild=True&FICode=MYTIMESHT"
```

Create `~/diwan/initiatives.yaml` with the initiatives and tasks available in
**your** Saviom account. The IDs below are entirely fictional placeholders;
replace them with the actual option values from your timesheet:

```yaml
initiatives:
  - name: "Example Platform"
    saviom_value: 12345
    description: "Work on an example internal platform."
    tasks:
      - name: "Development"
        saviom_value: 12346
        description: "Planned implementation of new features and improvements."
      - name: "Maintenance"
        saviom_value: 12347
        description: "Operational support and production incident remediation."
  - name: "Example Training"
    saviom_value: 23456
    tasks:
      - name: "Training"
        saviom_value: 23457
```

Add daily Markdown notes directly under `~/diwan/`, named `dd-mm-yyyy.md`.
For example, `~/diwan/12-05-2026.md` could contain:

```markdown
- Updated the example platform's staging deployment script (1h)
- Investigated and resolved an example production alert (30 minutes)
```

The browser stores your SSO session in `~/diwan/browser-profile/`. Avoid
storing credentials in YAML.

Run `uv run diwan` after replacing the example values with your own. By
default, Diwan reads unprocessed daily notes from the current local Monday–Sunday
week. To work on another week, use `uv run diwan --week 2026-05-11` (any date in
that week, in `YYYY-MM-DD` format).

Diwan prints each classified entry with its original note lines and lists any
lines not referenced by the classifier. It then saves the timesheet entries
without asking for confirmation; it never submits them. The preview includes
your note text, so be mindful when sharing terminal output or logs.

When every entry for a day is saved (or already matches Saviom) and no work
bullet was left unclassified, Diwan renames `12-05-2026.md` to
`12-05-2026.processed.md`. It leaves notes unchanged on conflicts or save
errors. Markdown headings may be unreferenced without blocking the rename.
To correct a processed note, rename it back to `dd-mm-yyyy.md` and rerun that
week; existing conflicting Saviom cells are never overwritten.

The writer currently expects the Saviom weekly grid layout described in
`src/diwan/saviom_writer.py`; other installations may require UI adjustments.

## License

[MIT](LICENSE).
