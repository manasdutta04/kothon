from pathlib import Path

from kothon.config import load_config
from kothon.pipeline import run_pipeline


def test_fixture_pipeline_produces_all_primary_outputs(tmp_path: Path) -> None:
    media = tmp_path / "sample.wav"
    media.write_bytes(b"fixture")
    result = run_pipeline(media, load_config(Path("config/default.yaml")), run_id="run-test")

    assert result.report.run_id == "run-test"
    assert result.report.summary.total_cards == 1
    assert "WEBVTT" in result.vtt
    assert "বাংলা" in result.bengali_vtt
    assert "This is a Bengali subtitle demo." in result.english_srt
    assert "यह" in result.hindi_srt
    assert result.report.cards[0].verification is not None
    assert result.report.cards[0].verification.verified is True
