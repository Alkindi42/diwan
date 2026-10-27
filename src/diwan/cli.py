import typer
import yaml
from pydantic import ValidationError

from diwan.classifier import ClassifiedEntry, classify
from diwan.config import load_config
from diwan.initiative_loader import Initiative, load_initiatives
from diwan.note_reader import read_notes
from diwan.saviom_writer import write_entries

app = typer.Typer()


@app.command()
def main():
    try:
        config = load_config()
    except FileNotFoundError:
        raise typer.BadParameter(
            "Missing ~/diwan/config.yaml; see README.md for setup."
        ) from None
    except (ValidationError, yaml.YAMLError):
        raise typer.BadParameter(
            "Invalid ~/diwan/config.yaml; check its YAML and saviom_timesheet_url (HTTPS)."
        ) from None

    notes = read_notes()
    initiatives = load_initiatives()
    classified_entries = classify(notes, initiatives)
    _show_classification(classified_entries, notes, initiatives)
    write_entries(classified_entries, timesheet_url=str(config.saviom_timesheet_url))


def _show_classification(
    entries: list[ClassifiedEntry], notes: dict[str, str], initiatives: list[Initiative]
) -> None:
    names = {
        (initiative.saviom_value, task.saviom_value): (initiative.name, task.name)
        for initiative in initiatives
        for task in initiative.tasks
    }
    print("\nClassified entries:")
    referenced: dict[str, set[int]] = {}
    for entry in entries:
        initiative_name, task_name = names[entry.initiative_value, entry.task_value]
        print(f"{entry.date} | {initiative_name} / {task_name} | {entry.duration_minutes} min")
        lines = notes[entry.date].splitlines()
        for number in entry.source_lines:
            print(f"  [{number}] {lines[number - 1].strip()}")
        referenced.setdefault(entry.date, set()).update(entry.source_lines)

    for date, note in notes.items():
        used = referenced.get(date, set())
        unused = [
            (number, line.strip())
            for number, line in enumerate(note.splitlines(), start=1)
            if line.strip() and number not in used
        ]
        if unused:
            print(f"\nUnreferenced note lines in {date}:")
            for number, line in unused:
                print(f"  [{number}] {line}")
