import wave
from pathlib import Path

from kothon.config import load_config
from kothon.pipeline import run_pipeline


def test_fixture_pipeline_produces_all_primary_outputs(tmp_path: Path) -> None:
    media = tmp_path / "sample.wav"
    with wave.open(str(media), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16_000)
        audio.writeframes(b"\x00\x00" * 16_000 * 7)
    result = run_pipeline(media, load_config(Path("config/default.yaml")), run_id="run-test")

    assert result.report.run_id == "run-test"
    assert result.report.media_metadata is not None
    assert result.report.media_metadata.media_type == "audio/wav"
    assert result.report.summary.total_cards == 3
    assert "WEBVTT" in result.vtt
    assert "বাংলা" in result.bengali_vtt
    assert "This is a Bengali subtitle demo." in result.english_srt
    assert "He has an office meeting." in result.english_srt
    assert "Is everyone ready?" in result.english_srt
    assert "यह" in result.hindi_srt
    assert len(result.bengali_lines) == 3
    assert result.bengali_lines[1][0].startswith("[Speaker 1]")
    assert result.report.cards[0].verification is not None
    assert result.report.cards[0].verification.verified is True
