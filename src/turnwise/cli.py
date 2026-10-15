"""Command-line interface for Turnwise."""

import json
from pathlib import Path

import typer
import yaml

from turnwise.pipeline.prefix import load_conversation
from turnwise.pipeline.replay import replay_conversation, write_replay_artifact
from turnwise.providers.fixture import FixtureProvider
from turnwise.providers.jev import JevProvider
from turnwise.providers.structured_llm import StructuredLLMProvider
from turnwise.dataset_validation import validate_dataset
from turnwise.evaluation.runner import run_experiment

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TASK_PATH = PROJECT_ROOT / "configs" / "tasks" / "repair-intake.yaml"

app = typer.Typer(
    name="turnwise",
    help="Work with Turnwise datasets, replays, benchmarks, and reports.",
    no_args_is_help=True,
)


def _not_implemented(command: str) -> None:
    typer.echo(f"The {command} command is not implemented yet.", err=True)
    raise typer.Exit(code=2)


@app.command()
def validate(
    dataset: Path = typer.Option(
        Path("data/examples"),
        "--dataset",
        help="Dataset directory to validate.",
    ),
) -> None:
    """Validate example conversations and annotations."""
    report = validate_dataset(dataset, TASK_PATH)
    if report.is_valid:
        typer.echo(
            "Dataset valid: "
            f"{report.conversations_checked} conversations, "
            f"{report.snapshots_checked} snapshots checked."
        )
        return

    for error in report.errors:
        typer.echo(f"ERROR: {error}", err=True)
    typer.echo(f"Dataset invalid: {len(report.errors)} error(s).", err=True)
    raise typer.Exit(code=1)


@app.command()
def replay(
    case: Path = typer.Option(..., "--case", help="Conversation fixture to replay."),
    provider: str = typer.Option(
        "fixture",
        "--provider",
        help="Provider to use: fixture, jev, or openai.",
    ),
    responses: Path | None = typer.Option(
        None,
        "--responses",
        help="Optional JSON script of fixture-provider responses.",
    ),
) -> None:
    """Replay one conversation through the selected decision provider."""
    if provider not in {"fixture", "jev", "openai"}:
        raise typer.BadParameter("provider must be fixture, jev, or openai")
    if responses is not None and provider != "fixture":
        typer.echo(
            "Error: --responses is only supported with --provider fixture",
            err=True,
        )
        raise typer.Exit(code=2)
    if not case.is_file():
        raise typer.BadParameter(f"conversation fixture not found: {case}")
    if responses is not None and not responses.is_file():
        raise typer.BadParameter(f"response script not found: {responses}")

    task = yaml.safe_load(TASK_PATH.read_text(encoding="utf-8"))["task"]
    fixture = load_conversation(case)
    try:
        if provider == "fixture":
            active_provider = (
                FixtureProvider.from_json(responses)
                if responses is not None
                else FixtureProvider()
            )
        elif provider == "jev":
            active_provider = JevProvider()
        else:
            active_provider = StructuredLLMProvider()
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error

    try:
        snapshots = replay_conversation(
            fixture,
            (field["id"] for field in task["fields"]),
            active_provider,
        )
        artifact_path = write_replay_artifact(fixture, active_provider, snapshots)
    finally:
        close = getattr(active_provider, "close", None)
        if close is not None:
            close()
    typer.echo(f"Replay complete: {artifact_path}")
    if provider == "fixture" and responses is None:
        typer.echo(
            "No response script supplied; the fixture provider made no field updates."
        )


@app.command()
def benchmark(
    config: Path = typer.Option(..., "--config", help="Benchmark configuration."),
    max_prefixes: int | None = typer.Option(
        None,
        "--max-prefixes",
        min=1,
        help="Optional positive limit for a bounded pilot run.",
    ),
) -> None:
    """Run the configured provider comparison and save evaluation results."""
    if not config.is_file():
        raise typer.BadParameter(f"experiment config not found: {config}")
    try:
        artifact_path = run_experiment(config, max_prefixes=max_prefixes)
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(f"Evaluation complete: {artifact_path}")


@app.command()
def report(
    run: Path = typer.Option(..., "--run", help="Run directory to report on."),
) -> None:
    """Summarize a completed evaluation artifact."""
    artifact_path = run / "evaluation.json" if run.is_dir() else run
    if not artifact_path.is_file():
        raise typer.BadParameter(f"evaluation artifact not found: {artifact_path}")
    try:
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise typer.BadParameter(f"cannot read evaluation artifact: {error}") from error

    typer.echo(f"Experiment: {artifact['experiment']['id']} ({artifact['experiment']['status']})")
    typer.echo(f"Run: {artifact['run_id']}")
    typer.echo(f"Prefixes: {artifact['dataset']['prefix_count']}")
    for provider_id in artifact["provider_order"]:
        summary = artifact["summary"][provider_id]
        latency = summary.get("latency_ms", {})
        usage = summary.get("usage_totals", {})
        cost = summary.get("estimated_cost", {})
        p50 = latency.get("p50")
        p95 = latency.get("p95")
        latency_text = (
            f"p50={p50:.1f} ms, p95={p95:.1f} ms"
            if isinstance(p50, (int, float)) and isinstance(p95, (int, float))
            else "unavailable"
        )
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        if cost.get("usd") is None:
            cost_text = "unavailable"
        else:
            cost_text = f"~${cost['usd']:.6f} {cost.get('currency', 'USD')}"
            if not cost.get("complete", True):
                cost_text += " (partial; some usage unreported)"
            if cost.get("pricing_tier"):
                cost_text += f", {cost['pricing_tier']} pricing"
        typer.echo(
            f"{provider_id}: macro-F1={summary['overall_macro_f1']:.3f}, "
            f"accuracy={summary['overall_accuracy']:.3f}, "
            f"evidence-validity={summary['evidence_validity']}, "
            f"latency {latency_text}, tokens in/out={input_tokens}/{output_tokens}, "
            f"estimated cost {cost_text}, errors={summary['provider_errors']}"
        )