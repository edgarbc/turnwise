"""Command-line interface for Turnwise."""

from pathlib import Path

import typer
import yaml

from turnwise.pipeline.prefix import load_conversation
from turnwise.pipeline.replay import replay_conversation, write_replay_artifact
from turnwise.providers.fixture import FixtureProvider

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
    _not_implemented("validate")


@app.command()
def replay(
    case: Path = typer.Option(..., "--case", help="Conversation fixture to replay."),
    provider: str = typer.Option(
        "fixture",
        "--provider",
        help="Provider to use for the replay (currently: fixture).",
    ),
    responses: Path | None = typer.Option(
        None,
        "--responses",
        help="Optional JSON script of fixture-provider responses.",
    ),
) -> None:
    """Replay one conversation through the offline fixture provider."""
    if provider != "fixture":
        raise typer.BadParameter("only the fixture provider is implemented")
    if not case.is_file():
        raise typer.BadParameter(f"conversation fixture not found: {case}")
    if responses is not None and not responses.is_file():
        raise typer.BadParameter(f"response script not found: {responses}")

    task = yaml.safe_load(TASK_PATH.read_text(encoding="utf-8"))["task"]
    fixture = load_conversation(case)
    fixture_provider = (
        FixtureProvider.from_json(responses)
        if responses is not None
        else FixtureProvider()
    )
    snapshots = replay_conversation(
        fixture,
        (field["id"] for field in task["fields"]),
        fixture_provider,
    )
    artifact_path = write_replay_artifact(fixture, fixture_provider, snapshots)
    typer.echo(f"Replay complete: {artifact_path}")
    if responses is None:
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