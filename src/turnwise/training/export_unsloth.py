"""Deterministic export of approved Turnwise prefixes to Unsloth decisions."""

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from turnwise.contracts import DecisionInput, EvidenceReference, TranscriptEvent
from turnwise.pipeline.candidates import extract_candidates
from turnwise.pipeline.normalization import normalize_candidate
from turnwise.providers.questions import UNKNOWN_CHOICE, build_task_questions


EXPORTER_VERSION = "0.1.0"


class ExportError(ValueError):
    """Raised when approved Turnwise data cannot be mapped safely for training."""


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExportError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise ExportError(f"expected a JSON object in {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_path(root: Path, value: Any, description: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ExportError(f"manifest {description} must be a non-empty path")
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise ExportError(f"manifest {description} escapes project root") from error
    return path


def _require_hash(path: Path, expected: Any, description: str) -> None:
    if not isinstance(expected, str) or _sha256(path) != expected:
        raise ExportError(f"{description} hash mismatch: {path}")


def _load_task(path: Path) -> Mapping[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ExportError(f"cannot read task definition {path}: {error}") from error
    task = data.get("task") if isinstance(data, dict) else None
    if not isinstance(task, dict):
        raise ExportError(f"task definition {path} must contain a task object")
    return task


def _load_catalog(path: Path) -> Mapping[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ExportError(f"cannot read scenario catalogue {path}: {error}") from error
    catalog = data.get("catalog") if isinstance(data, dict) else None
    if not isinstance(catalog, dict) or not isinstance(data.get("scenarios"), list):
        raise ExportError(f"scenario catalogue {path} is missing catalog/scenarios")
    return data


def _load_events(conversation: Mapping[str, Any], case_id: str) -> tuple[TranscriptEvent, ...]:
    conversation_id = conversation.get("conversation_id")
    if not isinstance(conversation_id, str) or not conversation_id:
        raise ExportError(f"{case_id}: conversation_id is missing")
    raw_events = conversation.get("events")
    if not isinstance(raw_events, list) or not raw_events:
        raise ExportError(f"{case_id}: events must be a non-empty list")
    try:
        return tuple(
            TranscriptEvent.from_mapping(conversation_id, event)
            for event in raw_events
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ExportError(f"{case_id}: invalid conversation event: {error}") from error


def _build_state(decision_input: DecisionInput) -> dict[str, Any]:
    return {
        "conversation_id": decision_input.conversation_id,
        "task_id": decision_input.task_id,
        "task_version": decision_input.task_version,
        "transcript_prefix": [
            {"event_id": event.event_id, "speaker": event.speaker, "text": event.text}
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


def _snapshot_gold(
    *,
    case_id: str,
    snapshot: Mapping[str, Any],
    decision_input: DecisionInput,
    task: Mapping[str, Any],
    questions: Mapping[str, Mapping[str, Any]],
    candidate_fields: frozenset[str],
) -> dict[str, str]:
    values = snapshot.get("values")
    evidence = snapshot.get("evidence")
    field_definitions = task.get("fields")
    if not isinstance(values, dict) or not isinstance(evidence, dict):
        raise ExportError(f"{case_id}: snapshot values and evidence must be objects")
    if not isinstance(field_definitions, list):
        raise ExportError("task fields must be a list")
    field_ids = [field["id"] for field in field_definitions]
    if set(values) != set(field_ids):
        raise ExportError(f"{case_id}: snapshot field set does not match task")
    known_fields = {field_id for field_id, value in values.items() if value is not None}
    if set(evidence) != known_fields:
        raise ExportError(f"{case_id}: evidence keys must match known fields")

    events_by_id = {event.event_id: event for event in decision_input.transcript}
    candidates_by_id = {
        candidate.candidate_id: candidate for candidate in decision_input.candidates
    }
    gold: dict[str, str] = {}

    for field_id in field_ids:
        question_id = f"value__{field_id}"
        options = questions[question_id]["criteria"]
        value = values[field_id]
        if value is None:
            target = UNKNOWN_CHOICE
        elif field_id in candidate_fields:
            references = evidence[field_id]
            if not isinstance(references, list) or not references:
                raise ExportError(f"{case_id}: known {field_id} lacks evidence")
            matches = []
            for reference in references:
                if not isinstance(reference, dict):
                    raise ExportError(f"{case_id}: invalid evidence for {field_id}")
                event_id = reference.get("event_id")
                event = events_by_id.get(event_id)
                start = reference.get("start_char")
                end = reference.get("end_char")
                if event is None or event.speaker != "customer":
                    raise ExportError(
                        f"{case_id}: {field_id} evidence must cite a visible customer event"
                    )
                if (
                    not isinstance(start, int)
                    or isinstance(start, bool)
                    or not isinstance(end, int)
                    or isinstance(end, bool)
                    or start < 0
                    or start >= end
                    or end > len(event.text)
                ):
                    raise ExportError(f"{case_id}: invalid evidence span for {field_id}")
                for candidate in decision_input.candidates:
                    if (
                        candidate.field_id == field_id
                        and candidate.event_id == event_id
                        and candidate.start_char >= start
                        and candidate.end_char <= end
                        and normalize_candidate(candidate) == value
                    ):
                        matches.append(candidate)
            unique_matches = {candidate.candidate_id: candidate for candidate in matches}
            if len(unique_matches) != 1:
                raise ExportError(
                    f"{case_id}: expected one evidence-supported {field_id} candidate, "
                    f"found {len(unique_matches)}"
                )
            target = next(iter(unique_matches))
            if target not in candidates_by_id:
                raise ExportError(f"{case_id}: gold candidate is unavailable for {field_id}")
        else:
            if not isinstance(value, bool):
                raise ExportError(f"{case_id}: boolean field {field_id} must be bool or null")
            references = evidence[field_id]
            if not isinstance(references, list) or len(references) != 1:
                raise ExportError(
                    f"{case_id}: known boolean {field_id} must have exactly one evidence event"
                )
            reference = references[0]
            event_id = reference.get("event_id") if isinstance(reference, dict) else None
            event = events_by_id.get(event_id)
            if event is None or event.speaker != "customer":
                raise ExportError(
                    f"{case_id}: boolean {field_id} evidence must cite a visible customer event"
                )
            start = reference.get("start_char")
            end = reference.get("end_char")
            if (
                not isinstance(start, int)
                or isinstance(start, bool)
                or not isinstance(end, int)
                or isinstance(end, bool)
                or start < 0
                or start >= end
                or end > len(event.text)
            ):
                raise ExportError(f"{case_id}: invalid evidence span for {field_id}")
            target = f"{str(value).lower()}::{event_id}"

        if target not in options:
            raise ExportError(
                f"{case_id}: gold target {target!r} is not an available option for {field_id}"
            )
        gold[question_id] = target

    if set(gold) != set(questions):
        raise ExportError(f"{case_id}: gold question IDs do not match questions")
    return gold


def _validate_snapshot_against_scenario(
    *,
    case_id: str,
    family_id: str,
    split: str,
    snapshot: Mapping[str, Any],
    annotation_snapshot: Mapping[str, Any],
    events: tuple[TranscriptEvent, ...],
) -> None:
    if snapshot.get("family_id") != family_id or snapshot.get("split") != split:
        raise ExportError(f"{case_id}: case family/split differs from scenario catalogue")
    specification = snapshot.get("specification")
    if not isinstance(specification, dict):
        raise ExportError(f"{case_id}: scenario specification is missing")
    turns = specification.get("turns")
    prefixes = specification.get("prefixes")
    if not isinstance(turns, list) or not isinstance(prefixes, list):
        raise ExportError(f"{case_id}: scenario turns/prefixes must be lists")
    if len(turns) != len(events):
        raise ExportError(f"{case_id}: scenario turn count differs from transcript")
    turn_to_event: dict[str, TranscriptEvent] = {}
    for turn, event in zip(turns, events):
        turn_id = turn.get("id")
        if not isinstance(turn_id, str) or turn.get("speaker") != event.speaker:
            raise ExportError(f"{case_id}: scenario turn identity/speaker mismatch")
        if turn_id in turn_to_event:
            raise ExportError(f"{case_id}: duplicate scenario turn ID {turn_id!r}")
        turn_to_event[turn_id] = event

    annotation_cutoff = annotation_snapshot.get("through_event_id")
    matching_prefixes = []
    for prefix in prefixes:
        through_turn = prefix.get("through_turn")
        event = turn_to_event.get(through_turn)
        if event is None:
            raise ExportError(f"{case_id}: scenario prefix has invalid turn cutoff")
        if event.event_id == annotation_cutoff:
            matching_prefixes.append(prefix)
    if len(matching_prefixes) != 1:
        raise ExportError(
            f"{case_id}: annotation cutoff does not map to one scenario prefix"
        )

    expected_facts = matching_prefixes[0].get("available_facts")
    values = annotation_snapshot.get("values")
    evidence = annotation_snapshot.get("evidence")
    if not isinstance(expected_facts, dict) or not isinstance(values, dict) or not isinstance(evidence, dict):
        raise ExportError(f"{case_id}: scenario facts or annotation fields are invalid")
    if set(expected_facts) != set(values):
        raise ExportError(f"{case_id}: scenario and annotation field sets differ")
    for field_id, expected in expected_facts.items():
        expected_value = expected.get("value") if isinstance(expected, dict) else expected
        if values[field_id] != expected_value:
            raise ExportError(
                f"{case_id}: annotation value for {field_id!r} differs from scenario specification"
            )
        if expected_value is None:
            continue
        expected_turn = expected.get("evidence_turn") if isinstance(expected, dict) else None
        if not isinstance(expected_turn, str) or expected_turn not in turn_to_event:
            raise ExportError(f"{case_id}: known scenario fact {field_id!r} lacks evidence turn")
        expected_event_id = turn_to_event[expected_turn].event_id
        references = evidence.get(field_id)
        if not isinstance(references, list) or not references:
            raise ExportError(f"{case_id}: known scenario fact {field_id!r} lacks annotation evidence")
        if any(reference.get("event_id") != expected_event_id for reference in references):
            raise ExportError(
                f"{case_id}: evidence event for {field_id!r} differs from scenario specification"
            )


def export_unsloth_rows(
    manifest_path: str | Path,
    task_path: str | Path,
    *,
    split: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load approved manifest data and return deterministic rows and provenance."""
    manifest_file = Path(manifest_path).resolve()
    task_file = Path(task_path).resolve()
    project_root = manifest_file.parents[2]
    manifest = _read_json(manifest_file)
    task = _load_task(task_file)
    manifest_task_path = _resolve_path(
        project_root,
        manifest.get("task", {}).get("path"),
        "task.path",
    )
    if manifest_task_path != task_file:
        raise ExportError("manifest task path does not match supplied task definition")
    _require_hash(manifest_task_path, manifest.get("task", {}).get("sha256"), "task")
    if manifest.get("task", {}).get("id") != task.get("id") or manifest.get(
        "task", {}
    ).get("version") != task.get("version"):
        raise ExportError("manifest task ID/version does not match task definition")
    if manifest.get("review_policy", {}).get("annotation_status") != "approved":
        raise ExportError("manifest annotations are not approved")
    if manifest.get("validation", {}).get("human_annotation_review") != "approved":
        raise ExportError("manifest human annotation review is not approved")
    catalog_path = _resolve_path(
        project_root,
        manifest.get("scenario_catalog", {}).get("path"),
        "scenario_catalog.path",
    )
    _require_hash(
        catalog_path,
        manifest.get("scenario_catalog", {}).get("sha256"),
        "scenario catalogue",
    )
    catalog_document = _load_catalog(catalog_path)
    catalog = catalog_document["catalog"]
    if (
        manifest.get("scenario_catalog", {}).get("id") != catalog.get("id")
        or manifest.get("scenario_catalog", {}).get("version") != catalog.get("version")
    ):
        raise ExportError("manifest scenario catalogue ID/version mismatch")
    scenarios = {item.get("id"): item for item in catalog_document["scenarios"]}

    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ExportError("manifest cases must be a non-empty list")
    family_splits: dict[str, str] = {}
    for case in cases:
        family_id = case.get("family_id")
        case_split = case.get("split")
        if not isinstance(family_id, str) or not isinstance(case_split, str):
            raise ExportError("every manifest case must include family_id and split")
        previous_split = family_splits.setdefault(family_id, case_split)
        if previous_split != case_split:
            raise ExportError(
                f"scenario family {family_id!r} leaks across splits "
                f"({previous_split!r}, {case_split!r})"
            )

    rows: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    seen_prefixes: set[tuple[str, str]] = set()
    for case in cases:
        if split is not None and case.get("split") != split:
            continue
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ExportError("manifest case has invalid case_id")
        if case.get("human_review_status") != "approved" or case.get(
            "transcript_review", {}
        ).get("outcome") != "approved":
            raise ExportError(f"{case_id}: transcript is not approved")
        if case.get("annotation_status") != "approved" or case.get(
            "annotation_review_status"
        ) != "approved":
            raise ExportError(f"{case_id}: annotation is not approved")
        scenario = scenarios.get(case_id)
        if not isinstance(scenario, dict) or scenario.get("specification_status") != "confirmed":
            raise ExportError(f"{case_id}: confirmed scenario specification is missing")

        conversation_path = _resolve_path(
            project_root, case.get("conversation_path"), f"{case_id} conversation_path"
        )
        annotation_path = _resolve_path(
            project_root, case.get("annotation_path"), f"{case_id} annotation_path"
        )
        _require_hash(conversation_path, case.get("conversation_sha256"), f"{case_id} conversation")
        _require_hash(annotation_path, case.get("annotation_sha256"), f"{case_id} annotation")
        conversation = _read_json(conversation_path)
        annotation = _read_json(annotation_path)
        if conversation.get("conversation_id") != case_id or annotation.get(
            "conversation_id"
        ) != case_id:
            raise ExportError(f"{case_id}: conversation/annotation identity mismatch")
        if (
            case.get("family_id") != scenario.get("family_id")
            or case.get("split") != scenario.get("split")
        ):
            raise ExportError(f"{case_id}: manifest case differs from scenario family/split")
        if (
            conversation.get("task_id") != task.get("id")
            or conversation.get("task_version") != task.get("version")
            or annotation.get("task_id") != task.get("id")
            or annotation.get("task_version") != task.get("version")
        ):
            raise ExportError(f"{case_id}: task ID/version mismatch")

        events = _load_events(conversation, case_id)
        raw_snapshots = annotation.get("snapshots")
        if not isinstance(raw_snapshots, list) or not raw_snapshots:
            raise ExportError(f"{case_id}: annotation snapshots must be non-empty")
        if len(raw_snapshots) != case.get("snapshot_count"):
            raise ExportError(f"{case_id}: snapshot count does not match manifest")
        event_positions = {event.event_id: position for position, event in enumerate(events)}
        previous_position = -1
        for snapshot in raw_snapshots:
            snapshot_id = snapshot.get("snapshot_id")
            cutoff = snapshot.get("through_event_id")
            if not isinstance(snapshot_id, str) or not isinstance(cutoff, str):
                raise ExportError(f"{case_id}: invalid snapshot identity/cutoff")
            prefix_position = event_positions.get(cutoff)
            if prefix_position is None or prefix_position <= previous_position:
                raise ExportError(f"{case_id}/{snapshot_id}: invalid prefix cutoff order")
            previous_position = prefix_position
            _validate_snapshot_against_scenario(
                case_id=case_id,
                family_id=str(case.get("family_id")),
                split=str(case.get("split")),
                snapshot=scenario,
                annotation_snapshot=snapshot,
                events=events,
            )
            prefix_events = events[: prefix_position + 1]
            candidates = extract_candidates(prefix_events)
            decision_input = DecisionInput(
                conversation_id=case_id,
                task_id=str(task["id"]),
                task_version=str(task["version"]),
                transcript=prefix_events,
                candidates=candidates,
            )
            task_questions = build_task_questions(decision_input, task)
            gold = _snapshot_gold(
                case_id=case_id,
                snapshot=snapshot,
                decision_input=decision_input,
                task=task,
                questions=task_questions.questions,
                candidate_fields=task_questions.candidate_fields,
            )
            key = (case_id, snapshot_id)
            if key in seen_prefixes:
                raise ExportError(f"duplicate export row for {case_id}/{snapshot_id}")
            seen_prefixes.add(key)
            rows.append(
                {
                    "state": _build_state(decision_input),
                    "questions": dict(task_questions.questions),
                    "gold": gold,
                }
            )
            metadata.append(
                {
                    "row_index": len(rows) - 1,
                    "case_id": case_id,
                    "snapshot_id": snapshot_id,
                    "through_event_id": cutoff,
                    "split": case.get("split"),
                    "scenario_family_id": case.get("family_id"),
                    "conversation_sha256": case["conversation_sha256"],
                    "annotation_sha256": case["annotation_sha256"],
                }
            )

    if not rows:
        raise ExportError(f"no approved rows found for split {split!r}")
    return rows, metadata


def write_unsloth_export(
    manifest_path: str | Path,
    task_path: str | Path,
    output_path: str | Path,
    metadata_path: str | Path,
    *,
    split: str | None = None,
) -> tuple[Path, Path, int]:
    """Write stable JSONL rows and an aligned metadata JSON sidecar."""
    rows, metadata = export_unsloth_rows(manifest_path, task_path, split=split)
    output_file = Path(output_path)
    metadata_file = Path(metadata_path)
    if output_file.resolve() == metadata_file.resolve():
        raise ExportError("row output and metadata output must be different files")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8", newline="\n") as destination:
        for row in rows:
            destination.write(
                json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n"
            )
    metadata_document = {
        "exporter_version": EXPORTER_VERSION,
        "manifest_path": str(Path(manifest_path)),
        "manifest_sha256": _sha256(Path(manifest_path).resolve()),
        "task_path": str(Path(task_path)),
        "task_sha256": _sha256(Path(task_path).resolve()),
        "split_filter": split,
        "row_count": len(metadata),
        "rows": metadata,
    }
    metadata_file.write_text(
        json.dumps(metadata_document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_file, metadata_file, len(rows)