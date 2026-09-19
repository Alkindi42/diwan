import typer

from diwan.initiative_loader import load_initiatives
from diwan.note_reader import read_notes


def main():
    notes = read_notes()
    print(notes)
    initiatives = load_initiatives()
    print(initiatives)


if __name__ == "__main__":
    typer.run(main)
