import json
from pathlib import Path
from typing import Any

import yaml

from turnwise.contracts import DecisionInput, DecisionResult
from turnwise.evaluation.runner import (
    _load_and_validate_manifest,
    _macro_f1,
    run_experiment,
)
from turnwise.cli import app
from typer.testing import CliRunner


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs" / "experiments" / "jev-vs-llm.yaml"


class RecordingProvider:
    def __init__(self, name: str, *, fail: bool = False) -> None:
        self.name = name
        self.model = f"{name}-test"
        self.fail = fail
        self.inputs: list[DecisionInput] = []
        self.closed = False

    def decide(self, decision_input: DecisionInput) -> DecisionResult:
        self.inputs.append(decision_input)
        if self.fail:
            raise RuntimeError("mock provider failure")
        return DecisionResult(
            values={field: None for field in (
                "appliance",
                "location",
                "active_leak",
                "preferred_appointment",
                "quote_required",
                "spending_limit",
            )},
            evidence={},
            provider=self.name,
            model=self.model,
            elapsed_ms=1.5,
            usage={"input_tokens": 3, "output_tokens": 2},
        )

    def close(self) -> None:
        self.closed = True


def test_runner_uses_identical_prefix_inputs_and_keeps_gold_out_of_providers(
    tmp_path: Path,
) -> None:
    jev = RecordingProvider("jev")
    openai = RecordingProvider("openai")
    artifact_path = run_experiment(
        CONFIG_PATH,
        provider_factories={"jev": lambda: jev, "openai": lambda: openai},
        output_root=tmp_path,
        max_prefixes=2,
        allow_unreviewed_pilot=True,
    )

    artifact = json.loads(artifact_path.read_text())
    assert len(jev.inputs) == len(openai.inputs) == 2
    assert jev.closed and openai.closed
    for jev_input, openai_input in zip(jev.inputs, openai.inputs, strict=True):
        assert jev_input == openai_input
        assert not hasattr(jev_input, "gold")
        assert jev_input.candidates
    assert artifact["dataset"]["prefix_count"] == 2
    assert artifact["experiment"]["status"] == "pilot"
    assert len(artifact["predictions"]["jev"]) == 2
    assert len(artifact["predictions"]["openai"]) == 2
    assert artifact["summary"]["jev"]["provider_errors"] == 0
    assert artifact["summary"]["jev"]["overall_accuracy"] < 1
    assert "gold_values" in artifact["predictions"]["jev"][0]


def test_runner_records_provider_failures_and_continues(tmp_path: Path) -> None:
    jev = RecordingProvider("jev", fail=True)
    openai = RecordingProvider("openai")

    artifact_path = run_experiment(
        CONFIG_PATH,
        provider_factories={"jev": lambda: jev, "openai": lambda: openai},
        output_root=tmp_path,
        max_prefixes=1,
        allow_unreviewed_pilot=True,
    )

    artifact = json.loads(artifact_path.read_text())
    jev_record = artifact["predictions"]["jev"][0]
    openai_record = artifact["predictions"]["openai"][0]
    assert "mock provider failure" in jev_record["error"]
    assert jev_record["predicted_values"] == {}
    assert openai_record["error"] is None
    assert artifact["summary"]["jev"]["provider_errors"] == 1
    assert artifact["summary"]["openai"]["provider_errors"] == 0


def test_runner_records_provider_initialization_failure(tmp_path: Path) -> None:
    openai = RecordingProvider("openai")

    def fail_to_initialize():
        raise RuntimeError("mock initialization failure")

    artifact_path = run_experiment(
        CONFIG_PATH,
        provider_factories={
            "jev": fail_to_initialize,
            "openai": lambda: openai,
        },
        output_root=tmp_path,
        max_prefixes=1,
        allow_unreviewed_pilot=True,
    )

    artifact = json.loads(artifact_path.read_text())
    assert "mock initialization failure" in artifact["predictions"]["jev"][0]["error"]
    assert artifact["predictions"]["openai"][0]["error"] is None


