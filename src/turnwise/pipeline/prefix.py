"""Load conversation fixtures and assemble provider-safe transcript prefixes."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from turnwise.contracts import (
    ConversationFixture,
    DecisionInput,
    ValueCandidate,
    TranscriptEvent,
)


def load_conversation(path: str | Path) -> ConversationFixture:
    """Load and validate a conversation JSON fixture."""
    source = Path(path)
    data: Mapping[str, Any] = json.loads(source.read_text(encoding="utf-8"))
    conversation_id = str(data["conversation_id"])
    events = tuple(
        TranscriptEvent.from_mapping(conversation_id, event_data)
        for event_data in data["events"]
    )
    return ConversationFixture(
        conversation_id=conversation_id,
        task_id=str(data["task_id"]),
        task_version=str(data["task_version"]),
        events=events,
    )


def assemble_prefix(
    fixture: ConversationFixture,
    through_event_id: str,
    *,
    candidates: tuple[ValueCandidate, ...] = (),
    reference_datetime: datetime | None = None,
    timezone: str | None = None,
) -> DecisionInput:
    """Build a decision input ending at the specified event, inclusive."""
    event_ids = [event.event_id for event in fixture.events]
    try:
        end_index = event_ids.index(through_event_id)
    except ValueError as error:
        raise ValueError(
            f"event {through_event_id!r} is not in conversation "
            f"{fixture.conversation_id!r}"
        ) from error

    return DecisionInput(
        conversation_id=fixture.conversation_id,
        task_id=fixture.task_id,
        task_version=fixture.task_version,
        transcript=fixture.events[: end_index + 1],
        candidates=candidates,
        reference_datetime=reference_datetime,
        timezone=timezone,
    )