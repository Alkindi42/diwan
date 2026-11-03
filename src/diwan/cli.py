import re
from datetime import date

import typer
import yaml
from pydantic import ValidationError

from diwan.classifier import ClassifiedEntry, classify
from diwan.config import load_config
from diwan.initiative_loader import Initiative, load_initiatives
from diwan.note_reader import mark_note_processed, read_notes
from diwan.saviom_writer import write_entries

app = typer.Typer()
WORK_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


@app.command()
def main(
    week: str = typer.Option("", "--week", help="Any date in the week (YYYY-MM-DD)."),
):
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

    try:
        selected_week = date.fromisoformat(week) if week else None
    except ValueError:
        raise typer.BadParameter("--week must be YYYY-MM-DD") from None

    notes = read_notes(week=selected_week)
    if not notes:
        print("No unprocessed notes in the selected week.")
        return

    initiatives = load_initiatives()
    classified_entries = classify(notes, initiatives)
    _show_classification(classified_entries, notes, initiatives)
    blocked_dates = _unreferenced_work_dates(notes, classified_entries)
    if blocked_dates:
        print(f"Unreferenced work bullets; not marking processed: {', '.join(sorted(blocked_dates))}")

    report = write_entries(classified_entries, timesheet_url=str(config.saviom_timesheet_url))
    for day in sorted(report.completed_dates - blocked_dates):
        try:
            mark_note_processed(day, notes[day])
        except (OSError, RuntimeError) as exc:
            print(f"Could not mark {day} processed: {exc}")
        else:
            print(f"Marked {day} processed.")


def _unreferenced_work_dates(
    notes: dict[str, str], entries: list[ClassifiedEntry]
) -> set[str]:
    referenced: dict[str, set[int]] = {}
    for entry in entries:
        referenced.setdefault(entry.date, set()).update(entry.source_lines)
    return {
        day
        for day, note in notes.items()
        if any(
            WORK_BULLET.match(line) and number not in referenced.get(day, set())
            for number, line in enumerate(note.splitlines(), start=1)
        )
    }


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
