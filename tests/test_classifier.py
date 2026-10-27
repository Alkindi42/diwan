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
                            {"task_key": "t2", "duration_minutes": 30},
                            {"task_key": "t2", "duration_minutes": 30},
                            {"task_key": "t3", "duration_minutes": 120},
                        ]
                    }
                )
            )
        )

        entries = classify({"27-10-2026": "Meetings and training"}, initiatives)

        self.assertEqual(
            [
                (e.date, e.initiative_value, e.task_value, e.duration_minutes)
                for e in entries
            ],
            [("27-10-2026", 12345, 12347, 60), ("27-10-2026", 23456, 23457, 120)],
        )
        call = chat.call_args.kwargs
        schema = call["format"]["$defs"]["CatalogActivity"]["properties"]["task_key"]
        self.assertEqual(schema["enum"], ["t1", "t2", "t3"])
        self.assertNotIn("12346", call["messages"][1]["content"])
        self.assertNotIn("12347", call["messages"][1]["content"])

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
                content='{"entries": [{"task_key": "t2", "duration_minutes": 60}]}'
            )
        )

        with self.assertRaisesRegex(ValueError, "unknown task key 't2'"):
            classify({"27-10-2026": "Work"}, initiatives)


if __name__ == "__main__":
    unittest.main()
