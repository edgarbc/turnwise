"""OpenAI Responses API provider using strict structured outputs."""

import json
from time import perf_counter
from typing import Any, Mapping

from openai import OpenAI

from turnwise.contracts import (
    DecisionInput,
    DecisionResult,
    EvidenceReference,
    ValueCandidate,
)
from turnwise.pipeline.normalization import normalize_candidate
from turnwise.providers.task import load_task_definition
from turnwise.settings import Settings


UNKNOWN_CHOICE = "__unknown__"


def _nullable_enum(values: list[str]) -> dict[str, Any]:
    return {"type": ["string", "null"], "enum": [*values, None]}


class StructuredLLMProvider:
    """Compare a general LLM using a strict JSON Schema over shared candidates."""

    name = "openai"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: Any | None = None,
        model: str | None = None,
        task_definition: Mapping[str, Any] | None = None,
    ) -> None:
        loaded_settings = settings or Settings.load()
        provider_config = loaded_settings.for_provider("openai") if client is None else None
        self.model = model or (
            provider_config.model if provider_config is not None else loaded_settings.openai_model
        )
        if not self.model:
            raise ValueError("OPENAI_MODEL is required to use the openai provider.")
        self._client = client or OpenAI(api_key=provider_config.api_key)
        self._task = task_definition or load_task_definition()
        self._candidate_fields = frozenset(
            self._task["value_extraction"]["candidate_selected_values"]
        )
        self._fields = tuple(self._task["fields"])

    def _response_schema(self, decision_input: DecisionInput) -> dict[str, Any]:
        candidates_by_field: dict[str, list[ValueCandidate]] = {
            field["id"]: [] for field in self._fields
        }
        for candidate in decision_input.candidates:
            candidates_by_field.setdefault(candidate.field_id, []).append(candidate)
        customer_event_ids = [
            event.event_id
            for event in decision_input.transcript
            if event.speaker == "customer"
        ]

        value_properties: dict[str, Any] = {}
        for field in self._fields:
            field_id = field["id"]
            if field_id in self._candidate_fields:
                candidate_ids = [
                    candidate.candidate_id
                    for candidate in candidates_by_field.get(field_id, [])
                ]
                value_properties[field_id] = _nullable_enum(candidate_ids)
            else:
                value_properties[field_id] = {
                    "type": "string",
                    "enum": ["true", "false", UNKNOWN_CHOICE],
                }

        evidence_properties = {
            field["id"]: _nullable_enum(customer_event_ids)
            for field in self._fields
            if field["id"] not in self._candidate_fields
        }
        return {
            "type": "object",
            "properties": {
                "values": {
                    "type": "object",
                    "properties": value_properties,
                    "required": list(value_properties),
                    "additionalProperties": False,
                },
                "evidence_event_ids": {
                    "type": "object",
                    "properties": evidence_properties,
                    "required": list(evidence_properties),
                    "additionalProperties": False,
                },
            },
            "required": ["values", "evidence_event_ids"],
            "additionalProperties": False,
        }

    def _instructions(self) -> str:
        field_instructions = "\n".join(
            f"- {field['id']}: {field.get('description', '')} "
            f"True: {field.get('true_means', 'not applicable')} "
            f"False: {field.get('false_means', 'not applicable')} "
            f"Unknown: {field.get('unknown_when', 'not stated')}"
            for field in self._fields
        )
        return (
            "Extract the current repair-intake form from only the supplied transcript prefix. "
            "Use only customer statements as evidence; an intake-agent question is not evidence. "
            "For candidate-backed fields, choose a supplied candidate ID or null; do not invent "
            "a value; the candidate itself provides its evidence span. For active_leak and "
            "quote_required return true, false, or __unknown__, and return a customer event ID "
            "supporting each known boolean value. Use null evidence for unknowns. "
            "Do not use events after the supplied prefix.\n\nFields:\n"
            f"{field_instructions}"
        )

    def decide(self, decision_input: DecisionInput) -> DecisionResult:
        if not decision_input.transcript:
            return DecisionResult({}, {}, self.name, self.model, error="empty transcript")
        if (decision_input.task_id, decision_input.task_version) != (
            self._task["id"],
            self._task["version"],
        ):
            return DecisionResult(
                {},
                {},
                self.name,
                self.model,
                error="decision input task ID/version does not match configured task",
            )

        candidate_by_id = {
            candidate.candidate_id: candidate for candidate in decision_input.candidates
        }
        state = {
            "conversation_id": decision_input.conversation_id,
            "task_id": decision_input.task_id,
            "task_version": decision_input.task_version,
            "transcript_prefix": [
                {
                    "event_id": event.event_id,
                    "speaker": event.speaker,
                    "text": event.text,
                }
                for event in decision_input.transcript
            ],
            "candidates": [
                {
                    "candidate_id": candidate.candidate_id,
                    "field_id": candidate.field_id,
                    "text": candidate.text,
                }
                for candidate in decision_input.candidates
            ],
        }
        schema = self._response_schema(decision_input)
        started = perf_counter()
        try:
            response = self._client.responses.create(
                model=self.model,
                instructions=self._instructions(),
                input=json.dumps(state, ensure_ascii=False),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "repair_intake_decision",
                        "strict": True,
                        "schema": schema,
                    }
                },
                reasoning={"effort": "low"},
                store=False,
            )
        except Exception as error:
            return DecisionResult(
                {},
                {},
                self.name,
                self.model,
                elapsed_ms=(perf_counter() - started) * 1000,
                error=f"{type(error).__name__}: {error}",
            )
        elapsed_ms = (perf_counter() - started) * 1000

        try:
            if response.status != "completed":
                detail = getattr(response, "incomplete_details", None)
                return DecisionResult(
                    {},
                    {},
                    self.name,
                    getattr(response, "model", self.model),
                    elapsed_ms=elapsed_ms,
                    error=f"OpenAI response status {response.status!r}: {detail!r}",
                )
            for output_item in response.output:
                if output_item.type != "message":
                    continue
                for content in output_item.content:
                    if content.type == "refusal":
                        return DecisionResult(
                            {},
                            {},
                            self.name,
                            getattr(response, "model", self.model),
                            elapsed_ms=elapsed_ms,
                            error=f"refusal: {content.refusal}",
                        )

            parsed = json.loads(response.output_text)
            raw_values = parsed["values"]
            raw_evidence = parsed["evidence_event_ids"]
            values: dict[str, Any] = {}
            evidence: dict[str, tuple[EvidenceReference, ...]] = {}
            for field in self._fields:
                field_id = field["id"]
                selected = raw_values[field_id]
                if field_id in self._candidate_fields:
                    if selected is None:
                        values[field_id] = None
                        continue
                    candidate = candidate_by_id.get(selected)
                    if candidate is None or candidate.field_id != field_id:
                        raise ValueError(
                            f"OpenAI selected invalid candidate {selected!r} for {field_id!r}"
                        )
                    values[field_id] = normalize_candidate(candidate)
                    evidence[field_id] = (
                        EvidenceReference(
                            candidate.event_id,
                            candidate.start_char,
                            candidate.end_char,
                        ),
                    )
                elif selected == UNKNOWN_CHOICE:
                    values[field_id] = None
                elif selected in {"true", "false"}:
                    values[field_id] = selected == "true"
                    event_id = raw_evidence[field_id]
                    event = next(
                        (
                            event
                            for event in decision_input.transcript
                            if event.event_id == event_id and event.speaker == "customer"
                        ),
                        None,
                    )
                    if event is None:
                        raise ValueError(
                            f"known value for {field_id!r} has invalid evidence event {event_id!r}"
                        )
                    evidence[field_id] = (
                        EvidenceReference(event.event_id, 0, len(event.text)),
                    )
                else:
                    raise ValueError(f"invalid value for {field_id!r}: {selected!r}")

            usage = {}
            if response.usage.input_tokens is not None:
                usage["input_tokens"] = response.usage.input_tokens
            if response.usage.output_tokens is not None:
                usage["output_tokens"] = response.usage.output_tokens
            return DecisionResult(
                values=values,
                evidence=evidence,
                provider=self.name,
                model=response.model,
                elapsed_ms=elapsed_ms,
                usage=usage,
            )
        except Exception as error:
            return DecisionResult(
                {},
                {},
                self.name,
                self.model,
                elapsed_ms=elapsed_ms,
                error=f"invalid OpenAI response: {type(error).__name__}: {error}",
            )

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close is not None:
            close()