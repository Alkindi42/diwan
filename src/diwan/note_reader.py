from diwan.paths import DIWAN_DIR


def read_notes() -> dict[str, str]:
    notes = {}

    for note in sorted(DIWAN_DIR.glob("*.md")):
        notes[note.stem] = note.read_text(encoding="utf-8")

    return notes
