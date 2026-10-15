import typer

from diwan.classifier import classify
from diwan.initiative_loader import load_initiatives
from diwan.note_reader import read_notes


def main():
    notes = read_notes()
    initiatives = load_initiatives()
    classified_entries = classify(notes, initiatives)


if __name__ == "__main__":
    typer.run(main)
