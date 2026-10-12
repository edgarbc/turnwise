from pathlib import Path

import yaml


TASK_PATH = (
    Path(__file__).resolve().parents[2]
    / "configs"
    / "tasks"
    / "repair-intake.yaml"
)
TASK = yaml.safe_load(TASK_PATH.read_text())["task"]


def test_task_defines_the_six_canonical_fields() -> None:
    field_ids = [field["id"] for field in TASK["fields"]]

    assert field_ids == [
        "appliance",
        "location",
        "active_leak",
        "preferred_appointment",
        "quote_required",
        "spending_limit",
    ]


def test_unknown_value_and_boolean_states_are_explicit() -> None:
    fields = {field["id"]: field for field in TASK["fields"]}

    assert TASK["output"]["unknown_value"] is None
    assert fields["active_leak"]["allowed_values"] == [True, False]
    assert fields["quote_required"]["allowed_values"] == [True, False]


def test_exact_values_are_selected_then_normalized_in_code() -> None:
    assert TASK["value_extraction"]["candidate_selected_values"] == [
        "preferred_appointment",
        "spending_limit",
    ]
    assert TASK["value_extraction"]["copy_source_text_and_normalize_in_code"]


def test_known_values_require_evidence_offsets() -> None:
    evidence = TASK["output"]["evidence"]

    assert evidence["required_for_known_values"]
    assert evidence["reference"]["interval"] == "half_open"
    assert evidence["reference"]["offset_unit"] == "unicode_code_point"