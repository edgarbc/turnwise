from pathlib import Path

import pytest

from turnwise.contracts import TranscriptEvent
from turnwise.pipeline.candidates import extract_candidates
from turnwise.pipeline.normalization import normalize_candidate
from turnwise.pipeline.prefix import assemble_prefix, load_conversation


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "data" / "examples" / "conversations"


@pytest.mark.parametrize(
    ("fixture_name", "expected"),
    [
        (
            "repair-001-ordinary.json",
            {"preferred_appointment": {"Thursday morning"},
             "spending_limit": {"three hundred fifty U.S. dollars"}},
        ),
        (
            "repair-002-missing.json",
            {"preferred_appointment": set(), "spending_limit": set()},
        ),
        (
            "repair-003-negation.json",
            {"preferred_appointment": {"Saturday morning"}, "spending_limit": set()},
        ),
        (
            "repair-004-corrections.json",
            {
                "preferred_appointment": {"Friday morning", "Saturday afternoon"},
                "spending_limit": {"six hundred U.S. dollars"},
            },
        ),
        (
            "repair-005-distractors.json",
            {
                "preferred_appointment": {"Tuesday at ten", "Saturday after lunch"},
                "spending_limit": {"one hundred eighty dollars"},
            },
        ),
    ],
    ids=["ordinary", "missing", "negation", "corrections", "distractors"],
)
def test_extracts_expected_pilot_candidates(
    fixture_name: str,
    expected: dict[str, set[str]],
) -> None:
    fixture = load_conversation(FIXTURE_DIR / fixture_name)

    candidates = extract_candidates(fixture.events)

    for field_id, expected_texts in expected.items():
        actual_texts = {
            candidate.text
            for candidate in candidates
            if candidate.field_id == field_id
        }
        assert actual_texts == expected_texts


def test_candidates_preserve_exact_source_offsets_and_source_order() -> None:
    fixture = load_conversation(FIXTURE_DIR / "repair-004-corrections.json")

    candidates = extract_candidates(fixture.events)

    event_positions = {
        event.event_id: index for index, event in enumerate(fixture.events)
    }
    assert list(candidates) == sorted(
        candidates,
        key=lambda candidate: (
            event_positions[candidate.event_id],
            candidate.start_char,
            candidate.field_id,
        ),
    )
    for candidate in candidates:
        event = next(event for event in fixture.events if event.event_id == candidate.event_id)
        assert event.text[candidate.start_char : candidate.end_char] == candidate.text
        assert candidate.candidate_id.endswith(
            f":{candidate.start_char}:{candidate.end_char}"
        )


def test_extractor_ignores_candidate_mentions_from_intake_agent() -> None:
    event = TranscriptEvent(
        conversation_id="agent-only",
        event_id="agent-only-e01",
        speaker="intake_agent",
        text="Friday morning costs three hundred dollars.",
        start_ms=0,
        end_ms=1000,
    )

    assert extract_candidates((event,)) == ()


def test_candidate_extraction_respects_the_assembled_prefix() -> None:
    fixture = load_conversation(FIXTURE_DIR / "repair-004-corrections.json")
    decision_input = assemble_prefix(fixture, "repair-004-e06")

    candidates = extract_candidates(decision_input.transcript)

    assert "Friday morning" in {candidate.text for candidate in candidates}
    assert "Saturday afternoon" not in {candidate.text for candidate in candidates}


def test_candidate_normalization_is_deterministic() -> None:
    fixture = load_conversation(FIXTURE_DIR / "repair-001-ordinary.json")
    candidates = extract_candidates(fixture.events)
    by_text = {candidate.text: candidate for candidate in candidates}

    assert normalize_candidate(by_text["washing machine"]) == "Washing machine"
    assert normalize_candidate(by_text["laundry room"]) == "Laundry room"
    assert normalize_candidate(by_text["Thursday morning"]) == "Thursday morning"
    assert normalize_candidate(by_text["three hundred fifty U.S. dollars"]) == {
        "amount": 350,
        "currency": "USD",
    }