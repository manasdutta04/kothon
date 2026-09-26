"""Command-line entry point."""

from pathlib import Path
from typing import Annotated

import typer

from kothon.config import load_config, load_runtime_config
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
    config = load_runtime_config()
    result = run_pipeline(media, config)
    output = Path("output")
    output.mkdir(exist_ok=True)
    (output / "bengali_cc.vtt").write_text(result.bengali_vtt or result.vtt, encoding="utf-8")
    (output / "english_subtitles.srt").write_text(
        result.english_srt or result.srt, encoding="utf-8"
    )
    (output / "hindi_subtitles.srt").write_text(result.hindi_srt, encoding="utf-8")
    (output / "report.json").write_text(
        result.report.model_dump_json(indent=2), encoding="utf-8"
    )
    (output / "qc_report.json").write_text(
        result.model_dump_json(include={"qc_report"}, indent=2), encoding="utf-8"
    )
    (output / "trace.json").write_text(
        result.model_dump_json(include={"trace"}, indent=2), encoding="utf-8"
    )
    typer.echo(f"Run complete: {result.report.run_id}")


if __name__ == "__main__":
    app()
