"""TypeSafe Jev decision provider."""

from time import perf_counter
from typing import Any, Mapping

from typesafe_sdk import Choice, TypeSafeClient

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


class JevProvider:
    """Use Jev Choices over source candidates and typed boolean outcomes."""

    name = "jev"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: Any | None = None,
        model: str | None = None,
        task_definition: Mapping[str, Any] | None = None,
    ) -> None:
        loaded_settings = settings or Settings.load()
        provider_config = loaded_settings.for_provider("jev") if client is None else None
        self.model = model or (
            provider_config.model if provider_config is not None else loaded_settings.jev_model
        )
        self._client = client or TypeSafeClient(
            api_key=provider_config.api_key if provider_config is not None else None,
            model=self.model,
        )
        self._task = task_definition or load_task_definition()
        self._candidate_fields = frozenset(
            self._task["value_extraction"]["candidate_selected_values"]
        )
        self._fields = tuple(self._task["fields"])

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

        candidates_by_id = {candidate.candidate_id: candidate for candidate in decision_input.candidates}
        candidates_by_field: dict[str, list[ValueCandidate]] = {
            field["id"]: [] for field in self._fields
        }
        for candidate in decision_input.candidates:
            candidates_by_field.setdefault(candidate.field_id, []).append(candidate)

        questions: dict[str, Choice] = {}
        question_fields: dict[str, str] = {}
        customer_events = [
            event for event in decision_input.transcript if event.speaker == "customer"
        ]
        for field in self._fields:
            field_id = field["id"]
            if field_id in self._candidate_fields:
                options = candidates_by_field.get(field_id, [])
                criteria = {
                    candidate.candidate_id: candidate.text for candidate in options
                }
                criteria[UNKNOWN_CHOICE] = f"No supported value for {field_id}."
                question_id = f"value__{field_id}"
                questions[question_id] = Choice(
                    instructions=(
                        f"Select the candidate that answers the task field "
                        f"{field_id!r}. Select {UNKNOWN_CHOICE!r} if none does. "
                        "Do not infer or combine candidate values."
                    ),
                    criteria=criteria,
                )
                question_fields[question_id] = field_id
            else:
                question_id = f"value__{field_id}"
                evidence_criteria: dict[str, str] = {}
                for event in customer_events:
                    for boolean_value in ("true", "false"):
                        option_id = f"{boolean_value}::{event.event_id}"
                        outcome_description = field.get(
                            "true_means" if boolean_value == "true" else "false_means",
                            f"The field is explicitly {boolean_value}.",
                        )
                        evidence_criteria[option_id] = (
                            f"{outcome_description} Supporting customer statement: "
                            f"{event.text}"
                        )
                evidence_criteria[UNKNOWN_CHOICE] = field.get(
                    "unknown_when", "Unknown or unstated."
                )
                questions[question_id] = Choice(
                    instructions=(
                        f"Determine the current value of {field_id!r} using the supplied "
                        "customer statements. Select a true/false option together with the "
                        "customer event that supports it. Select unknown if no statement "
                        "supports either known value."
                    ),
                    criteria=evidence_criteria,
                )
                question_fields[question_id] = field_id

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
        started = perf_counter()
        try:
            response = self._client.system_one(
                state=state,
                questions=questions,
                model=self.model,
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
            values: dict[str, Any] = {}
            evidence: dict[str, tuple[EvidenceReference, ...]] = {}
            probabilities: dict[str, Mapping[str, float]] = {}
            choices = response.choices
            for question_id, field_id in question_fields.items():
                answer = choices[question_id]
                selected = answer.choice
                probabilities[field_id] = dict(answer.probabilities)
                if selected == UNKNOWN_CHOICE:
                    values[field_id] = None
                    continue
                if field_id in self._candidate_fields:
                    candidate = candidates_by_id.get(selected)
                    if candidate is None or candidate.field_id != field_id:
                        raise ValueError(
                            f"Jev selected invalid candidate {selected!r} for {field_id!r}"
                        )
                    values[field_id] = normalize_candidate(candidate)
                    evidence[field_id] = (
                        EvidenceReference(
                            candidate.event_id,
                            candidate.start_char,
                            candidate.end_char,
                        ),
                    )
                else:
                    if selected == UNKNOWN_CHOICE:
                        values[field_id] = None
                        continue
                    boolean_value, separator, evidence_event_id = selected.partition("::")
                    if not separator or boolean_value not in {"true", "false"}:
                        raise ValueError(
                            f"Jev returned invalid boolean/evidence choice {selected!r}"
                        )
                    event = next(
                        (
                            event
                            for event in customer_events
                            if event.event_id == evidence_event_id
                        ),
                        None,
                    )
                    if event is None:
                        raise ValueError(
                            f"Jev returned invalid evidence event {evidence_event_id!r}"
                        )
                    values[field_id] = boolean_value == "true"
                    evidence[field_id] = (
                        EvidenceReference(event.event_id, 0, len(event.text)),
                    )
                    probability_totals = {"true": 0.0, "false": 0.0, UNKNOWN_CHOICE: 0.0}
                    for option, probability in answer.probabilities.items():
                        if option == UNKNOWN_CHOICE:
                            probability_totals[UNKNOWN_CHOICE] += probability
                        else:
                            option_value, option_separator, _ = option.partition("::")
                            if option_separator and option_value in {"true", "false"}:
                                probability_totals[option_value] += probability
                    probabilities[field_id] = probability_totals

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
                probabilities=probabilities or None,
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
                error=f"invalid Jev response: {type(error).__name__}: {error}",
            )

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close is not None:
            close()