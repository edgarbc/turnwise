import hashlib
import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from turnwise.cli import app


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs" / "experiments" / "jev-vs-llm.yaml"


def test_jev_vs_openai_experiment_is_pinned_and_pilot_only() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text())
    experiment = config["experiment"]
    providers = {provider["id"]: provider for provider in config["providers"]}

    assert experiment["id"] == "jev-vs-llm"
    assert experiment["status"] == "pilot"
    assert providers["jev"]["model"]["id"] == "jev-1.13.0"
    assert providers["jev"]["sdk"]["version"] == "0.7.4"
    assert providers["openai"]["model"]["id"] == "gpt-6.1-sol"
    assert providers["openai"]["sdk"]["version"] == "3.29.0"
    assert providers["openai"]["request"]["strict"] is True
    assert config["dataset"]["purpose"] == "development_pilot_only"
    assert config["dataset"]["leakage_controls"]["exclude_annotations_from_provider_input"]
    assert config["input"]["candidates"]["required_before_provider_comparison"]
    assert "per_field_macro_f1" in config["measurements"]["correctness"]


def test_all_pilot_cases_exist_as_conversation_and_annotation_pairs() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text())
    cases = config["dataset"]["cases"]
    conversations_dir = ROOT / config["dataset"]["conversations_dir"]
    annotations_dir = ROOT / config["dataset"]["annotations_dir"]

    assert len(cases) == 5
    for case_id in cases:
        assert (conversations_dir / f"{case_id}.json").is_file()
        assert (annotations_dir / f"{case_id}.json").is_file()


def test_manifest_hashes_match_and_review_is_explicitly_pending() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text())
    manifest_path = ROOT / config["dataset"]["manifest_path"]
    manifest = json.loads(manifest_path.read_text())

    assert manifest["human_review"]["required_before_hosted_benchmark"] is True
    assert manifest["human_review"]["status"] == "pending"
    assert manifest["totals"] == {"conversation_count": 5, "snapshot_count": 10}
    for path_key, digest_key in (
        ("path", "sha256"),
        ("config_path", "sha256"),
    ):
        record = manifest["task"] if path_key == "path" else manifest["experiment"]
        source_path = ROOT / record[path_key]
        assert hashlib.sha256(source_path.read_bytes()).hexdigest() == record[digest_key]
    for case in manifest["cases"]:
        for path_key, digest_key in (
            ("conversation_path", "conversation_sha256"),
            ("annotation_path", "annotation_sha256"),
        ):
            source_path = ROOT / case[path_key]
            assert hashlib.sha256(source_path.read_bytes()).hexdigest() == case[digest_key]


def test_benchmark_cli_blocks_until_gold_review_is_approved() -> None:
    result = CliRunner().invoke(
        app,
        ["benchmark", "--config", str(CONFIG_PATH), "--max-prefixes", "1"],
    )

    assert result.exit_code == 2
    assert "hosted evaluation blocked" in result.output
