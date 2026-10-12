"""Offline validation for task definitions and example datasets."""

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TASK_PATH = PROJECT_ROOT / "configs" / "tasks" / "repair-intake.yaml"
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True)
class ValidationReport:
    errors: tuple[str, ...]
    conversations_checked: int
    snapshots_checked: int

    @property
    def is_valid(self) -> bool:
        return not self.errors


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_json(path: Path, root: Path, errors: list[str]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{_display_path(path, root)}: cannot read JSON: {error}")
        return None


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_values(
    values: Any,
    field_definitions: Mapping[str, Mapping[str, Any]],
    path: Path,
    root: Path,
    errors: list[str],
) -> set[str]:
    if not isinstance(values, dict):
        errors.append(f"{_display_path(path, root)}: values must be an object")
        return set()

    expected_fields = set(field_definitions)
    actual_fields = set(values)
    if actual_fields != expected_fields:
        missing = sorted(expected_fields - actual_fields)
        extra = sorted(actual_fields - expected_fields)
        errors.append(
            f"{_display_path(path, root)}: values field mismatch; "
            f"missing={missing}, extra={extra}"
        )

    known_fields: set[str] = set()
    for field_id in expected_fields & actual_fields:
        value = values[field_id]
        if value is None:
            continue
        known_fields.add(field_id)
        field_type = field_definitions[field_id].get("type")
        is_valid = True
        if field_type == "string":
            is_valid = isinstance(value, str) and bool(value.strip())
        elif field_type == "boolean":
            is_valid = isinstance(value, bool)
        elif field_type == "money":
            is_valid = (
                isinstance(value, dict)
                and {"amount", "currency"}.issubset(value)
                and isinstance(value.get("amount"), (int, float, Decimal))
                and not isinstance(value.get("amount"), bool)
                and value["amount"] >= 0
                and (
                    value.get("currency") is None
                    or (
                        isinstance(value["currency"], str)
                        and _CURRENCY_PATTERN.fullmatch(value["currency"]) is not None
                    )
                )
            )
        else:
            is_valid = False
        if not is_valid:
            errors.append(
                f"{_display_path(path, root)}: invalid {field_type!r} value "
                f"for field {field_id!r}"
            )
    return known_fields


def _validate_evidence(
    evidence: Any,
    known_fields: set[str],
    events_by_id: Mapping[str, Mapping[str, Any]],
    event_positions: Mapping[str, int],
    prefix_position: int,
    path: Path,
    root: Path,
    errors: list[str],
) -> None:
    if not isinstance(evidence, dict):
        errors.append(f"{_display_path(path, root)}: evidence must be an object")
        return
    if set(evidence) != known_fields:
        errors.append(
            f"{_display_path(path, root)}: evidence fields must match known value fields"
        )

    for field_id in known_fields & set(evidence):
        references = evidence[field_id]
        if not isinstance(references, list) or not references:
            errors.append(
                f"{_display_path(path, root)}: evidence for {field_id!r} "
                "must be a non-empty list"
            )
            continue
        for reference in references:
            if not isinstance(reference, dict):
                errors.append(
                    f"{_display_path(path, root)}: evidence reference for "
                    f"{field_id!r} must be an object"
                )
                continue
            event_id = reference.get("event_id")
            start = reference.get("start_char")
            end = reference.get("end_char")
            event = events_by_id.get(event_id) if isinstance(event_id, str) else None
            if event is None:
                errors.append(
                    f"{_display_path(path, root)}: evidence for {field_id!r} "
                    f"references unknown event {event_id!r}"
                )
                continue
            if event_positions[event_id] > prefix_position:
                errors.append(
                    f"{_display_path(path, root)}: evidence for {field_id!r} "
                    f"references event {event_id!r} after the snapshot prefix"
                )
            if event.get("speaker") != "customer":
                errors.append(
                    f"{_display_path(path, root)}: evidence for {field_id!r} "
                    f"must reference customer text, not event {event_id!r}"
                )
            text = event.get("text")
            if (
                not _is_int(start)
                or not _is_int(end)
                or not isinstance(text, str)
                or start < 0
                or start >= end
                or end > len(text)
            ):
                errors.append(
                    f"{_display_path(path, root)}: evidence span for {field_id!r} "
                    f"is invalid in event {event_id!r}"
                )


def _validate_conversation(
    data: Any,
    path: Path,
    root: Path,
    task_id: str,
    task_version: str,
    speaker_roles: set[str],
    errors: list[str],
) -> tuple[list[Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    if not isinstance(data, dict):
        errors.append(f"{_display_path(path, root)}: conversation must be an object")
        return [], {}
    for key in ("conversation_id", "task_id", "task_version"):
        if not isinstance(data.get(key), str) or not data[key]:
            errors.append(f"{_display_path(path, root)}: {key} must be a non-empty string")
    if data.get("task_id") != task_id:
        errors.append(f"{_display_path(path, root)}: task_id does not match task config")
    if data.get("task_version") != task_version:
        errors.append(
            f"{_display_path(path, root)}: task_version does not match task config"
        )

    raw_events = data.get("events")
    if not isinstance(raw_events, list) or not raw_events:
        errors.append(f"{_display_path(path, root)}: events must be a non-empty list")
        return [], {}

    events: list[Mapping[str, Any]] = []
    events_by_id: dict[str, Mapping[str, Any]] = {}
    previous_start = -1
    conversation_id = data.get("conversation_id")
    for index, event in enumerate(raw_events):
        if not isinstance(event, dict):
            errors.append(f"{_display_path(path, root)}: event {index} must be an object")
            continue
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            errors.append(f"{_display_path(path, root)}: event {index} has invalid event_id")
            continue
        if event_id in events_by_id:
            errors.append(f"{_display_path(path, root)}: duplicate event_id {event_id!r}")
            continue
        events_by_id[event_id] = event
        events.append(event)
        if not isinstance(event.get("speaker"), str) or event["speaker"] not in speaker_roles:
            errors.append(
                f"{_display_path(path, root)}: event {event_id!r} has invalid speaker"
            )
        if not isinstance(event.get("text"), str) or not event["text"].strip():
            errors.append(f"{_display_path(path, root)}: event {event_id!r} has empty text")
        start = event.get("start_ms")
        end = event.get("end_ms")
        if (
            not _is_int(start)
            or not _is_int(end)
            or start < 0
            or end < start
        ):
            errors.append(f"{_display_path(path, root)}: event {event_id!r} has invalid timestamps")
        elif start < previous_start:
            errors.append(
                f"{_display_path(path, root)}: event {event_id!r} is out of timestamp order"
            )
        else:
            previous_start = start
        if not _is_int(event.get("revision", 0)) or event.get("revision", 0) < 0:
            errors.append(f"{_display_path(path, root)}: event {event_id!r} has invalid revision")
        if not isinstance(event.get("is_final", True), bool):
            errors.append(f"{_display_path(path, root)}: event {event_id!r} has invalid is_final")
        if event.get("conversation_id", conversation_id) != conversation_id:
            errors.append(
                f"{_display_path(path, root)}: event {event_id!r} belongs to another conversation"
            )
    return events, events_by_id


def validate_dataset(
    dataset_path: str | Path,
    task_path: str | Path = DEFAULT_TASK_PATH,
) -> ValidationReport:
    """Validate example conversations and annotations without model calls."""
    dataset_root = Path(dataset_path)
    task_file = Path(task_path)
    errors: list[str] = []
    try:
        task_config = yaml.safe_load(task_file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        return ValidationReport((f"{task_file}: cannot read task YAML: {error}",), 0, 0)
    task = task_config.get("task") if isinstance(task_config, dict) else None
    if not isinstance(task, dict):
        return ValidationReport((f"{task_file}: missing task object",), 0, 0)

    task_id = task.get("id")
    task_version = task.get("version")
    raw_fields = task.get("fields")
    raw_scope = task.get("scope")
    raw_roles = raw_scope.get("speaker_roles") if isinstance(raw_scope, dict) else None
    if not isinstance(task_id, str) or not task_id:
        errors.append(f"{task_file}: task.id must be a non-empty string")
    if not isinstance(task_version, str) or not task_version:
        errors.append(f"{task_file}: task.version must be a non-empty string")
    if not isinstance(raw_fields, list) or not raw_fields:
        errors.append(f"{task_file}: task.fields must be a non-empty list")
        return ValidationReport(tuple(errors), 0, 0)
    field_definitions: dict[str, Mapping[str, Any]] = {}
    for field_definition in raw_fields:
        if not isinstance(field_definition, dict):
            errors.append(f"{task_file}: each task field must be an object")
            continue
        field_id = field_definition.get("id")
        field_type = field_definition.get("type")
        if not isinstance(field_id, str) or not field_id:
            errors.append(f"{task_file}: field id must be a non-empty string")
            continue
        if field_id in field_definitions:
            errors.append(f"{task_file}: duplicate field id {field_id!r}")
            continue
        if not isinstance(field_type, str) or field_type not in {
            "string",
            "boolean",
            "money",
        }:
            errors.append(f"{task_file}: unsupported type for field {field_id!r}")
        field_definitions[field_id] = field_definition
    raw_output = task.get("output")
    if not isinstance(raw_output, dict) or raw_output.get("unknown_value", object()) is not None:
        errors.append(f"{task_file}: output.unknown_value must be null")
    if not isinstance(raw_roles, dict) or not raw_roles:
        errors.append(f"{task_file}: scope.speaker_roles must be a non-empty object")
        speaker_roles: set[str] = set()
    else:
        speaker_roles = set(raw_roles)

    conversation_dir = dataset_root / "conversations"
    annotation_dir = dataset_root / "annotations"
    if not conversation_dir.is_dir():
        errors.append(f"{conversation_dir}: conversation directory not found")
    if not annotation_dir.is_dir():
        errors.append(f"{annotation_dir}: annotation directory not found")
    conversation_files = sorted(conversation_dir.glob("*.json")) if conversation_dir.is_dir() else []
    annotation_files = sorted(annotation_dir.glob("*.json")) if annotation_dir.is_dir() else []
    if not conversation_files:
        errors.append(f"{conversation_dir}: no JSON conversation fixtures found")
    conversation_stems = {path.stem for path in conversation_files}
    annotation_stems = {path.stem for path in annotation_files}
    for stem in sorted(conversation_stems - annotation_stems):
        errors.append(f"{_display_path(conversation_dir / f'{stem}.json', dataset_root)}: matching annotation not found")
    for stem in sorted(annotation_stems - conversation_stems):
        errors.append(f"{_display_path(annotation_dir / f'{stem}.json', dataset_root)}: matching conversation not found")

    snapshots_checked = 0
    for conversation_path in conversation_files:
        conversation = _read_json(conversation_path, dataset_root, errors)
        if conversation is None:
            continue
        events, events_by_id = _validate_conversation(
            conversation,
            conversation_path,
            dataset_root,
            str(task_id),
            str(task_version),
            speaker_roles,
            errors,
        )
        annotation_path = annotation_dir / conversation_path.name
        if annotation_path.is_file():
            annotation = _read_json(annotation_path, dataset_root, errors)
            if annotation is not None:
                if not isinstance(annotation, dict):
                    errors.append(f"{_display_path(annotation_path, dataset_root)}: annotation must be an object")
                else:
                    if annotation.get("conversation_id") != conversation.get("conversation_id"):
                        errors.append(f"{_display_path(annotation_path, dataset_root)}: conversation_id does not match fixture")
                    if annotation.get("task_id") != task_id:
                        errors.append(f"{_display_path(annotation_path, dataset_root)}: task_id does not match task config")
                    if annotation.get("task_version") != task_version:
                        errors.append(f"{_display_path(annotation_path, dataset_root)}: task_version does not match task config")
                    raw_snapshots = annotation.get("snapshots")
                    if not isinstance(raw_snapshots, list) or not raw_snapshots:
                        errors.append(f"{_display_path(annotation_path, dataset_root)}: snapshots must be a non-empty list")
                    else:
                        event_positions = {
                            event["event_id"]: index
                            for index, event in enumerate(events)
                            if isinstance(event.get("event_id"), str)
                        }
                        previous_prefix_position = -1
                        snapshot_ids: set[str] = set()
                        for snapshot_index, snapshot in enumerate(raw_snapshots):
                            snapshots_checked += 1
                            if not isinstance(snapshot, dict):
                                errors.append(f"{_display_path(annotation_path, dataset_root)}: snapshot {snapshot_index} must be an object")
                                continue
                            snapshot_id = snapshot.get("snapshot_id")
                            if not isinstance(snapshot_id, str) or not snapshot_id:
                                errors.append(f"{_display_path(annotation_path, dataset_root)}: snapshot {snapshot_index} has invalid snapshot_id")
                            elif snapshot_id in snapshot_ids:
                                errors.append(f"{_display_path(annotation_path, dataset_root)}: duplicate snapshot_id {snapshot_id!r}")
                            else:
                                snapshot_ids.add(snapshot_id)
                            cutoff_id = snapshot.get("through_event_id")
                            prefix_position = event_positions.get(cutoff_id) if isinstance(cutoff_id, str) else None
                            if prefix_position is None:
                                errors.append(f"{_display_path(annotation_path, dataset_root)}: snapshot {snapshot_id!r} has unknown through_event_id {cutoff_id!r}")
                                continue
                            if prefix_position <= previous_prefix_position:
                                errors.append(f"{_display_path(annotation_path, dataset_root)}: snapshots are not in strictly increasing prefix order")
                            previous_prefix_position = prefix_position
                            known_fields = _validate_values(
                                snapshot.get("values"),
                                field_definitions,
                                annotation_path,
                                dataset_root,
                                errors,
                            )
                            _validate_evidence(
                                snapshot.get("evidence"),
                                known_fields,
                                events_by_id,
                                event_positions,
                                prefix_position,
                                annotation_path,
                                dataset_root,
                                errors,
                            )
    return ValidationReport(tuple(errors), len(conversation_files), snapshots_checked)