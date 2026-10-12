import unittest
from pathlib import Path

import yaml


class RepairIntakeTaskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        task_path = (
            Path(__file__).resolve().parents[2]
            / "configs"
            / "tasks"
            / "repair-intake.yaml"
        )
        cls.task = yaml.safe_load(task_path.read_text())["task"]

    def test_task_defines_the_six_canonical_fields(self) -> None:
        field_ids = [field["id"] for field in self.task["fields"]]

        self.assertEqual(
            field_ids,
            [
                "appliance",
                "location",
                "active_leak",
                "preferred_appointment",
                "quote_required",
                "spending_limit",
            ],
        )

    def test_unknown_value_and_boolean_states_are_explicit(self) -> None:
        fields = {field["id"]: field for field in self.task["fields"]}

        self.assertIsNone(self.task["output"]["unknown_value"])
        self.assertEqual(fields["active_leak"]["allowed_values"], [True, False])
        self.assertEqual(fields["quote_required"]["allowed_values"], [True, False])

    def test_exact_values_are_selected_then_normalized_in_code(self) -> None:
        self.assertEqual(
            self.task["value_extraction"]["candidate_selected_values"],
            ["preferred_appointment", "spending_limit"],
        )
        self.assertTrue(
            self.task["value_extraction"]["copy_source_text_and_normalize_in_code"]
        )

    def test_known_values_require_evidence_offsets(self) -> None:
        evidence = self.task["output"]["evidence"]

        self.assertTrue(evidence["required_for_known_values"])
        self.assertEqual(evidence["reference"]["interval"], "half_open")
        self.assertEqual(evidence["reference"]["offset_unit"], "unicode_code_point")


if __name__ == "__main__":
    unittest.main()