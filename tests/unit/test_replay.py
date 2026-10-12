import json
from pathlib import Path

import pytest

from turnwise.contracts import (
    DecisionInput,
    DecisionResult,
    EvidenceReference,
)
from turnwise.pipeline.prefix import assemble_prefix, load_conversation
from turnwise.pipeline.replay import (
    SnapshotCommitter,
    replay_conversation,
    write_replay_artifact,
)
from turnwise.providers.fixture import FixtureProvider


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "data" / "examples" / "conversations"
FIELD_IDS = (
    "appliance",
    "location",
    "active_leak",
    "preferred_appointment",
    "quote_required",
    "spending_limit",
)


def test_scripted_provider_updates_values_and_preserves_corrections() -> None:
    fixture = load_conversation(FIXTURE_DIR / "repair-004-corrections.json")
    provider = FixtureProvider(
        {
            "repair-004-e01": DecisionResult(
                values={"location": "Upstairs kitchen"},
                evidence={
                    "location": (
                        EvidenceReference("repair-004-e01", 27, 43),
                    )
                },
                provider="fixture",
                model="test-script",
            ),
            "repair-004-e03": DecisionResult(
                values={"preferred_appointment": "Friday morning"},
                evidence={
                    "preferred_appointment": (
                        EvidenceReference("repair-004-e03", 0, 14),
                    )
                },
                provider="fixture",
                model="test-script",
            ),
            "repair-004-e07": DecisionResult(
                values={
                    "location": "Basement utility room",
                    "preferred_appointment": "Saturday afternoon",
                },
                evidence={
                    "location": (
                        EvidenceReference("repair-004-e07", 51, 72),
                    ),
                    "preferred_appointment": (
                        EvidenceReference("repair-004-e07", 78, 96),
                    ),
                },
                provider="fixture",
                model="test-script",
            ),
        }
    )

    snapshots = replay_conversation(fixture, FIELD_IDS, provider)

    before_correction = next(
        snapshot for snapshot in snapshots if snapshot.through_event_id == "repair-004-e06"
    )
    after_correction = next(
        snapshot for snapshot in snapshots if snapshot.through_event_id == "repair-004-e07"
    )
    assert before_correction.values["location"] == "Upstairs kitchen"
    assert before_correction.values["preferred_appointment"] == "Friday morning"
    assert after_correction.values["location"] == "Basement utility room"
    assert after_correction.values["preferred_appointment"] == "Saturday afternoon"
    assert [revision.value for revision in after_correction.revisions if revision.field_id == "location"] == [
        "Upstairs kitchen",
        "Basement utility room",
    ]


def test_snapshot_committer_rejects_an_older_result_after_a_newer_one() -> None:
    fixture = load_conversation(FIXTURE_DIR / "repair-004-corrections.json")
    committer = SnapshotCommitter(fixture.conversation_id, FIELD_IDS)
    old_input = assemble_prefix(fixture, "repair-004-e05")
    new_input = assemble_prefix(fixture, "repair-004-e07")
    newer_result = DecisionResult(
        values={"preferred_appointment": "Saturday afternoon"},
        evidence={
            "preferred_appointment": (
                EvidenceReference("repair-004-e07", 78, 96),
            )
        },
        provider="fixture",
        model="test-script",
    )
    older_result = DecisionResult(
        values={"preferred_appointment": "Friday morning"},
        evidence={
            "preferred_appointment": (
                EvidenceReference("repair-004-e03", 0, 14),
            )
        },
        provider="fixture",
        model="test-script",
    )

    newest_snapshot = committer.commit(
        new_input,
        newer_result,
        through_event_id="repair-004-e07",
        event_position=6,
    )
    stale_snapshot = committer.commit(
        old_input,
        older_result,
        through_event_id="repair-004-e05",
        event_position=4,
    )

    assert newest_snapshot is not None
    assert newest_snapshot.values["preferred_appointment"] == "Saturday afternoon"
    assert stale_snapshot is None


def test_result_cannot_use_intake_agent_question_as_evidence() -> None:
    fixture = load_conversation(FIXTURE_DIR / "repair-004-corrections.json")
    decision_input = assemble_prefix(fixture, "repair-004-e02")
    committer = SnapshotCommitter(fixture.conversation_id, FIELD_IDS)
    result = DecisionResult(
        values={"preferred_appointment": "Friday morning"},
        evidence={
            "preferred_appointment": (
                EvidenceReference("repair-004-e02", 0, 14),
            )
        },
        provider="fixture",
        model="test-script",
    )

    with pytest.raises(ValueError, match="customer event"):
        committer.commit(
            decision_input,
            result,
            through_event_id="repair-004-e02",
            event_position=1,
        )


