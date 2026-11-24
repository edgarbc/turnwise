"""Pure construction of the Turnwise decision questions and their options."""

from dataclasses import dataclass
from typing import Any, Mapping

from turnwise.contracts import DecisionInput


UNKNOWN_CHOICE = "__unknown__"


@dataclass(frozen=True, slots=True)
class TaskQuestions:
    """Provider-independent question payload and field lookup."""

    questions: Mapping[str, Mapping[str, Any]]
    question_fields: Mapping[str, str]
    candidate_fields: frozenset[str]


def build_task_questions(
    decision_input: DecisionInput,
    task_definition: Mapping[str, Any],
) -> TaskQuestions:
    """Build plain-data Choice questions shared by providers and training export."""
    candidate_fields = frozenset(
        task_definition["value_extraction"]["candidate_selected_values"]
    )
    candidates_by_field: dict[str, list[Any]] = {}
    for candidate in decision_input.candidates:
        candidates_by_field.setdefault(candidate.field_id, []).append(candidate)

    customer_events = [
        event for event in decision_input.transcript if event.speaker == "customer"
    ]
    questions: dict[str, dict[str, Any]] = {}
    question_fields: dict[str, str] = {}

    for field in task_definition["fields"]:
        field_id = field["id"]
        question_id = f"value__{field_id}"
        if question_id in questions:
            raise ValueError(f"duplicate question ID {question_id!r}")

        if field_id in candidate_fields:
            criteria = {
                candidate.candidate_id: candidate.text
                for candidate in candidates_by_field.get(field_id, [])
            }
            if UNKNOWN_CHOICE in criteria:
                raise ValueError(
                    f"candidate ID {UNKNOWN_CHOICE!r} is reserved for unknown"
                )
            criteria[UNKNOWN_CHOICE] = f"No supported value for {field_id}."
            questions[question_id] = {
                "type": "choice",
                "instructions": (
                    f"Select the candidate that answers the task field "
                    f"{field_id!r}. Select {UNKNOWN_CHOICE!r} if none does. "
                    "Do not infer or combine candidate values."
                ),
                "criteria": criteria,
            }
        else:
            criteria: dict[str, str] = {}
            for event in customer_events:
                for boolean_value in ("true", "false"):
                    option_id = f"{boolean_value}::{event.event_id}"
                    outcome_description = field.get(
                        "true_means" if boolean_value == "true" else "false_means",
                        f"The field is explicitly {boolean_value}.",
                    )
                    criteria[option_id] = (
                        f"{outcome_description} Supporting customer statement: "
                        f"{event.text}"
                    )
            if UNKNOWN_CHOICE in criteria:
                raise ValueError(
                    f"customer event creates reserved option {UNKNOWN_CHOICE!r}"
                )
            criteria[UNKNOWN_CHOICE] = field.get(
                "unknown_when", "Unknown or unstated."
            )
            questions[question_id] = {
                "type": "choice",
                "instructions": (
                    f"Determine the current value of {field_id!r} using the supplied "
                    "customer statements. Select a true/false option together with the "
                    "customer event that supports it. Select unknown if no statement "
                    "supports either known value."
                ),
                "criteria": criteria,
            }
        question_fields[question_id] = field_id

    return TaskQuestions(questions, question_fields, candidate_fields)