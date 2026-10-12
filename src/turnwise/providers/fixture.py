"""Scripted provider for deterministic, offline pipeline checks."""

import json
from pathlib import Path
from typing import Any, Mapping

from turnwise.contracts import DecisionInput, DecisionResult, EvidenceReference


class FixtureProvider:
    name = "fixture"

    def __init__(
        self,
        responses: Mapping[str, DecisionResult] | None = None,
        *,
        model: str = "scripted",
    ) -> None:
        self.model = model
        self._responses = dict(responses or {})

    def decide(self, decision_input: DecisionInput) -> DecisionResult:
        """Return the scripted response for the last event in the prefix."""
        if not decision_input.transcript:
            raise ValueError("fixture provider requires a non-empty transcript")

        through_event_id = decision_input.transcript[-1].event_id
        response = self._responses.get(through_event_id)
        if response is None:
            return DecisionResult(
                values={},
                evidence={},
                provider=self.name,
                model=self.model,
            )
        return response

    @classmethod
    def from_json(cls, path: str | Path) -> "FixtureProvider":
        """Load scripted per-event responses from a separate JSON file."""
        data: Mapping[str, Any] = json.loads(
            Path(path).read_text(encoding="utf-8")
        )
        model = str(data.get("model", "scripted"))
        responses: dict[str, DecisionResult] = {}
        for item in data["responses"]:
            through_event_id = str(item["through_event_id"])
            if through_event_id in responses:
                raise ValueError(f"duplicate response for event {through_event_id!r}")
            evidence = {
                field_id: tuple(EvidenceReference(**reference) for reference in refs)
                for field_id, refs in item.get("evidence", {}).items()
            }
            responses[through_event_id] = DecisionResult(
                values=item.get("values", {}),
                evidence=evidence,
                provider=cls.name,
                model=model,
            )
        return cls(responses, model=model)