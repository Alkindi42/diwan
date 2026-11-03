import io
import unittest
from datetime import date
from contextlib import redirect_stdout
from unittest.mock import patch

from diwan.classifier import ClassifiedEntry
from diwan.cli import main
from diwan.config import AppConfig
from diwan.initiative_loader import Initiative, Task
from diwan.saviom_writer import WriteReport


class PreviewTests(unittest.TestCase):
    @patch("diwan.cli.mark_note_processed")
    @patch("diwan.cli.write_entries")
    @patch("diwan.cli.classify")
    @patch("diwan.cli.load_initiatives")
    @patch("diwan.cli.read_notes")
    @patch("diwan.cli.load_config")
    def test_preview_uses_original_lines_before_writing(
        self, load_config, read_notes, load_initiatives, classify, write_entries, mark_processed
    ):
        load_config.return_value = AppConfig.model_validate(
            {"saviom_timesheet_url": "https://example.com/timesheet"}
        )
        read_notes.return_value = {
            "27-10-2026": "- Team meeting\n- Unrelated work\n- Daily scrum"
        }
        load_initiatives.return_value = [
            Initiative(
                name="Example Platform",
                saviom_value=12345,
                tasks=[Task(name="Management", saviom_value=12347)],
            )
        ]
        classify.return_value = [
            ClassifiedEntry(
                date="27-10-2026",
                initiative_value=12345,
                task_value=12347,
                duration_minutes=80,
                source_lines=[1, 3],
            )
        ]
        output = io.StringIO()

        def check_preview(*args, **kwargs):
            self.assertIn("[1] - Team meeting", output.getvalue())
            self.assertIn("[3] - Daily scrum", output.getvalue())
            return WriteReport(completed_dates={"27-10-2026"})

        write_entries.side_effect = check_preview
        with redirect_stdout(output):
            main(week="")

        mark_processed.assert_not_called()  # Unreferenced work bullet.
        read_notes.assert_called_once_with(week=None)
        self.assertIn("Example Platform / Management | 80 min", output.getvalue())
        self.assertIn("Unreferenced note lines in 27-10-2026:", output.getvalue())
        self.assertIn("[2] - Unrelated work", output.getvalue())
        write_entries.assert_called_once_with(
            classify.return_value, timesheet_url="https://example.com/timesheet"
        )

    @patch("diwan.cli.mark_note_processed")
    @patch("diwan.cli.write_entries")
    @patch("diwan.cli.classify")
    @patch("diwan.cli.load_initiatives")
    @patch("diwan.cli.read_notes")
    @patch("diwan.cli.load_config")
    def test_marks_saved_note_with_only_heading_unreferenced(
        self, load_config, read_notes, load_initiatives, classify, write_entries, mark_processed
    ):
        load_config.return_value = AppConfig.model_validate(
            {"saviom_timesheet_url": "https://example.com/timesheet"}
        )
        note = "# Example project\n- Investigated alert (1h)"
        read_notes.return_value = {"27-10-2026": note}
        load_initiatives.return_value = [
            Initiative(
                name="Example Platform",
                saviom_value=12345,
                tasks=[Task(name="Maintenance", saviom_value=12347)],
            )
        ]
        classify.return_value = [
            ClassifiedEntry(
                date="27-10-2026",
                initiative_value=12345,
                task_value=12347,
                duration_minutes=60,
                source_lines=[2],
            )
        ]
        write_entries.return_value = WriteReport(completed_dates={"27-10-2026"})

        with redirect_stdout(io.StringIO()):
            main(week="2026-10-27")

        read_notes.assert_called_once_with(week=date(2026, 10, 27))
        mark_processed.assert_called_once_with("27-10-2026", note)


if __name__ == "__main__":
    unittest.main()
