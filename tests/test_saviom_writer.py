import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from diwan.classifier import ClassifiedEntry
from diwan.saviom_writer import _to_hours, write_entries


def entry(date: str) -> ClassifiedEntry:
    return ClassifiedEntry(
        date=date, initiative_value=12345, task_value=12346, duration_minutes=90
    )


class WriterTests(unittest.TestCase):
    def test_decimal_hours(self):
        self.assertEqual(_to_hours(90), "1.5")
        self.assertEqual(_to_hours(15), "0.25")

    @patch("diwan.saviom_writer._print_report")
    @patch("diwan.saviom_writer._save")
    @patch("diwan.saviom_writer._write_entry")
    @patch("diwan.saviom_writer._day_columns", return_value={})
    @patch("diwan.saviom_writer._goto_week")
    @patch("diwan.saviom_writer.saviom_session")
    def test_reports_only_confirmed_saves(
        self, session, navigate, columns, fill, save, print_report
    ):
        session.return_value = MagicMock()
        fill.side_effect = lambda page, entry, day, cols, report: report.written.append(
            "filled cell"
        )
        save.return_value = "validation error"

        with redirect_stdout(io.StringIO()):
            write_entries(
                [entry("23-09-2026"), entry("30-09-2026")],
                timesheet_url="https://example.com/timesheet",
            )

        session.assert_called_once_with("https://example.com/timesheet")

        save.assert_called_once()
        navigate.assert_called_once()  # No navigation after a failed save.
        report = print_report.call_args.args[0]
        self.assertEqual(report.written, [])
        self.assertIn("not confirmed saved", report.problems[0])

    @patch("diwan.saviom_writer._print_report")
    @patch("diwan.saviom_writer._save")
    @patch("diwan.saviom_writer._write_entry")
    @patch("diwan.saviom_writer._day_columns", return_value={})
    @patch("diwan.saviom_writer._goto_week")
    @patch("diwan.saviom_writer.saviom_session")
    def test_skips_save_when_no_cells_were_filled(
        self, session, navigate, columns, fill, save, print_report
    ):
        session.return_value = MagicMock()
        fill.side_effect = lambda page, entry, day, cols, report: report.problems.append(
            "cell already occupied"
        )

        with redirect_stdout(io.StringIO()):
            write_entries([entry("23-09-2026")], timesheet_url="https://example.com/timesheet")

        save.assert_not_called()
        report = print_report.call_args.args[0]
        self.assertEqual(report.written, [])
        self.assertEqual(report.problems, ["cell already occupied"])

    def test_report_omits_submission_message(self):
        from diwan.saviom_writer import WriteReport, _print_report

        output = io.StringIO()
        with redirect_stdout(output):
            _print_report(WriteReport(written=["example entry"]))
        self.assertIn("Saved 1 cell.", output.getvalue())
        self.assertNotIn("submitted", output.getvalue())


if __name__ == "__main__":
    unittest.main()
