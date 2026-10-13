import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from turnwise.pipeline.candidates import extract_candidates
from turnwise.pipeline.prefix import assemble_prefix, load_conversation
from turnwise.providers.jev import JevProvider
from turnwise.providers.structured_llm import StructuredLLMProvider
from turnwise.settings import Settings
from turnwise.cli import app
from typer.testing import CliRunner


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "data" / "examples" / "conversations" / "repair-001-ordinary.json"


def _decision_input(
    fixture_path: Path = FIXTURE_PATH,
    through_event_id: str | None = None,
):
    fixture = load_conversation(fixture_path)
    last_event_id = through_event_id or fixture.events[-1].event_id
    end_position = next(
        index for index, event in enumerate(fixture.events) if event.event_id == last_event_id
    )
    prefix = assemble_prefix(
        fixture,
        last_event_id,
        candidates=extract_candidates(fixture.events[: end_position + 1]),
    )
    return prefix


def _candidate_id(decision_input, field_id: str, text: str) -> str:
    return next(
        candidate.candidate_id
        for candidate in decision_input.candidates
        if candidate.field_id == field_id and candidate.text == text
    )


class FakeJevClient:
    def __init__(self, selections: dict[str, str]) -> None:
        self.selections = selections
        self.call: dict[str, Any] | None = None

    def system_one(self, *, state: Any, questions: Any, model: str) -> Any:
        self.call = {"state": state, "questions": questions, "model": model}
        choices = {
            question_id: SimpleNamespace(
                choice=self.selections[question_id],
                probabilities={self.selections[question_id]: 1.0},
            )
            for question_id in questions
        }
        return SimpleNamespace(
            choices=choices,
            model=model,
            usage=SimpleNamespace(input_tokens=17, output_tokens=8),
        )


def _jev_selections(decision_input) -> dict[str, str]:
    selections = {
        "value__appliance": _candidate_id(
            decision_input, "appliance", "washing machine"
        ),
        "value__location": _candidate_id(decision_input, "location", "laundry room"),
        "value__active_leak": "true::repair-001-e01",
        "value__preferred_appointment": _candidate_id(
            decision_input, "preferred_appointment", "Thursday morning"
        ),
        "value__quote_required": "true::repair-001-e07",
        "value__spending_limit": _candidate_id(
            decision_input, "spending_limit", "three hundred fifty U.S. dollars"
        ),
    }
    return selections


def test_jev_adapter_builds_shared_candidate_choices_and_maps_result() -> None:
    decision_input = _decision_input()
    client = FakeJevClient(_jev_selections(decision_input))
    provider = JevProvider(
        Settings(),
        client=client,
        model="jev-test",
    )

    result = provider.decide(decision_input)

    assert client.call is not None
    assert client.call["model"] == "jev-test"
    assert "gold" not in json.dumps(client.call["state"]).casefold()
    assert "evidence__active_leak" not in client.call["questions"]
    active_options = client.call["questions"]["value__active_leak"].criteria
    assert "true::repair-001-e01" in active_options
    assert "false::repair-001-e01" in active_options
    assert result.error is None
    assert result.values == {
        "appliance": "Washing machine",
        "location": "Laundry room",
        "active_leak": True,
        "preferred_appointment": "Thursday morning",
        "quote_required": True,
        "spending_limit": {"amount": 350, "currency": "USD"},
    }
    assert result.evidence["appliance"][0].event_id == "repair-001-e01"
    assert result.evidence["active_leak"][0].event_id == "repair-001-e01"
    assert result.evidence["quote_required"][0].event_id == "repair-001-e07"
    assert result.usage == {"input_tokens": 17, "output_tokens": 8}


def test_jev_adapter_returns_unknown_without_evidence() -> None:
    decision_input = _decision_input()
    selections = _jev_selections(decision_input)
    selections["value__active_leak"] = "__unknown__"
    selections["value__quote_required"] = "__unknown__"
    result = JevProvider(Settings(), client=FakeJevClient(selections), model="jev-test").decide(
        decision_input
    )

    assert result.error is None
    assert result.values["active_leak"] is None
    assert result.values["quote_required"] is None
    assert "active_leak" not in result.evidence
    assert "quote_required" not in result.evidence


def test_jev_known_boolean_always_carries_its_evidence_on_problem_prefixes() -> None:
    regression_prefixes = [
        ("repair-004-corrections.json", "repair-004-e05", "repair-004-e01"),
        ("repair-005-distractors.json", "repair-005-e07", "repair-005-e01"),
    ]
    for fixture_name, cutoff_event_id, evidence_event_id in regression_prefixes:
        decision_input = _decision_input(
            FIXTURE_PATH.with_name(fixture_name),
            cutoff_event_id,
        )
        selections = {
            f"value__{field_id}": "__unknown__"
            for field_id in (
                "appliance",
                "location",
                "preferred_appointment",
                "spending_limit",
            )
        }
        selections["value__active_leak"] = f"false::{evidence_event_id}"
        selections["value__quote_required"] = "__unknown__"
        result = JevProvider(
            Settings(),
            client=FakeJevClient(selections),
            model="jev-test",
        ).decide(decision_input)

        assert result.error is None
        assert result.values["active_leak"] is False
        assert result.evidence["active_leak"][0].event_id == evidence_event_id


