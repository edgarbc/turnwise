import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from turnwise.cli import app
from turnwise.dataset_validation import validate_dataset


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DATASET = ROOT / "data" / "examples"


def test_checked_in_example_dataset_is_valid() -> None:
    report = validate_dataset(EXAMPLE_DATASET)

    assert report.is_valid
    assert report.conversations_checked == 5
    assert report.snapshots_checked == 10
    assert report.errors == ()


def test_invalid_evidence_span_is_reported(tmp_path: Path) -> None:
    dataset = tmp_path / "examples"
    shutil.copytree(EXAMPLE_DATASET, dataset)
    annotation_path = dataset / "annotations" / "repair-001-ordinary.json"
    annotation = json.loads(annotation_path.read_text())
    annotation["snapshots"][0]["evidence"]["appliance"][0]["end_char"] = 999
    annotation_path.write_text(json.dumps(annotation))

    report = validate_dataset(dataset)

    assert not report.is_valid
    assert any("evidence span" in error for error in report.errors)
    assert any("repair-001-ordinary.json" in error for error in report.errors)


def test_validate_cli_returns_success_for_valid_dataset() -> None:
    result = CliRunner().invoke(app, ["validate", "--dataset", str(EXAMPLE_DATASET)])

    assert result.exit_code == 0
    assert "5 conversations, 10 snapshots checked" in result.stdout


def test_validate_cli_returns_failure_for_invalid_dataset(tmp_path: Path) -> None:
    dataset = tmp_path / "examples"
    shutil.copytree(EXAMPLE_DATASET, dataset)
    (dataset / "annotations" / "repair-001-ordinary.json").unlink()

    result = CliRunner().invoke(app, ["validate", "--dataset", str(dataset)])

    assert result.exit_code == 1
    assert "matching annotation not found" in result.output
