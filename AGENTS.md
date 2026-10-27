# Diwan

Diwan turns daily Markdown work notes into structured Saviom timesheet entries.

## Project conventions

- Use Python with `uv` for dependency management and execution.
- Keep the implementation simple and avoid speculative abstractions.
- Prefer typed data structures and validate external/untrusted data with Pydantic.
- Treat LLM output as untrusted until validated.
- Keep deterministic logic in Python when practical.
- Keep Playwright/Saviom-specific logic isolated from classification logic.

## Workflow

1. Read daily Markdown notes.
2. Load the configured Saviom initiatives and tasks.
3. Classify notes into initiative, task, and duration.
4. Aggregate entries by date, initiative, and task.
5. Write the resulting entries to Saviom.

Saviom entries may be saved automatically, but **must never be submitted automatically**.

## Data

Runtime data and configuration live under `~/diwan`.
