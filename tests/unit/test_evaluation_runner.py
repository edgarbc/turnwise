import json
from pathlib import Path
from typing import Any

import yaml

from turnwise.contracts import DecisionInput, DecisionResult, EvidenceReference
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
    def __init__(
        self,
        name: str,
        *,
        fail: bool = False,
        values: dict[str, Any] | None = None,
        evidence: dict[str, tuple[EvidenceReference, ...]] | None = None,
    ) -> None:
        self.name = name
        self.model = f"{name}-test"
        self.fail = fail
        self.values = values
        self.evidence = evidence or {}
        self.inputs: list[DecisionInput] = []
        self.closed = False

    def decide(self, decision_input: DecisionInput) -> DecisionResult:
        self.inputs.append(decision_input)
        if self.fail:
            raise RuntimeError("mock provider failure")
        return DecisionResult(
            values=self.values or {field: None for field in (
                "appliance",
                "location",
                "active_leak",
                "preferred_appointment",
                "quote_required",
                "spending_limit",
            )},
            evidence=self.evidence,
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


def test_runner_scores_typed_evidence_and_serializes_artifact(tmp_path: Path) -> None:
    jev = RecordingProvider(
        "jev",
        values={
            "appliance": "Washing machine",
            "location": None,
            "active_leak": None,
            "preferred_appointment": None,
            "quote_required": None,
            "spending_limit": None,
        },
        evidence={
            "appliance": (EvidenceReference("repair-001-e01", 4, 19),),
        },
    )
    openai = RecordingProvider("openai")

    artifact_path = run_experiment(
        CONFIG_PATH,
        provider_factories={"jev": lambda: jev, "openai": lambda: openai},
        output_root=tmp_path,
        max_prefixes=1,
        allow_unreviewed_pilot=True,
    )

    artifact = json.loads(artifact_path.read_text())
    jev_summary = artifact["summary"]["jev"]
    jev_prediction = artifact["predictions"]["jev"][0]
    openai_summary = artifact["summary"]["openai"]
    assert abs(jev_summary["evidence_validity"] - 1 / 3) < 1e-12
    assert abs(jev_summary["evidence_matches_gold_event"] - 1 / 3) < 1e-12
    assert jev_summary["latency_ms"] == {"p50": 1.5, "p95": 1.5}
    assert jev_summary["usage_totals"] == {"input_tokens": 3, "output_tokens": 2}
    assert abs(jev_summary["estimated_cost"]["usd"] - 3 * 0.042 / 1_000_000) < 1e-15
    assert jev_summary["estimated_cost"]["complete"] is True
    assert abs(openai_summary["estimated_cost"]["usd"] - 26 / 1_000_000) < 1e-15
    assert openai_summary["estimated_cost"]["complete"] is True
    assert jev_prediction["predicted_evidence"]["appliance"] == [
        {"event_id": "repair-001-e01", "start_char": 4, "end_char": 19}
    ]


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


def test_approved_manifest_allows_mock_providers(tmp_path: Path) -> None:
    factory_calls: list[str] = []

    def factory(provider_id: str):
        def create():
            factory_calls.append(provider_id)
            return RecordingProvider(provider_id)

        return create

    artifact_path = run_experiment(
        CONFIG_PATH,
        provider_factories={"jev": factory("jev"), "openai": factory("openai")},
        output_root=tmp_path,
        max_prefixes=1,
        allow_unreviewed_pilot=True,
    )

    assert artifact_path.is_file()
    assert factory_calls == ["jev", "openai"]


def test_pending_manifest_fails_review_gate(tmp_path: Path) -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text())
    manifest_path = ROOT / config["dataset"]["manifest_path"]
    manifest = json.loads(manifest_path.read_text())
    manifest["human_review"]["status"] = "pending"
    pending_manifest = tmp_path / "pending-manifest.json"
    pending_manifest.write_text(json.dumps(manifest))

    try:
        _load_and_validate_manifest(
            pending_manifest,
            experiment_path=CONFIG_PATH,
            project_root=ROOT,
            config=config,
            allow_unreviewed_pilot=False,
            task_path=ROOT / config["task"]["path"],
        )
    except ValueError as error:
        assert "human_review must have" in str(error)
    else:
        raise AssertionError("pending human review should block evaluation")


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
    manifest["human_review"]["reviewed_by"] = None
    manifest["human_review"]["reviewed_at"] = None
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
                        "latency_ms": {"p50": 25.0, "p95": 40.0},
                        "usage_totals": {"input_tokens": 100, "output_tokens": 25},
                        "estimated_cost": {
                            "usd": 0.00045,
                            "currency": "USD",
                            "pricing_tier": "standard",
                            "complete": True,
                        },
                    }
                },
            }
        )
    )

    result = CliRunner().invoke(app, ["report", "--run", str(artifact_path)])

    assert result.exit_code == 0
    assert "Experiment: pilot-test (pilot)" in result.stdout
    assert "jev: macro-F1=0.500, accuracy=0.750" in result.stdout
    assert "latency p50=25.0 ms, p95=40.0 ms" in result.stdout
    assert "tokens in/out=100/25" in result.stdout
    assert "estimated cost ~$0.000450 USD, standard pricing" in result.stdout


if __name__ == "__main__":
    import pytest

    pytest.main([__file__])
