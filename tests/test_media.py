import wave
from pathlib import Path

from kothon.media import inspect_media, read_audio


def make_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8_000)
        audio.writeframes(b"\x00\x00" * 8_000)


def test_wav_metadata_and_mono_audio(tmp_path: Path) -> None:
    path = tmp_path / "sample.wav"
    make_wav(path)

    metadata = inspect_media(path)
    chunk = read_audio(path)

    assert metadata.media_type == "audio/wav"
    assert metadata.duration_seconds == 1
    assert chunk.sample_rate == 16_000
    assert chunk.end == 1
    assert len(chunk.samples) == 16_000

