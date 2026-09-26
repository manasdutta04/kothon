import wave
from pathlib import Path

from kothon.contracts import AudioChunk
from kothon.media import write_audio_chunks


def test_audio_chunks_have_overlap_and_pcm_wav_headers(tmp_path: Path) -> None:
    audio = AudioChunk(
        start=0,
        end=4,
        sample_rate=10,
        samples=[0.0] * 40,
    )

    chunks = write_audio_chunks(
        audio,
        tmp_path,
        chunk_seconds=2,
        overlap_seconds=0.2,
    )

    assert [round(offset, 1) for _, offset in chunks] == [0.0, 1.8, 3.6]
    with wave.open(str(chunks[0][0]), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getframerate() == 10
        assert handle.getsampwidth() == 2