def test_failed_result_is_not_partially_committed() -> None:
    fixture = load_conversation(FIXTURE_DIR / "repair-004-corrections.json")
    decision_input = assemble_prefix(fixture, "repair-004-e01")
    committer = SnapshotCommitter(fixture.conversation_id, FIELD_IDS)
    invalid_result = DecisionResult(
        values={"location": "Upstairs kitchen", "active_leak": False},
        evidence={
            "location": (EvidenceReference("repair-004-e01", 27, 43),),
        },
        provider="fixture",
        model="test-script",
    )

    with pytest.raises(ValueError, match="requires evidence"):
        committer.commit(
            decision_input,
            invalid_result,
            through_event_id="repair-004-e01",
            event_position=0,
        )

    empty_snapshot = committer.commit(
        decision_input,
        DecisionResult({}, {}, provider="fixture", model="test-script"),
        through_event_id="repair-004-e01",
        event_position=0,
    )

    assert empty_snapshot is not None
    assert empty_snapshot.values["location"] is None


def test_unknown_is_distinct_from_explicit_false() -> None:
    fixture = load_conversation(FIXTURE_DIR / "repair-004-corrections.json")
    provider = FixtureProvider(
        {
            "repair-004-e01": DecisionResult(
                values={"active_leak": False},
                evidence={
                    "active_leak": (
                        EvidenceReference("repair-004-e01", 123, 140),
                    )
                },
                provider="fixture",
                model="test-script",
            )
        }
    )

    first_snapshot = replay_conversation(fixture, FIELD_IDS, provider)[0]

    assert first_snapshot.values["active_leak"] is False
    assert first_snapshot.values["quote_required"] is None


def test_replay_passes_only_prefix_local_candidates_to_provider() -> None:
    fixture = load_conversation(FIXTURE_DIR / "repair-004-corrections.json")

    class RecordingProvider:
        name = "fixture"
        model = "recording-test"

        def __init__(self) -> None:
            self.inputs: list[DecisionInput] = []

        def decide(self, decision_input: DecisionInput) -> DecisionResult:
            self.inputs.append(decision_input)
            return DecisionResult({}, {}, provider=self.name, model=self.model)

    provider = RecordingProvider()
    replay_conversation(fixture, FIELD_IDS, provider)

    before_correction = provider.inputs[5]
    after_correction = provider.inputs[6]
    before_appointment_candidates = {
        candidate.text
        for candidate in before_correction.candidates
        if candidate.field_id == "preferred_appointment"
    }
    after_appointment_candidates = {
        candidate.text
        for candidate in after_correction.candidates
        if candidate.field_id == "preferred_appointment"
    }
    assert "Friday morning" in before_appointment_candidates
    assert "Saturday afternoon" not in before_appointment_candidates
    assert "Saturday afternoon" in after_appointment_candidates
    assert any(
        candidate.text == "six hundred U.S. dollars"
        for candidate in before_correction.candidates
    )


def test_fixture_provider_loads_scripted_json_responses(tmp_path: Path) -> None:
    response_path = tmp_path / "responses.json"
    response_path.write_text(
        json.dumps(
            {
                "model": "scripted-test",
                "responses": [
                    {
                        "through_event_id": "repair-004-e01",
                        "values": {"location": "Upstairs kitchen"},
                        "evidence": {
                            "location": [
                                {
                                    "event_id": "repair-004-e01",
                                    "start_char": 27,
                                    "end_char": 43,
                                }
                            ]
                        },
                    }
                ],
            }
        )
    )
    fixture = load_conversation(FIXTURE_DIR / "repair-004-corrections.json")
    decision_input = assemble_prefix(fixture, "repair-004-e01")

    result = FixtureProvider.from_json(response_path).decide(decision_input)

    assert result.model == "scripted-test"
    assert result.values == {"location": "Upstairs kitchen"}


def test_run_artifact_contains_snapshots_but_not_transcript_text(tmp_path: Path) -> None:
    fixture = load_conversation(FIXTURE_DIR / "repair-004-corrections.json")
    provider = FixtureProvider()
    snapshots = replay_conversation(fixture, FIELD_IDS, provider)

    artifact_path = write_replay_artifact(
        fixture,
        provider,
        snapshots,
        output_root=tmp_path,
    )
    artifact = json.loads(artifact_path.read_text())

    assert artifact["conversation_id"] == fixture.conversation_id
    assert artifact["snapshot_count"] == len(fixture.events)
    assert "transcript" not in artifact
    assert all("text" not in snapshot for snapshot in artifact["snapshots"])


if __name__ == "__main__":
    pytest.main([__file__])