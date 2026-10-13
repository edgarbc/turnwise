"""Sequential pilot evaluation over annotated transcript prefixes."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import sys
from types import SimpleNamespace
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Callable, Mapping
from uuid import uuid4

import yaml

from turnwise.contracts import DecisionInput, DecisionResult, EvidenceReference
from turnwise.dataset_validation import DEFAULT_TASK_PATH, validate_dataset
from turnwise.pipeline.candidates import extract_candidates
from turnwise.pipeline.prefix import assemble_prefix, load_conversation
from turnwise.providers.base import DecisionProvider
from turnwise.providers.jev import JevProvider
from turnwise.providers.structured_llm import StructuredLLMProvider


ProviderFactory = Callable[[], DecisionProvider]


def _json_value(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False))


def _label(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _macro_f1(gold_values: list[Any], predicted_values: list[Any]) -> float:
    labels = {_label(value) for value in gold_values + predicted_values}
    if not labels:
        return 0.0
    scores: list[float] = []
    for label in labels:
        true_positive = sum(
            _label(gold) == label and _label(predicted) == label
            for gold, predicted in zip(gold_values, predicted_values, strict=True)
        )
        false_positive = sum(
            _label(gold) != label and _label(predicted) == label
            for gold, predicted in zip(gold_values, predicted_values, strict=True)
        )
        false_negative = sum(
            _label(gold) == label and _label(predicted) != label
            for gold, predicted in zip(gold_values, predicted_values, strict=True)
        )
        denominator = 2 * true_positive + false_positive + false_negative
        scores.append(2 * true_positive / denominator if denominator else 0.0)
    return sum(scores) / len(scores)


def _evidence_is_valid(
    references: tuple[EvidenceReference, ...],
    decision_input: DecisionInput,
) -> bool:
    if not references:
        return False
    events = {event.event_id: event for event in decision_input.transcript}
    return all(
        (event := events.get(reference.event_id)) is not None
        and event.speaker == "customer"
        and 0 <= reference.start_char < reference.end_char <= len(event.text)
        for reference in references
    )


def _score_provider_records(
    records: list[dict[str, Any]], field_ids: tuple[str, ...]
) -> dict[str, Any]:
    field_metrics: dict[str, Any] = {}
    all_gold: list[Any] = []
    all_predicted: list[Any] = []
    known_value_count = 0
    valid_evidence_count = 0
    matching_evidence_count = 0
    missing_field_count = 0
    provider_error_count = 0
    refusal_count = 0
    latencies: list[float] = []
    total_usage: dict[str, int | float] = {}

    for record in records:
        if record["error"] is not None:
            provider_error_count += 1
            refusal_count += str(record["error"]).startswith("refusal:")
        if isinstance(record["elapsed_ms"], (int, float)):
            latencies.append(float(record["elapsed_ms"]))
        for key, value in record["usage"].items():
            if isinstance(value, (int, float)):
                total_usage[key] = total_usage.get(key, 0) + value
        gold = record["gold_values"]
        predicted = record["predicted_values"]
        evidence = record["predicted_evidence"]
        gold_evidence = record["gold_evidence"]
        decision_input = record["_decision_input"]
        for field_id in field_ids:
            expected = gold[field_id]
            actual = predicted.get(field_id)
            if field_id not in predicted:
                missing_field_count += 1
            all_gold.append(expected)
            all_predicted.append(actual)
            metrics = field_metrics.setdefault(
                field_id,
                {"correct": 0, "count": 0, "gold": [], "predicted": []},
            )
            metrics["count"] += 1
            metrics["correct"] += actual == expected
            metrics["gold"].append(expected)
            metrics["predicted"].append(actual)
            if expected is not None:
                known_value_count += 1
                references = tuple(evidence.get(field_id, ()))
                valid_evidence_count += _evidence_is_valid(references, decision_input)
                gold_event_ids = {
                    reference["event_id"] for reference in gold_evidence.get(field_id, [])
                }
                matching_evidence_count += bool(
                    gold_event_ids
                    & {reference.event_id for reference in references}
                )

    for field_id, metrics in field_metrics.items():
        count = metrics.pop("count")
        correct = metrics.pop("correct")
        gold_values = metrics.pop("gold")
        predicted_values = metrics.pop("predicted")
        metrics["accuracy"] = correct / count if count else 0.0
        metrics["macro_f1"] = _macro_f1(gold_values, predicted_values)

    total = len(all_gold)
    sorted_latencies = sorted(latencies)
    p95_index = max(0, math.ceil(0.95 * len(sorted_latencies)) - 1)
    return {
        "field_metrics": field_metrics,
        "overall_accuracy": sum(
            gold == predicted for gold, predicted in zip(all_gold, all_predicted, strict=True)
        ) / total if total else 0.0,
        "overall_macro_f1": _macro_f1(all_gold, all_predicted),
        "evidence_validity": (
            valid_evidence_count / known_value_count if known_value_count else None
        ),
        "evidence_matches_gold_event": (
            matching_evidence_count / known_value_count if known_value_count else None
        ),
        "missing_fields": missing_field_count,
        "provider_errors": provider_error_count,
        "refusals": refusal_count,
        "prefixes_evaluated": len(records),
        "latency_ms": {
            "p50": median(sorted_latencies) if sorted_latencies else None,
            "p95": sorted_latencies[p95_index] if sorted_latencies else None,
        },
        "usage_totals": total_usage,
    }


def _record_result(
    *,
    case_id: str,
    snapshot: Mapping[str, Any],
    provider: DecisionProvider,
    decision_input: DecisionInput,
    result: DecisionResult | None,
    error: str | None,
) -> dict[str, Any]:
    values = dict(result.values) if result is not None else {}
    evidence = {
        field_id: [
            {
                "event_id": reference.event_id,
                "start_char": reference.start_char,
                "end_char": reference.end_char,
            }
            for reference in references
        ]
        for field_id, references in (result.evidence.items() if result else [])
    }
    usage = dict(result.usage) if result is not None else {}
    raw_elapsed = result.elapsed_ms if result is not None else None
    return {
        "case_id": case_id,
        "conversation_id": decision_input.conversation_id,
        "snapshot_id": snapshot["snapshot_id"],
        "through_event_id": snapshot["through_event_id"],
        "provider": provider.name,
        "model": result.model if result is not None else provider.model,
        "predicted_values": _json_value(values),
        "predicted_evidence": evidence,
        "probabilities": _json_value(result.probabilities) if result and result.probabilities else None,
        "elapsed_ms": raw_elapsed,
        "usage": usage,
        "error": error or (result.error if result is not None else None),
        "gold_values": snapshot["values"],
        "gold_evidence": snapshot.get("evidence", {}),
        "_decision_input": decision_input,
    }


def run_experiment(
    config_path: str | Path,
    *,
    provider_factories: Mapping[str, ProviderFactory] | None = None,
    output_root: str | Path | None = None,
    max_prefixes: int | None = None,
) -> Path:
    """Run configured providers over annotated prefixes and write a pilot report.

    Annotations are loaded only by this evaluator after prefix inputs have been
    constructed; they are never passed to a provider.
    """
    experiment_path = Path(config_path).resolve()
    if max_prefixes is not None and max_prefixes < 1:
        raise ValueError("max_prefixes must be positive")
    project_root = Path(__file__).resolve().parents[3]
    config = yaml.safe_load(experiment_path.read_text(encoding="utf-8"))
    experiment = config["experiment"]
    dataset_config = config["dataset"]
    task_config = config["task"]
    base_directory = project_root

    def resolve_config_path(value: str) -> Path:
        candidate = Path(value)
        return candidate if candidate.is_absolute() else base_directory / candidate

    task_path = resolve_config_path(task_config["path"])
    dataset_root = resolve_config_path(dataset_config["conversations_dir"]).parent
    conversations_dir = resolve_config_path(dataset_config["conversations_dir"])
    annotations_dir = resolve_config_path(dataset_config["annotations_dir"])
    validation = validate_dataset(dataset_root, task_path)
    if not validation.is_valid:
        raise ValueError("dataset validation failed: " + "; ".join(validation.errors))
    task = yaml.safe_load(task_path.read_text(encoding="utf-8"))["task"]
    field_ids = tuple(field["id"] for field in task["fields"])

    factory_map: dict[str, ProviderFactory] = {
        "jev": JevProvider,
        "openai": StructuredLLMProvider,
    }
    if provider_factories:
        factory_map.update(provider_factories)
    provider_specs = {provider["id"]: provider for provider in config["providers"]}
    provider_order = config["execution"]["provider_order"]
    if any(provider_id not in provider_specs for provider_id in provider_order):
        raise ValueError("execution provider_order references an unknown provider")

    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + "-"
        + uuid4().hex[:8]
    )
    provider_records: dict[str, list[dict[str, Any]]] = {
        provider_id: [] for provider_id in provider_order
    }
    active_providers: dict[str, DecisionProvider] = {}
    initialization_errors: dict[str, str] = {}
    for provider_id in provider_order:
        try:
            active_providers[provider_id] = factory_map[provider_id]()
        except Exception as exception:
            initialization_errors[provider_id] = (
                f"{type(exception).__name__}: {exception}"
            )

    expected_prefix_count = 0
    try:
        for case_id in dataset_config["cases"]:
            conversation_path = conversations_dir / f"{case_id}.json"
            annotation_path = annotations_dir / f"{case_id}.json"
            fixture = load_conversation(conversation_path)
            annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
            event_positions = {
                event.event_id: index for index, event in enumerate(fixture.events)
            }
            for snapshot in annotation["snapshots"]:
                cutoff_id = snapshot["through_event_id"]
                prefix_position = event_positions[cutoff_id]
                prefix_events = fixture.events[: prefix_position + 1]
                decision_input = assemble_prefix(
                    fixture,
                    cutoff_id,
                    candidates=extract_candidates(prefix_events),
                )
                expected_prefix_count += 1
                for provider_id in provider_order:
                    provider = active_providers.get(provider_id)
                    if provider is None:
                        provider = SimpleNamespace(
                            name=provider_id,
                            model=provider_specs[provider_id]["model"]["id"],
                        )
                        result = None
                        error = initialization_errors[provider_id]
                    else:
                        try:
                            result = provider.decide(decision_input)
                            error = result.error
                        except Exception as exception:
                            result = None
                            error = f"{type(exception).__name__}: {exception}"
                    provider_records[provider_id].append(
                        _record_result(
                            case_id=case_id,
                            snapshot=snapshot,
                            provider=provider,
                            decision_input=decision_input,
                            result=result,
                            error=error,
                        )
                    )
                if max_prefixes is not None and expected_prefix_count >= max_prefixes:
                    break
            if max_prefixes is not None and expected_prefix_count >= max_prefixes:
                break
    finally:
        for provider in active_providers.values():
            close = getattr(provider, "close", None)
            if close is not None:
                close()

    safe_records: dict[str, list[dict[str, Any]]] = {}
    provider_summaries: dict[str, Any] = {}
    for provider_id, records in provider_records.items():
        safe_records[provider_id] = [
            {key: value for key, value in record.items() if not key.startswith("_")}
            for record in records
        ]
        provider_summaries[provider_id] = _score_provider_records(records, field_ids)

    files = sorted(
        [
            *conversations_dir.glob("*.json"),
            *annotations_dir.glob("*.json"),
            experiment_path,
            task_path,
        ]
    )
    hashes: dict[str, str] = {}
    for path in files:
        try:
            display_path = path.resolve().relative_to(project_root.resolve()).as_posix()
        except ValueError:
            display_path = path.resolve().as_posix()
        hashes[display_path] = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        code_revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        code_revision = "unknown"

    artifact = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experiment": experiment,
        "experiment_config_path": (
            experiment_path.resolve().relative_to(project_root.resolve()).as_posix()
            if experiment_path.resolve().is_relative_to(project_root.resolve())
            else experiment_path.resolve().as_posix()
        ),
        "task": {"id": task["id"], "version": task["version"]},
        "dataset": {
            "purpose": dataset_config["purpose"],
            "cases": dataset_config["cases"],
            "prefix_count": expected_prefix_count,
            "file_sha256": hashes,
        },
        "code_revision": code_revision,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "provider_order": provider_order,
        "summary": provider_summaries,
        "predictions": safe_records,
        "limitations": config.get("limitations", []),
    }
    destination_root = Path(output_root) if output_root else resolve_config_path(config["artifacts"]["output_dir"])
    run_directory = destination_root / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    artifact_path = run_directory / "evaluation.json"
    artifact_path.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return artifact_path