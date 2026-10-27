import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from diwan.classifier import classify
from diwan.initiative_loader import Initiative, Task


class ClassifierTests(unittest.TestCase):
    @patch("diwan.classifier.chat")
    def test_selects_catalog_keys_and_maps_to_saviom_ids(self, chat):
        initiatives = [
            Initiative(
                name="Example Platform",
                saviom_value=12345,
                tasks=[
                    Task(name="Development", saviom_value=12346),
                    Task(name="Management", saviom_value=12347),
                ],
            ),
            Initiative(
                name="Example Training",
                saviom_value=23456,
                tasks=[Task(name="Training", saviom_value=23457)],
            ),
        ]
        chat.return_value = SimpleNamespace(
            message=SimpleNamespace(
                content=json.dumps(
                    {
                        "entries": [
                            {
                                "task_key": "t2",
                                "duration_minutes": 30,
                                "source_lines": [1],
                            },
                            {
                                "task_key": "t2",
                                "duration_minutes": 30,
                                "source_lines": [2],
                            },
                            {
                                "task_key": "t3",
                                "duration_minutes": 120,
                                "source_lines": [4],
                            },
                        ]
                    }
                )
            )
        )

        entries = classify(
            {"27-10-2026": "Meeting A\nMeeting B\n\nTraining"}, initiatives
        )

        self.assertEqual(
            [
                (
                    e.date,
                    e.initiative_value,
                    e.task_value,
                    e.duration_minutes,
                    e.source_lines,
                )
                for e in entries
            ],
            [
                ("27-10-2026", 12345, 12347, 60, [1, 2]),
                ("27-10-2026", 23456, 23457, 120, [4]),
            ],
        )
        call = chat.call_args.kwargs
        schema = call["format"]["$defs"]["CatalogActivity"]["properties"]["task_key"]
        self.assertEqual(schema["enum"], ["t1", "t2", "t3"])
        source_schema = call["format"]["$defs"]["CatalogActivity"]["properties"][
            "source_lines"
        ]
        self.assertEqual(source_schema["items"]["enum"], [1, 2, 4])
        self.assertIn("[4] Training", call["messages"][1]["content"])
        self.assertNotIn("12346", call["messages"][1]["content"])
        self.assertNotIn("12347", call["messages"][1]["content"])

    @patch("diwan.classifier.chat")
    def test_rejects_unknown_source_line(self, chat):
        initiatives = [
            Initiative(
                name="Example Platform",
                saviom_value=12345,
                tasks=[Task(name="Development", saviom_value=12346)],
            )
        ]
        chat.return_value = SimpleNamespace(
            message=SimpleNamespace(
                content='{"entries": [{"task_key": "t1", "duration_minutes": 60, "source_lines": [2]}]}'
            )
        )

        with self.assertRaisesRegex(ValueError, "unknown source line 2"):
            classify({"27-10-2026": "One bullet"}, initiatives)

    @patch("diwan.classifier.chat")
    def test_rejects_unknown_task_key(self, chat):
        initiatives = [
            Initiative(
                name="Example Platform",
                saviom_value=12345,
                tasks=[Task(name="Development", saviom_value=12346)],
            )
        ]
        chat.return_value = SimpleNamespace(
            message=SimpleNamespace(
                content='{"entries": [{"task_key": "t2", "duration_minutes": 60, "source_lines": [1]}]}'
            )
        )

        with self.assertRaisesRegex(ValueError, "unknown task key 't2'"):
            classify({"27-10-2026": "Work"}, initiatives)


if __name__ == "__main__":
    unittest.main()
