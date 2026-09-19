import typer

from diwan.note_reader import read_notes


def main():
    notes = read_notes()
    print(notes)


if __name__ == "__main__":
    typer.run(main)
