import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from diwan.classifier import ClassifiedEntry
from diwan.saviom_writer import _fill_day_cell, _to_hours, write_entries


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
        def fill_cell(page, entry, day, cols, report):
            report.written.append("filled cell")
            return True

        fill.side_effect = fill_cell
        save.return_value = "validation error"

        with redirect_stdout(io.StringIO()):
            result = write_entries(
                [entry("23-09-2026"), entry("30-09-2026")],
                timesheet_url="https://example.com/timesheet",
            )

        self.assertEqual(result.completed_dates, set())
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
    def test_skips_save_when_cells_already_match(
        self, session, navigate, columns, fill, save, print_report
    ):
        session.return_value = MagicMock()
        def already_present(page, entry, day, cols, report):
            report.already_present.append("matching cell")
            return True

        fill.side_effect = already_present
        with redirect_stdout(io.StringIO()):
            report = write_entries(
                [entry("23-09-2026")], timesheet_url="https://example.com/timesheet"
            )

        save.assert_not_called()
        self.assertEqual(report.written, [])
        self.assertEqual(report.already_present, ["matching cell"])
        self.assertEqual(report.completed_dates, {"23-09-2026"})
        self.assertEqual(report.problems, [])

    @patch("diwan.saviom_writer._print_report")
    @patch("diwan.saviom_writer._save", return_value=None)
    @patch("diwan.saviom_writer._write_entry")
    @patch("diwan.saviom_writer._day_columns", return_value={})
    @patch("diwan.saviom_writer._goto_week")
    @patch("diwan.saviom_writer.saviom_session")
    def test_only_successful_dates_are_complete(
        self, session, navigate, columns, fill, save, print_report
    ):
        session.return_value = MagicMock()

        def fill_cell(page, item, day, cols, report):
            if item.task_value == 12347:
                report.problems.append("conflicting cell")
                return False
            report.written.append("filled cell")
            return True

        fill.side_effect = fill_cell
        with redirect_stdout(io.StringIO()):
            result = write_entries(
                [
                    entry("23-09-2026"),
                    ClassifiedEntry(
                        date="23-09-2026",
                        initiative_value=12345,
                        task_value=12347,
                        duration_minutes=60,
                    ),
                    entry("24-09-2026"),
                ],
                timesheet_url="https://example.com/timesheet",
            )

        save.assert_called_once()
        self.assertEqual(result.completed_dates, {"24-09-2026"})
        self.assertEqual(result.problems, ["conflicting cell"])

    def test_matching_cell_is_not_overwritten(self):
        page = MagicMock()
        cell = page.locator.return_value
        cell.input_value.return_value = "1.50"

        self.assertEqual(_fill_day_cell(page, 1, 8, 90), (False, None))
        cell.fill.assert_not_called()

        cell.input_value.return_value = "1.67"
        was_written, problem = _fill_day_cell(page, 1, 8, 90)
        self.assertFalse(was_written)
        assert problem is not None
        self.assertIn("expected 1.5h", problem)
        cell.fill.assert_not_called()

    def test_report_omits_submission_message(self):
        from diwan.saviom_writer import WriteReport, _print_report

        output = io.StringIO()
        with redirect_stdout(output):
            _print_report(WriteReport(written=["example entry"]))
        self.assertIn("Saved 1 cell.", output.getvalue())
        self.assertNotIn("submitted", output.getvalue())


if __name__ == "__main__":
    unittest.main()
