import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import typer
from pydantic import ValidationError

from diwan.cli import main
from diwan.config import load_config


class ConfigTests(unittest.TestCase):
    def test_loads_full_timesheet_url(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            url = "https://saviom.example.com/Timesheet/frmTimesheet.aspx?RequestFrom=MYTIMESHT&FICode=MYTIMESHT"
            path.write_text(f'saviom_timesheet_url: "{url}"\n', encoding="utf-8")
            self.assertEqual(str(load_config(path).saviom_timesheet_url), url)

    def test_rejects_insecure_or_missing_url(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            for content in (
                "saviom_timesheet_url: http://example.com/timesheet\n",
                "other_setting: value\n",
            ):
                with self.subTest(content=content):
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaises(ValidationError):
                        load_config(path)

    @patch("diwan.cli.classify")
    @patch("diwan.cli.load_config", side_effect=FileNotFoundError)
    def test_cli_checks_config_before_classification(self, load, classify):
        with self.assertRaises(typer.BadParameter):
            main()
        classify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
