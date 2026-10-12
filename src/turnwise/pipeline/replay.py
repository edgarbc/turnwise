"""Offline conversation replay and monotonic form snapshot updates."""

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from turnwise.contracts import (
    ConversationFixture,
    DecisionInput,
    DecisionResult,
    EvidenceReference,
    FieldRevision,
    FormSnapshot,
)
from turnwise.providers.base import DecisionProvider


class SnapshotCommitter:
    """Apply provider results while rejecting stale transcript-prefix results."""

    def __init__(self, conversation_id: str, field_ids: Iterable[str]) -> None:
        self.conversation_id = conversation_id
        self.field_order = tuple(dict.fromkeys(field_ids))
        self.field_ids = frozenset(self.field_order)
        self._latest_position = -1
        self._values: dict[str, Any] = {field_id: None for field_id in self.field_order}
        self._evidence: dict[str, tuple[EvidenceReference, ...]] = {}
        self._revisions: list[FieldRevision] = []

    def commit(
        self,
        decision_input: DecisionInput,
        result: DecisionResult,
        *,
        through_event_id: str,
        event_position: int,
    ) -> FormSnapshot | None:
        """Apply a result, returning None when its prefix is stale."""
        if event_position <= self._latest_position:
            return None
        if not decision_input.transcript:
            raise ValueError("cannot commit a decision for an empty transcript")
        if decision_input.conversation_id != self.conversation_id:
            raise ValueError("decision input belongs to a different conversation")
        if decision_input.transcript[-1].event_id != through_event_id:
            raise ValueError("decision input does not end at through_event_id")
        if event_position != len(decision_input.transcript) - 1:
            raise ValueError("event_position does not match the transcript prefix")
        if result.error is not None:
            raise RuntimeError(f"provider {result.provider!r} failed: {result.error}")

        unknown_fields = set(result.values) - self.field_ids
        if unknown_fields:
            raise ValueError(f"provider returned unknown fields: {sorted(unknown_fields)}")
        evidence_fields_without_values = set(result.evidence) - set(result.values)
        if evidence_fields_without_values:
            raise ValueError(
                "provider returned evidence without corresponding values: "
                f"{sorted(evidence_fields_without_values)}"
            )

        visible_events = {event.event_id: event for event in decision_input.transcript}
        for field_id, value in result.values.items():
            references = tuple(result.evidence.get(field_id, ()))
            if value is not None and not references:
                raise ValueError(f"known value for {field_id!r} requires evidence")
            if value is None and references:
                raise ValueError(f"unknown value for {field_id!r} cannot have evidence")
            for reference in references:
                event = visible_events.get(reference.event_id)
                if event is None:
                    raise ValueError(
                        f"evidence event {reference.event_id!r} is outside the prefix"
                    )
                if event.speaker != "customer":
                    raise ValueError("evidence must reference a customer event")
                if reference.end_char > len(event.text):
                    raise ValueError("evidence span exceeds its transcript event")
                if reference.end_char > len(event.text):
                    raise ValueError("evidence span exceeds its transcript event")

        for field_id, value in result.values.items():
            references = tuple(result.evidence.get(field_id, ()))
            previous_value = self._values[field_id]
            if previous_value != value:
                self._revisions.append(
                    FieldRevision(
                        field_id=field_id,
                        value=value,
                        evidence=references,
                        event_id=through_event_id,
                    )
                )
            self._values[field_id] = value
            if references:
                self._evidence[field_id] = references
            else:
                self._evidence.pop(field_id, None)

        self._latest_position = event_position
        return FormSnapshot(
            conversation_id=self.conversation_id,
            snapshot_id=f"{self.conversation_id}:{through_event_id}",
            through_event_id=through_event_id,
            values=dict(self._values),
            evidence=dict(self._evidence),
            revisions=tuple(self._revisions),
        )


def replay_conversation(
    fixture: ConversationFixture,
    field_ids: Iterable[str],
    provider: DecisionProvider,
) -> tuple[FormSnapshot, ...]:
    """Run the provider against each event prefix and commit results in order."""
    from turnwise.pipeline.candidates import extract_candidates
    from turnwise.pipeline.prefix import assemble_prefix

    committer = SnapshotCommitter(fixture.conversation_id, field_ids)
    snapshots: list[FormSnapshot] = []
    for event_position, event in enumerate(fixture.events):
        prefix_events = fixture.events[: event_position + 1]
        decision_input = assemble_prefix(
            fixture,
            event.event_id,
            candidates=extract_candidates(prefix_events),
        )
        result = provider.decide(decision_input)
        snapshot = committer.commit(
            decision_input,
            result,
            through_event_id=event.event_id,
            event_position=event_position,
        )
        if snapshot is not None:
            snapshots.append(snapshot)
    return tuple(snapshots)


def snapshot_to_dict(snapshot: FormSnapshot) -> dict[str, Any]:
    """Serialize a snapshot and nested dataclasses into JSON-compatible data."""
    return asdict(snapshot)


def write_replay_artifact(
    fixture: ConversationFixture,
    provider: DecisionProvider,
    snapshots: tuple[FormSnapshot, ...],
    *,
    output_root: str | Path = "runs",
) -> Path:
    """Write replay metadata and snapshots without transcript or secret data."""
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + "-"
        + uuid4().hex[:8]
    )
    run_directory = Path(output_root) / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    artifact_path = run_directory / "replay.json"
    artifact = {
        "run_id": run_id,
        "conversation_id": fixture.conversation_id,
        "task_id": fixture.task_id,
        "task_version": fixture.task_version,
        "provider": provider.name,
        "model": provider.model,
        "snapshot_count": len(snapshots),
        "snapshots": [snapshot_to_dict(snapshot) for snapshot in snapshots],
    }
    artifact_path.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return artifact_path