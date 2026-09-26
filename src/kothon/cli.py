"""Command-line entry point."""

from pathlib import Path
from typing import Annotated

import typer

from kothon.config import load_config

app = typer.Typer(help="Kothon Bengali subtitle pipeline")


@app.command()
def config_check(
    config: Annotated[Path, typer.Option("--config", exists=True)] = Path("config/default.yaml"),
) -> None:
    """Validate a Kothon configuration file."""
    loaded = load_config(config)
    typer.echo(f"Configuration valid: language_hint={loaded.language_hint}")


@app.command()
def run(media: Path) -> None:
    """Run the pipeline (provider orchestration is added in a later feature)."""
    if not media.exists():
        raise typer.BadParameter(f"Media file does not exist: {media}")
    typer.echo("Pipeline execution is not configured yet; use config-check to validate setup.")


if __name__ == "__main__":
    app()
