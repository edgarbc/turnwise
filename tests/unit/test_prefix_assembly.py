from pathlib import Path

import pytest

from turnwise.contracts import ValueCandidate
from turnwise.pipeline.prefix import assemble_prefix, load_conversation


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "data" / "examples" / "conversations"


def test_prefix_includes_the_cutoff_event_but_excludes_future_events() -> None:
    fixture = load_conversation(FIXTURE_DIR / "repair-004-corrections.json")

    decision_input = assemble_prefix(fixture, "repair-004-e05")

    assert [event.event_id for event in decision_input.transcript] == [
        "repair-004-e01",
        "repair-004-e02",
        "repair-004-e03",
        "repair-004-e04",
        "repair-004-e05",
    ]
    assert "Saturday afternoon" not in " ".join(
        event.text for event in decision_input.transcript
    )


def test_corrected_values_are_visible_only_at_the_correction_event() -> None:
    fixture = load_conversation(FIXTURE_DIR / "repair-004-corrections.json")

    before_correction = assemble_prefix(fixture, "repair-004-e06")
    after_correction = assemble_prefix(fixture, "repair-004-e07")

    assert "Friday morning" in " ".join(
        event.text for event in before_correction.transcript
    )
    assert "Saturday afternoon" not in " ".join(
        event.text for event in before_correction.transcript
    )
    assert "Saturday afternoon" in " ".join(
        event.text for event in after_correction.transcript
    )


def test_unknown_cutoff_event_fails_closed() -> None:
    fixture = load_conversation(FIXTURE_DIR / "repair-001-ordinary.json")

    with pytest.raises(ValueError, match="not in conversation"):
        assemble_prefix(fixture, "future-event")


def test_candidate_must_reference_an_event_in_the_prefix() -> None:
    fixture = load_conversation(FIXTURE_DIR / "repair-004-corrections.json")
    future_candidate = ValueCandidate(
        candidate_id="appointment-1",
        field_id="preferred_appointment",
        event_id="repair-004-e07",
        start_char=78,
        end_char=96,
        text="Saturday afternoon",
    )

    with pytest.raises(ValueError, match="outside the transcript"):
        assemble_prefix(
            fixture,
            "repair-004-e05",
            candidates=(future_candidate,),
        )


def test_candidate_span_must_match_source_text() -> None:
    fixture = load_conversation(FIXTURE_DIR / "repair-004-corrections.json")
    invalid_candidate = ValueCandidate(
        candidate_id="appointment-1",
        field_id="preferred_appointment",
        event_id="repair-004-e03",
        start_char=0,
        end_char=14,
        text="Saturday morning",
    )

    with pytest.raises(ValueError, match="does not match its source span"):
        assemble_prefix(
            fixture,
            "repair-004-e05",
            candidates=(invalid_candidate,),
        )