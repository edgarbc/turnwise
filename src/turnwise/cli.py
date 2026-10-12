"""Command-line interface for Turnwise."""

from pathlib import Path

import typer

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
        help="Provider to use for the replay.",
    ),
) -> None:
    """Replay one conversation through a provider."""
    _not_implemented("replay")


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