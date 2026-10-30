import json
import hashlib
import shutil
from pathlib import Path

import pytest
import yaml

from turnwise.pipeline.candidates import extract_candidates
from turnwise.pipeline.prefix import assemble_prefix, load_conversation
from turnwise.providers.questions import build_task_questions
from turnwise.training.export_unsloth import ExportError, export_unsloth_rows, write_unsloth_export
from turnwise.cli import app
from typer.testing import CliRunner


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "manifests" / "training-initial-drafts.json"
TASK = ROOT / "configs" / "tasks" / "repair-intake.yaml"


def _copy_training_batch(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "project"
    shutil.copytree(ROOT / "data" / "training", root / "data" / "training")
    shutil.copytree(ROOT / "data" / "scenarios", root / "data" / "scenarios")
    shutil.copytree(ROOT / "configs" / "tasks", root / "configs" / "tasks")
    manifests = root / "data" / "manifests"
    manifests.mkdir(parents=True)
    copied_manifest = manifests / MANIFEST.name
    shutil.copy2(MANIFEST, copied_manifest)
    return root, copied_manifest, root / "configs" / "tasks" / TASK.name


def test_export_rows_share_exact_jev_question_options() -> None:
    rows, metadata = export_unsloth_rows(MANIFEST, TASK)

    assert len(rows) == 13
    assert len(metadata) == 13
    assert all(set(row) == {"state", "questions", "gold"} for row in rows)
    assert all(len(row["questions"]) == 6 and len(row["gold"]) == 6 for row in rows)

    case_id = "train-candidate-distractors-001"
    row_index = next(
        item["row_index"] for item in metadata if item["case_id"] == case_id
    )
    row = rows[row_index]
    conversation = load_conversation(
        ROOT / "data" / "training" / "conversations" / f"{case_id}.json"
    )
    decision_input = assemble_prefix(
        conversation,
        "train-candidate-distractors-001-e02",
        candidates=extract_candidates(conversation.events),
    )
    task = yaml.safe_load(TASK.read_text(encoding="utf-8"))["task"]
    shared_questions = build_task_questions(decision_input, task).questions

    assert row["questions"] == shared_questions
    assert row["gold"]["value__preferred_appointment"] == next(
        candidate.candidate_id
        for candidate in decision_input.candidates
        if candidate.field_id == "preferred_appointment"
        and candidate.text == "Saturday after lunch"
    )
    assert row["gold"]["value__spending_limit"] == next(
        candidate.candidate_id
        for candidate in decision_input.candidates
        if candidate.field_id == "spending_limit" and candidate.text == "180 USD"
    )


def test_export_split_filter_and_jsonl_sidecar_are_deterministic(tmp_path: Path) -> None:
    rows, metadata = export_unsloth_rows(MANIFEST, TASK, split="training")
    assert len(rows) == 8
    assert {item["split"] for item in metadata} == {"training"}

    rows_path = tmp_path / "training.jsonl"
    metadata_path = tmp_path / "training.metadata.json"
    write_unsloth_export(
        MANIFEST, TASK, rows_path, metadata_path, split="training"
    )
    first_rows = rows_path.read_bytes()
    first_metadata = metadata_path.read_bytes()
    write_unsloth_export(
        MANIFEST, TASK, rows_path, metadata_path, split="training"
    )

    assert rows_path.read_bytes() == first_rows
    assert metadata_path.read_bytes() == first_metadata
    json_rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    sidecar = json.loads(metadata_path.read_text())
    assert len(json_rows) == sidecar["row_count"] == 8
    assert sidecar["rows"] == metadata


def test_export_refuses_unapproved_annotation(tmp_path: Path) -> None:
    _, manifest_path, task_path = _copy_training_batch(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["cases"][0]["annotation_status"] = "draft_pending_human_review"
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(ExportError, match="annotation is not approved"):
        export_unsloth_rows(manifest_path, task_path)


def test_export_refuses_annotation_hash_mismatch(tmp_path: Path) -> None:
    _, manifest_path, task_path = _copy_training_batch(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["cases"][0]["annotation_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(ExportError, match="annotation hash mismatch"):
        export_unsloth_rows(manifest_path, task_path)


def test_export_fails_closed_when_known_value_has_no_evidence_candidate(
    tmp_path: Path,
) -> None:
    root, manifest_path, task_path = _copy_training_batch(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    case = manifest["cases"][0]
    conversation_path = root / case["conversation_path"]
    conversation = json.loads(conversation_path.read_text())
    conversation["events"][0]["text"] = conversation["events"][0]["text"].replace(
        "refrigerator", "mechanical unit"
    )
    conversation_path.write_text(json.dumps(conversation))
    case["conversation_sha256"] = hashlib.sha256(conversation_path.read_bytes()).hexdigest()
    annotation_path = root / case["annotation_path"]
    annotation = json.loads(annotation_path.read_text())
    annotation["snapshots"][0]["evidence"]["appliance"][0]["end_char"] += len(
        "mechanical unit"
    ) - len("refrigerator")
    annotation_path.write_text(json.dumps(annotation))
    case["annotation_sha256"] = hashlib.sha256(annotation_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(ExportError, match="expected one evidence-supported appliance candidate"):
        export_unsloth_rows(manifest_path, task_path)


def test_export_rejects_annotation_that_disagrees_with_scenario_spec(
    tmp_path: Path,
) -> None:
    root, manifest_path, task_path = _copy_training_batch(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    case = next(
        item for item in manifest["cases"] if item["case_id"] == "train-missing-001"
    )
    annotation_path = root / case["annotation_path"]
    annotation = json.loads(annotation_path.read_text())
    annotation["snapshots"][0]["values"]["preferred_appointment"] = "Monday morning"
    annotation["snapshots"][0]["evidence"]["preferred_appointment"] = [
        {
            "event_id": "train-missing-001-e03",
            "start_char": 0,
            "end_char": 8,
        }
    ]
    annotation_path.write_text(json.dumps(annotation))
    case["annotation_sha256"] = hashlib.sha256(annotation_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(ExportError, match="differs from scenario specification"):
        export_unsloth_rows(manifest_path, task_path)


def test_export_cli_reports_validation_errors(tmp_path: Path) -> None:
    _, manifest_path, task_path = _copy_training_batch(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["cases"][0]["human_review_status"] = "unreviewed"
    manifest_path.write_text(json.dumps(manifest))
    result = CliRunner().invoke(
        app,
        [
            "export-unsloth",
            "--manifest",
            str(manifest_path),
            "--task",
            str(task_path),
            "--output",
            str(tmp_path / "rows.jsonl"),
            "--metadata",
            str(tmp_path / "metadata.json"),
        ],
    )

    assert result.exit_code == 1
    assert "transcript is not approved" in result.output


def test_export_rejects_scenario_family_leakage(tmp_path: Path) -> None:
    _, manifest_path, task_path = _copy_training_batch(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["cases"][1]["family_id"] = manifest["cases"][0]["family_id"]
    manifest["cases"][1]["split"] = "validation"
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(ExportError, match="scenario family .* leaks across splits"):
        export_unsloth_rows(manifest_path, task_path)


def test_export_unsloth_cli_writes_rows_and_metadata(tmp_path: Path) -> None:
    output = tmp_path / "rows.jsonl"
    metadata = tmp_path / "rows.metadata.json"
    result = CliRunner().invoke(
        app,
        [
            "export-unsloth",
            "--manifest",
            str(MANIFEST),
            "--task",
            str(TASK),
            "--split",
            "training",
            "--output",
            str(output),
            "--metadata",
            str(metadata),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Exported 8 rows" in result.stdout
    assert len(output.read_text().splitlines()) == 8
    assert json.loads(metadata.read_text())["row_count"] == 8
