"""Command-line interface for Turnwise."""

from pathlib import Path

import typer
import yaml

from turnwise.pipeline.prefix import load_conversation
from turnwise.pipeline.replay import replay_conversation, write_replay_artifact
from turnwise.providers.fixture import FixtureProvider
from turnwise.providers.jev import JevProvider
from turnwise.providers.structured_llm import StructuredLLMProvider
from turnwise.dataset_validation import validate_dataset

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
        raise typer.BadParameter("--responses is only supported with --provider fixture")
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
) -> None:
    """Run a configured provider benchmark."""
    _not_implemented("benchmark")


@app.command()
def report(
    run: Path = typer.Option(..., "--run", help="Run directory to report on."),
) -> None:
    """Generate a report for a completed run."""
    _not_implemented("report")