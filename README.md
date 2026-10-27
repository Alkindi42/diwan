# Diwan

Diwan turns daily work notes into structured timesheet entries for Saviom.

It reads daily Markdown files, classifies work against configured initiatives and tasks, estimates time when needed, and persists the resulting entries to Saviom.

## Setup

Install dependencies and the browser used for Saviom:

```bash
uv sync
uv run playwright install chromium
```

Create `~/diwan/config.yaml` with the **full My Timesheet URL** from your
Saviom installation (not the login URL):

```yaml
saviom_timesheet_url: "https://saviom.example.com/SaviomERMWeb/Timesheet/frmTimesheet.aspx?RequestFrom=MYTIMESHT&IsMDIChild=True&FICode=MYTIMESHT"
```

Keep your initiative/task catalog in `~/diwan/initiatives.yaml` and daily
Markdown notes in `~/diwan/` as `dd-mm-yyyy.md`. The browser stores your SSO
session in `~/diwan/browser-profile/`. Avoid storing credentials in YAML.

Run `uv run diwan`. Diwan saves timesheet entries but never submits them.
The writer currently expects the same Saviom weekly grid layout described in
`src/diwan/saviom_writer.py`; other installations may require UI adjustments.
