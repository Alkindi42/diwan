import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from diwan.note_reader import mark_note_processed, read_notes


class NoteReaderTests(unittest.TestCase):
    def test_reads_only_unprocessed_notes_from_selected_week(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in (
                "26-10-2026.md",
                "28-10-2026.md",
                "27-10-2026.processed.md",
                "02-11-2026.md",
                "19-10-2026.md",
                "README.md",
                "not-a-date.md",
                "31-02-2026.md",
            ):
                (root / name).write_text(name, encoding="utf-8")

            with patch("diwan.note_reader.DIWAN_DIR", root):
                notes = read_notes(week=date(2026, 10, 30))
                previous = read_notes(week=date(2026, 10, 19))

            self.assertEqual(list(notes), ["26-10-2026", "28-10-2026"])
            self.assertEqual(list(previous), ["19-10-2026"])

    def test_renames_only_the_note_that_was_classified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            note = root / "28-10-2026.md"
            processed = root / "28-10-2026.processed.md"
            note.write_text("- Work (1h)", encoding="utf-8")

            with patch("diwan.note_reader.DIWAN_DIR", root):
                with self.assertRaisesRegex(RuntimeError, "changed during classification"):
                    mark_note_processed("28-10-2026", "- Old work (1h)")
                self.assertTrue(note.exists())

                processed.write_text("existing note", encoding="utf-8")
                with self.assertRaises(FileExistsError):
                    mark_note_processed("28-10-2026", "- Work (1h)")
                self.assertEqual(processed.read_text(encoding="utf-8"), "existing note")

                processed.unlink()
                mark_note_processed("28-10-2026", "- Work (1h)")
                self.assertFalse(note.exists())
                self.assertEqual(processed.read_text(encoding="utf-8"), "- Work (1h)")
                self.assertEqual(read_notes(week=date(2026, 10, 28)), {})


if __name__ == "__main__":
    unittest.main()
