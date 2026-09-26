"""Command-line entry point."""

from pathlib import Path
from typing import Annotated

import typer

from kothon.config import load_config
from kothon.pipeline import run_pipeline

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
    """Run the configured pipeline and write subtitle/report outputs."""
    if not media.exists():
        raise typer.BadParameter(f"Media file does not exist: {media}")
    config = load_config(Path("config/default.yaml"))
    result = run_pipeline(media, config)
    output = Path("output")
    output.mkdir(exist_ok=True)
    (output / "subtitles.srt").write_text(result.srt, encoding="utf-8")
    (output / "subtitles.vtt").write_text(result.vtt, encoding="utf-8")
    (output / "report.json").write_text(
        result.report.model_dump_json(indent=2), encoding="utf-8"
    )
    typer.echo(f"Run complete: {result.report.run_id}")


if __name__ == "__main__":
    app()
