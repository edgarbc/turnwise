import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONVERSATION_DIR = ROOT / "data" / "examples" / "conversations"
ANNOTATION_DIR = ROOT / "data" / "examples" / "annotations"


class SyntheticConversationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        task_path = ROOT / "configs" / "tasks" / "repair-intake.yaml"
        cls.task = yaml.safe_load(task_path.read_text())["task"]
        cls.field_ids = {field["id"] for field in cls.task["fields"]}
        cls.speaker_roles = set(cls.task["scope"]["speaker_roles"])

    def test_five_conversation_fixtures_have_separate_gold_files(self) -> None:
        conversation_files = sorted(CONVERSATION_DIR.glob("*.json"))
        annotation_files = sorted(ANNOTATION_DIR.glob("*.json"))

        self.assertEqual(len(conversation_files), 5)
        self.assertEqual(
            [path.stem for path in conversation_files],
            [path.stem for path in annotation_files],
        )

    def test_each_snapshot_is_prefix_safe_and_has_valid_evidence(self) -> None:
        for conversation_path in sorted(CONVERSATION_DIR.glob("*.json")):
            with self.subTest(conversation=conversation_path.stem):
                conversation = json.loads(conversation_path.read_text())
                annotation_path = ANNOTATION_DIR / conversation_path.name
                annotation = json.loads(annotation_path.read_text())
                events = conversation["events"]
                event_positions = {
                    event["event_id"]: index for index, event in enumerate(events)
                }
                events_by_id = {event["event_id"]: event for event in events}

                self.assertEqual(
                    conversation["conversation_id"], annotation["conversation_id"]
                )
                self.assertEqual(conversation["task_id"], self.task["id"])
                self.assertEqual(conversation["task_version"], self.task["version"])
                self.assertEqual(annotation["task_version"], self.task["version"])
                self.assertTrue(
                    all(event["speaker"] in self.speaker_roles for event in events)
                )
                self.assertEqual(
                    len({event["event_id"] for event in events}), len(events)
                )
                self.assertEqual(
                    sorted((event["start_ms"], event["end_ms"]) for event in events),
                    [(event["start_ms"], event["end_ms"]) for event in events],
                )

                previous_position = -1
                for snapshot in annotation["snapshots"]:
                    prefix_position = event_positions[snapshot["through_event_id"]]
                    self.assertGreater(prefix_position, previous_position)
                    previous_position = prefix_position
                    self.assertEqual(set(snapshot["values"]), self.field_ids)
                    known_fields = {
                        field_id
                        for field_id, value in snapshot["values"].items()
                        if value is not None
                    }
                    self.assertEqual(set(snapshot["evidence"]), known_fields)

                    for field_references in snapshot["evidence"].values():
                        self.assertGreater(len(field_references), 0)
                        for reference in field_references:
                            evidence_position = event_positions[reference["event_id"]]
                            event = events_by_id[reference["event_id"]]
                            start = reference["start_char"]
                            end = reference["end_char"]
                            self.assertLessEqual(evidence_position, prefix_position)
                            self.assertEqual(event["speaker"], "customer")
                            self.assertGreaterEqual(start, 0)
                            self.assertLess(start, end)
                            self.assertLessEqual(end, len(event["text"]))

    def test_unknown_negation_correction_and_distractor_cases(self) -> None:
        missing = json.loads(
            (ANNOTATION_DIR / "repair-002-missing.json").read_text()
        )
        self.assertIsNone(missing["snapshots"][-1]["values"]["active_leak"])
        self.assertIsNone(
            missing["snapshots"][-1]["values"]["preferred_appointment"]
        )

        negation = json.loads(
            (ANNOTATION_DIR / "repair-003-negation.json").read_text()
        )
        self.assertIs(negation["snapshots"][0]["values"]["active_leak"], True)
        self.assertIs(negation["snapshots"][1]["values"]["active_leak"], False)

        corrections = json.loads(
            (ANNOTATION_DIR / "repair-004-corrections.json").read_text()
        )
        self.assertEqual(
            corrections["snapshots"][0]["values"]["location"], "Upstairs kitchen"
        )
        self.assertEqual(
            corrections["snapshots"][1]["values"]["location"],
            "Basement utility room",
        )
        self.assertEqual(
            corrections["snapshots"][1]["values"]["preferred_appointment"],
            "Saturday afternoon",
        )

        distractors = json.loads(
            (ANNOTATION_DIR / "repair-005-distractors.json").read_text()
        )
        final_values = distractors["snapshots"][-1]["values"]
        self.assertEqual(final_values["preferred_appointment"], "Saturday after lunch")
        self.assertIsNone(final_values["spending_limit"])


if __name__ == "__main__":
    unittest.main()
