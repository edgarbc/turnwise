"""Shared data contracts for Turnwise pipelines and providers."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class TranscriptEvent:
    conversation_id: str
    event_id: str
    speaker: str
    text: str
    start_ms: int
    end_ms: int
    revision: int = 0
    is_final: bool = True

    def __post_init__(self) -> None:
        if not self.conversation_id:
            raise ValueError("conversation_id must not be empty")
        if not self.event_id:
            raise ValueError("event_id must not be empty")
        if not self.speaker:
            raise ValueError("speaker must not be empty")
        if self.start_ms < 0 or self.end_ms < self.start_ms:
            raise ValueError("event timestamps must be non-negative and ordered")
        if self.revision < 0:
            raise ValueError("revision must be non-negative")

    @classmethod
    def from_mapping(
        cls, conversation_id: str, data: Mapping[str, Any]
    ) -> "TranscriptEvent":
        return cls(
            conversation_id=conversation_id,
            event_id=str(data["event_id"]),
            speaker=str(data["speaker"]),
            text=str(data["text"]),
            start_ms=int(data["start_ms"]),
            end_ms=int(data["end_ms"]),
            revision=int(data.get("revision", 0)),
            is_final=bool(data.get("is_final", True)),
        )


@dataclass(frozen=True, slots=True)
class ValueCandidate:
    candidate_id: str
    field_id: str
    event_id: str
    start_char: int
    end_char: int
    text: str

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.field_id or not self.event_id:
            raise ValueError("candidate_id, field_id, and event_id must not be empty")
        if self.start_char < 0 or self.end_char <= self.start_char:
            raise ValueError("candidate offsets must form a non-empty half-open span")


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    event_id: str
    start_char: int
    end_char: int

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("evidence event_id must not be empty")
        if self.start_char < 0 or self.end_char <= self.start_char:
            raise ValueError("evidence offsets must form a non-empty half-open span")


@dataclass(frozen=True, slots=True)
class DecisionInput:
    conversation_id: str
    task_id: str
    task_version: str
    transcript: tuple[TranscriptEvent, ...]
    candidates: tuple[ValueCandidate, ...] = ()
    reference_datetime: datetime | None = None
    timezone: str | None = None

    def __post_init__(self) -> None:
        if not self.conversation_id or not self.task_id or not self.task_version:
            raise ValueError("conversation_id, task_id, and task_version are required")
        if any(event.conversation_id != self.conversation_id for event in self.transcript):
            raise ValueError("all transcript events must belong to the input conversation")
        event_ids = [event.event_id for event in self.transcript]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("transcript event IDs must be unique")
        events_by_id = {event.event_id: event for event in self.transcript}
        for candidate in self.candidates:
            event = events_by_id.get(candidate.event_id)
            if event is None:
                raise ValueError(
                    f"candidate event {candidate.event_id!r} is outside the transcript"
                )
            if candidate.end_char > len(event.text):
                raise ValueError("candidate span exceeds its transcript event")
            if event.text[candidate.start_char : candidate.end_char] != candidate.text:
                raise ValueError("candidate text does not match its source span")


@dataclass(frozen=True, slots=True)
class DecisionResult:
    values: Mapping[str, Any]
    evidence: Mapping[str, tuple[EvidenceReference, ...]]
    provider: str
    model: str
    probabilities: Mapping[str, Mapping[str, float]] | None = None
    elapsed_ms: float | None = None
    usage: Mapping[str, int | float] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True, slots=True)
class FieldRevision:
    field_id: str
    value: Any
    evidence: tuple[EvidenceReference, ...]
    event_id: str


@dataclass(frozen=True, slots=True)
class FormSnapshot:
    conversation_id: str
    snapshot_id: str
    through_event_id: str
    values: Mapping[str, Any]
    accepted: bool = False
    revisions: tuple[FieldRevision, ...] = ()


@dataclass(frozen=True, slots=True)
class GoldSnapshot:
    conversation_id: str
    snapshot_id: str
    task_id: str
    task_version: str
    through_event_id: str
    values: Mapping[str, Any]
    evidence: Mapping[str, tuple[EvidenceReference, ...]]


@dataclass(frozen=True, slots=True)
class RunManifest:
    run_id: str
    dataset_version: str
    code_version: str
    configuration: Mapping[str, Any]
    environment: Mapping[str, str]
    measurement_policy: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ConversationFixture:
    conversation_id: str
    task_id: str
    task_version: str
    events: tuple[TranscriptEvent, ...]

    def __post_init__(self) -> None:
        if not self.conversation_id or not self.task_id or not self.task_version:
            raise ValueError("conversation_id, task_id, and task_version are required")
        if any(event.conversation_id != self.conversation_id for event in self.events):
            raise ValueError("all events must belong to the fixture conversation")
        event_ids = [event.event_id for event in self.events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("fixture event IDs must be unique")
        if any(
            current.start_ms < previous.start_ms
            for previous, current in zip(self.events, self.events[1:])
        ):
            raise ValueError("fixture events must be ordered by start_ms")