def test_pending_human_review_blocks_provider_construction(tmp_path: Path) -> None:
    factory_calls: list[str] = []

    def should_not_initialize(provider_id: str):
        def factory():
            factory_calls.append(provider_id)
            return RecordingProvider(provider_id)

        return factory

    try:
        run_experiment(
            CONFIG_PATH,
            provider_factories={
                "jev": should_not_initialize("jev"),
                "openai": should_not_initialize("openai"),
            },
            output_root=tmp_path,
            max_prefixes=1,
        )
    except ValueError as error:
        assert "human_review must have" in str(error)
    else:
        raise AssertionError("pending human review should block evaluation")

    assert factory_calls == []


def test_manifest_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text())
    manifest_path = ROOT / config["dataset"]["manifest_path"]
    manifest = json.loads(manifest_path.read_text())
    manifest["cases"][0]["conversation_sha256"] = "0" * 64
    altered_manifest_path = tmp_path / "manifest.json"
    altered_manifest_path.write_text(json.dumps(manifest))

    try:
        _load_and_validate_manifest(
            altered_manifest_path,
            experiment_path=CONFIG_PATH,
            project_root=ROOT,
            config=config,
            allow_unreviewed_pilot=True,
            task_path=ROOT / config["task"]["path"],
        )
    except ValueError as error:
        assert "manifest hash mismatch" in str(error)
    else:
        raise AssertionError("manifest hash mismatch should fail closed")


def test_approval_without_reviewer_and_timestamp_is_rejected(tmp_path: Path) -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text())
    manifest_path = ROOT / config["dataset"]["manifest_path"]
    manifest = json.loads(manifest_path.read_text())
    manifest["human_review"]["status"] = "approved"
    altered_manifest_path = tmp_path / "manifest.json"
    altered_manifest_path.write_text(json.dumps(manifest))

    try:
        _load_and_validate_manifest(
            altered_manifest_path,
            experiment_path=CONFIG_PATH,
            project_root=ROOT,
            config=config,
            allow_unreviewed_pilot=False,
            task_path=ROOT / config["task"]["path"],
        )
    except ValueError as error:
        assert "reviewed_by" in str(error)
        assert "reviewed_at" in str(error)
    else:
        raise AssertionError("approval metadata is required")


def test_macro_f1_uses_per_class_f1() -> None:
    assert abs(_macro_f1([True, False, None], [True, True, None]) - 5 / 9) < 1e-12


def test_benchmark_cli_delegates_without_live_provider_calls(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[Path, int | None]] = []
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text("experiment: {}\n")
    artifact_path = tmp_path / "evaluation.json"

    def fake_run(config: Path, *, max_prefixes: int | None = None) -> Path:
        calls.append((config, max_prefixes))
        return artifact_path

    monkeypatch.setattr("turnwise.cli.run_experiment", fake_run)
    result = CliRunner().invoke(
        app,
        ["benchmark", "--config", str(config_path), "--max-prefixes", "3"],
    )

    assert result.exit_code == 0
    assert calls == [(config_path, 3)]
    assert str(artifact_path) in result.stdout


def test_report_cli_summarizes_saved_evaluation_artifact(tmp_path: Path) -> None:
    artifact_path = tmp_path / "evaluation.json"
    artifact_path.write_text(
        json.dumps(
            {
                "experiment": {"id": "pilot-test", "status": "pilot"},
                "run_id": "run-test",
                "dataset": {"prefix_count": 2},
                "provider_order": ["jev"],
                "summary": {
                    "jev": {
                        "overall_macro_f1": 0.5,
                        "overall_accuracy": 0.75,
                        "evidence_validity": 1.0,
                        "provider_errors": 0,
                    }
                },
            }
        )
    )

    result = CliRunner().invoke(app, ["report", "--run", str(artifact_path)])

    assert result.exit_code == 0
    assert "Experiment: pilot-test (pilot)" in result.stdout
    assert "jev: macro-F1=0.500, accuracy=0.750" in result.stdout


if __name__ == "__main__":
    import pytest

    pytest.main([__file__])
