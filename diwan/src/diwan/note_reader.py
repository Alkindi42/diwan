from pathlib import Path


def read_notes() -> dict[str, str]:
    notes = {}

    for note in sorted((Path.home() / "diwan").glob("*.md")):
        notes[note.stem] = note.read_text(encoding="utf-8")

    return notes
