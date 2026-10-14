import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
CONVERSATION_DIR = ROOT / "data" / "examples" / "conversations"
ANNOTATION_DIR = ROOT / "data" / "examples" / "annotations"
EXPERIMENT_PATH = ROOT / "configs" / "experiments" / "jev-vs-llm.yaml"


TASK_PATH = ROOT / "configs" / "tasks" / "repair-intake.yaml"
TASK = yaml.safe_load(TASK_PATH.read_text())["task"]
FIELD_IDS = {field["id"] for field in TASK["fields"]}
SPEAKER_ROLES = set(TASK["scope"]["speaker_roles"])
CONVERSATION_FILES = sorted(CONVERSATION_DIR.glob("*.json"))


def test_configured_conversation_fixtures_have_separate_gold_files() -> None:
    expected_case_ids = yaml.safe_load(EXPERIMENT_PATH.read_text())["dataset"]["cases"]
    annotation_files = sorted(ANNOTATION_DIR.glob("*.json"))

    assert [path.stem for path in CONVERSATION_FILES] == expected_case_ids
    assert [path.stem for path in CONVERSATION_FILES] == [
        path.stem for path in annotation_files
    ]


@pytest.mark.parametrize(
    "conversation_path",
    CONVERSATION_FILES,
    ids=[path.stem for path in CONVERSATION_FILES],
)
def test_each_snapshot_is_prefix_safe_and_has_valid_evidence(
    conversation_path: Path,
) -> None:
    conversation = json.loads(conversation_path.read_text())
    annotation_path = ANNOTATION_DIR / conversation_path.name
    annotation = json.loads(annotation_path.read_text())
    events = conversation["events"]
    event_positions = {event["event_id"]: index for index, event in enumerate(events)}
    events_by_id = {event["event_id"]: event for event in events}

    assert conversation["conversation_id"] == annotation["conversation_id"]
    assert conversation["task_id"] == TASK["id"]
    assert conversation["task_version"] == TASK["version"]
    assert annotation["task_version"] == TASK["version"]
    assert all(event["speaker"] in SPEAKER_ROLES for event in events)
    assert len({event["event_id"] for event in events}) == len(events)
    assert sorted((event["start_ms"], event["end_ms"]) for event in events) == [
        (event["start_ms"], event["end_ms"]) for event in events
    ]

    previous_position = -1
    for snapshot in annotation["snapshots"]:
        prefix_position = event_positions[snapshot["through_event_id"]]
        assert prefix_position > previous_position
        previous_position = prefix_position
        assert set(snapshot["values"]) == FIELD_IDS
        known_fields = {
            field_id
            for field_id, value in snapshot["values"].items()
            if value is not None
        }
        assert set(snapshot["evidence"]) == known_fields

        for field_references in snapshot["evidence"].values():
            assert field_references
            for reference in field_references:
                evidence_position = event_positions[reference["event_id"]]
                event = events_by_id[reference["event_id"]]
                start = reference["start_char"]
                end = reference["end_char"]
                assert evidence_position <= prefix_position
                assert event["speaker"] == "customer"
                assert 0 <= start < end <= len(event["text"])


def test_unknown_negation_correction_and_distractor_cases() -> None:
    missing = json.loads((ANNOTATION_DIR / "repair-002-missing.json").read_text())
    assert missing["snapshots"][-1]["values"]["active_leak"] is None
    assert missing["snapshots"][-1]["values"]["preferred_appointment"] is None

    negation = json.loads((ANNOTATION_DIR / "repair-003-negation.json").read_text())
    assert negation["snapshots"][0]["values"]["active_leak"] is True
    assert negation["snapshots"][1]["values"]["active_leak"] is False

    corrections = json.loads(
        (ANNOTATION_DIR / "repair-004-corrections.json").read_text()
    )
    assert corrections["snapshots"][0]["values"]["location"] == "Upstairs kitchen"
    assert corrections["snapshots"][1]["values"]["location"] == "Basement utility room"
    assert (
        corrections["snapshots"][1]["values"]["preferred_appointment"]
        == "Saturday afternoon"
    )

    distractors = json.loads(
        (ANNOTATION_DIR / "repair-005-distractors.json").read_text()
    )
    final_values = distractors["snapshots"][-1]["values"]
    assert final_values["preferred_appointment"] == "Saturday after lunch"
    assert final_values["spending_limit"] is None