def test_jev_adapter_rejects_selection_of_unknown_candidate() -> None:
    decision_input = _decision_input()
    selections = _jev_selections(decision_input)
    selections["value__appliance"] = "not-a-candidate"
    result = JevProvider(Settings(), client=FakeJevClient(selections), model="jev-test").decide(
        decision_input
    )

    assert result.error is not None
    assert "invalid candidate" in result.error


class FakeOpenAIResponses:
    def __init__(self, output: dict[str, Any] | None = None) -> None:
        self.output = output
        self.request: dict[str, Any] | None = None

    def create(self, **request: Any) -> Any:
        self.request = request
        return SimpleNamespace(
            status="completed",
            model=request["model"],
            output=[],
            output_text=json.dumps(self.output),
            usage=SimpleNamespace(
                input_tokens=29,
                output_tokens=11,
                input_tokens_details=SimpleNamespace(
                    cached_tokens=4,
                    cache_write_tokens=2,
                ),
            ),
        )


class FakeOpenAIClient:
    def __init__(self, responses: FakeOpenAIResponses) -> None:
        self.responses = responses


def _openai_output(decision_input) -> dict[str, Any]:
    return {
        "values": {
            "appliance": _candidate_id(decision_input, "appliance", "washing machine"),
            "location": _candidate_id(decision_input, "location", "laundry room"),
            "active_leak": "true",
            "preferred_appointment": _candidate_id(
                decision_input, "preferred_appointment", "Thursday morning"
            ),
            "quote_required": "true",
            "spending_limit": _candidate_id(
                decision_input, "spending_limit", "three hundred fifty U.S. dollars"
            ),
        },
        "evidence_event_ids": {
            "active_leak": "repair-001-e01",
            "quote_required": "repair-001-e07",
        },
    }


def test_openai_adapter_sends_strict_schema_and_maps_selected_candidates() -> None:
    decision_input = _decision_input()
    responses = FakeOpenAIResponses(_openai_output(decision_input))
    provider = StructuredLLMProvider(
        Settings(),
        client=FakeOpenAIClient(responses),
        model="gpt-test",
    )

    result = provider.decide(decision_input)

    assert responses.request is not None
    request = responses.request
    assert request["model"] == "gpt-test"
    assert "explicitly indicates the leak is active now" in request["instructions"]
    assert request["store"] is False
    assert request["text"]["format"]["strict"] is True
    assert request["text"]["format"]["schema"]["additionalProperties"] is False
    assert result.error is None
    assert result.values["appliance"] == "Washing machine"
    assert result.values["active_leak"] is True
    assert result.values["spending_limit"] == {"amount": 350, "currency": "USD"}
    assert result.evidence["preferred_appointment"][0].event_id == "repair-001-e05"
    assert result.usage == {
        "input_tokens": 29,
        "output_tokens": 11,
        "cached_input_tokens": 4,
        "cache_write_tokens": 2,
    }
    sent_input = request["input"]
    assert "gold" not in sent_input.casefold()
    assert "repair-001-e07" in sent_input


def test_openai_adapter_rejects_invalid_candidate_ids() -> None:
    decision_input = _decision_input()
    output = _openai_output(decision_input)
    output["values"]["appliance"] = "not-a-candidate"
    provider = StructuredLLMProvider(
        Settings(),
        client=FakeOpenAIClient(FakeOpenAIResponses(output)),
        model="gpt-test",
    )

    result = provider.decide(decision_input)

    assert result.error is not None
    assert "invalid candidate" in result.error


def test_openai_adapter_reports_refusals() -> None:
    decision_input = _decision_input()

    class RefusalResponses:
        def create(self, **request: Any) -> Any:
            refusal = SimpleNamespace(type="refusal", refusal="not available")
            message = SimpleNamespace(type="message", content=[refusal])
            return SimpleNamespace(
                status="completed",
                model=request["model"],
                output=[message],
                output_text="",
                usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            )

    provider = StructuredLLMProvider(
        Settings(),
        client=SimpleNamespace(responses=RefusalResponses()),
        model="gpt-test",
    )

    result = provider.decide(decision_input)

    assert result.error == "refusal: not available"


def test_provider_settings_default_to_experiment_pins() -> None:
    settings = Settings(typesafe_api_key="jev-key", openai_api_key="openai-key")

    assert settings.for_provider("jev").model == "jev-1.13.0"
    assert settings.for_provider("openai").model == "gpt-6.1-sol"


def test_replay_cli_lists_real_providers() -> None:
    result = CliRunner().invoke(app, ["replay", "--help"])

    assert result.exit_code == 0
    assert "fixture, jev, or openai" in result.output


def test_replay_cli_restricts_response_scripts_to_fixture_provider() -> None:
    result = CliRunner().invoke(
        app,
        [
            "replay",
            "--case",
            str(FIXTURE_PATH),
            "--provider",
            "openai",
            "--responses",
            "response-script.json",
        ],
    )

    assert result.exit_code != 0
    assert "only supported with --provider fixture" in result.output


def test_replay_cli_reports_missing_provider_credentials_cleanly() -> None:
    result = CliRunner().invoke(
        app,
        ["replay", "--case", str(FIXTURE_PATH), "--provider", "jev"],
        env={"TYPESAFE_API_KEY": ""},
    )

    assert result.exit_code == 2
    assert "TYPESAFE_API_KEY is required" in result.output
    assert "Traceback" not in result.output


