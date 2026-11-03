"""Read and mark daily Markdown notes stored under ~/diwan."""

import re
from datetime import date, datetime, timedelta

from diwan.paths import DIWAN_DIR

DATE_FORMAT = "%d-%m-%Y"
NOTE_NAME = re.compile(r"\d{2}-\d{2}-\d{4}")


def read_notes(week: date | None = None) -> dict[str, str]:
    """Read unprocessed notes from the local Monday–Sunday week."""
    day = week if week is not None else date.today()
    monday = day - timedelta(days=day.weekday())
    selected = []

    for path in DIWAN_DIR.glob("*.md"):
        if not NOTE_NAME.fullmatch(path.stem):
            continue
        try:
            note_date = datetime.strptime(path.stem, DATE_FORMAT).date()
        except ValueError:
            continue
        if monday <= note_date < monday + timedelta(days=7):
            selected.append((note_date, path))

    return {
        path.stem: path.read_text(encoding="utf-8")
        for _, path in sorted(selected)
    }


def mark_note_processed(day: str, original_text: str) -> None:
    """Rename a saved note without losing edits made during the run."""
    if not NOTE_NAME.fullmatch(day):
        raise ValueError(f"Invalid note date: {day!r}")
    path = DIWAN_DIR / f"{day}.md"
    processed = DIWAN_DIR / f"{day}.processed.md"
    if path.read_text(encoding="utf-8") != original_text:
        raise RuntimeError(f"{path} changed during classification; not marking processed")
    if processed.exists():
        raise FileExistsError(f"{processed} already exists; not overwriting it")
    path.rename(processed)
