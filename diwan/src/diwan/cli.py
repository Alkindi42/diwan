import typer
import yaml
from pydantic import ValidationError

from diwan.classifier import classify
from diwan.config import load_config
from diwan.initiative_loader import load_initiatives
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
            "Invalid ~/diwan/config.yaml; check its YAML and saviom_timesheet_url (HTTPS, no credentials)."
        ) from None

    notes = read_notes()
    initiatives = load_initiatives()
    classified_entries = classify(notes, initiatives)
    write_entries(classified_entries, timesheet_url=str(config.saviom_timesheet_url))
