"""Provider interface shared by local and hosted decision backends."""

from typing import Protocol

from turnwise.contracts import DecisionInput, DecisionResult


class DecisionProvider(Protocol):
    name: str
    model: str

    def decide(self, decision_input: DecisionInput) -> DecisionResult:
        """Return decisions for the supplied transcript prefix."""