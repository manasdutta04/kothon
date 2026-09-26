"""Container-aware media utilities with no model dependencies."""

import wave
from collections.abc import Iterator
from pathlib import Path

from kothon.contracts import AudioChunk, MediaMetadata


class MediaError(RuntimeError):
    """Raised when media cannot be inspected or decoded."""


def write_audio_chunks(
    audio: AudioChunk,
    output_dir: Path,
    *,
    chunk_seconds: float = 30.0,
    overlap_seconds: float = 1.0,
) -> list[tuple[Path, float]]:
    """Write small mono PCM WAV chunks for remote transcription.

    A 30-second 16 kHz mono PCM chunk is comfortably below Groq's upload
    ceiling, including WAV headers.  The returned offset is the timestamp of
    the chunk's first sample in the source media.
    """
    if chunk_seconds <= 0 or overlap_seconds < 0 or overlap_seconds >= chunk_seconds:
        raise ValueError("chunk_seconds must be positive and overlap must be smaller")
    output_dir.mkdir(parents=True, exist_ok=True)
    import numpy as np

    samples = np.asarray(audio.samples, dtype=np.float32)
    chunk_size = max(1, round(chunk_seconds * audio.sample_rate))
    overlap = round(overlap_seconds * audio.sample_rate)
    step = max(1, chunk_size - overlap)
    chunks: list[tuple[Path, float]] = []
    for index, start in enumerate(range(0, len(samples), step), start=1):
        end = min(len(samples), start + chunk_size)
        if end <= start:
            break
        clipped = np.clip(samples[start:end], -1.0, 1.0)
        pcm = (clipped * 32767.0).astype(np.int16).tobytes()
        chunk_path = output_dir / f"chunk-{index:04d}.wav"
        with wave.open(str(chunk_path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(audio.sample_rate)
            output.writeframes(pcm)
        chunks.append((chunk_path, start / audio.sample_rate))
        if end == len(samples):
            break
    return chunks


def write_media_audio_chunks(
    media_path: Path,
    output_dir: Path,
    *,
    sample_rate: int = 16_000,
    chunk_seconds: float = 90.0,
    overlap_seconds: float = 1.5,
) -> list[tuple[Path, float]]:
    """Extract and chunk media incrementally without loading the full track."""
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if chunk_seconds <= 0 or overlap_seconds < 0 or overlap_seconds >= chunk_seconds:
        raise ValueError("chunk_seconds must be positive and overlap must be smaller")
    output_dir.mkdir(parents=True, exist_ok=True)
    chunk_bytes = round(chunk_seconds * sample_rate * 2)
    overlap_bytes = round(overlap_seconds * sample_rate * 2)
    chunks: list[tuple[Path, float]] = []
    offset = 0
    pending = b""
    for block in _media_pcm_blocks(media_path, sample_rate):
        pending += block
        while len(pending) >= chunk_bytes:
            payload = pending[:chunk_bytes]
            path = output_dir / f"chunk-{len(chunks) + 1:04d}.wav"
            _write_pcm_wav(path, payload, sample_rate)
            chunks.append((path, offset / (sample_rate * 2)))
            offset += chunk_bytes - overlap_bytes
            pending = pending[chunk_bytes - overlap_bytes :]
    if pending:
        path = output_dir / f"chunk-{len(chunks) + 1:04d}.wav"
        _write_pcm_wav(path, pending, sample_rate)
        chunks.append((path, offset / (sample_rate * 2)))
    return chunks


def _write_pcm_wav(path: Path, payload: bytes, sample_rate: int) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(payload)


def _media_pcm_blocks(media_path: Path, sample_rate: int) -> Iterator[bytes]:
    if media_path.suffix.lower() == ".wav":
        try:
            with wave.open(str(media_path), "rb") as source:
                while block := source.readframes(sample_rate * 4):
                    yield block
            return
        except (wave.Error, EOFError) as exc:
            raise MediaError(f"Invalid WAV media: {media_path.name}") from exc
    try:
        import subprocess

        import imageio_ffmpeg  # type: ignore[import-untyped]

        process = subprocess.Popen(
            [
                imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(media_path), "-f", "s16le",
                "-ac", "1", "-ar", str(sample_rate), "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert process.stdout is not None
        while block := process.stdout.read(sample_rate * 8):
            yield block
        stderr = (
            process.stderr.read().decode("utf-8", errors="replace")
            if process.stderr
            else ""
        )
        if process.wait() != 0:
            raise MediaError(f"Unable to decode audio: {media_path.name}: {stderr[-200:]}")
    except ImportError as exc:
        raise MediaError("Video decoding requires the audio dependency group") from exc


def _inspect_wav(path: Path) -> MediaMetadata:
    try:
        with wave.open(str(path), "rb") as audio:
            frames = audio.getnframes()
            rate = audio.getframerate()
            return MediaMetadata(
                path=str(path),
                media_type="audio/wav",
                duration_seconds=frames / rate if rate else 0,
                sample_rate=rate,
                channels=audio.getnchannels(),
            )
    except (wave.Error, EOFError) as exc:
        raise MediaError(f"Invalid WAV media: {path.name}") from exc


def inspect_media(path: Path) -> MediaMetadata:
    """Inspect audio/video metadata using stdlib WAV or bundled FFmpeg."""
    if not path.exists() or not path.is_file():
        raise MediaError(f"Media file does not exist: {path}")
    if path.suffix.lower() == ".wav":
        return _inspect_wav(path)
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise MediaError("Video inspection requires the audio dependency group") from exc
    try:
        import subprocess

        probe = subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        duration = 0.0
        marker = "Duration: "
        if marker in probe.stderr:
            value = probe.stderr.split(marker, 1)[1].split(",", 1)[0]
            hours, minutes, seconds = value.split(":")
            duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        return MediaMetadata(path=str(path), media_type="video", duration_seconds=duration)
    except Exception as exc:
        raise MediaError(f"Unable to inspect media: {path.name}") from exc


def read_audio(path: Path, *, sample_rate: int = 16_000) -> AudioChunk:
    """Read the complete audio track as normalized mono samples."""
    metadata = inspect_media(path)
    if path.suffix.lower() == ".wav":
        import numpy as np

        with wave.open(str(path), "rb") as audio:
            raw = audio.readframes(audio.getnframes())
            width = audio.getsampwidth()
            channels = audio.getnchannels()
            dtype = {1: np.uint8, 2: np.int16, 4: np.int32}.get(width)
            if dtype is None:
                raise MediaError(f"Unsupported WAV sample width: {width}")
            samples = np.frombuffer(raw, dtype=dtype).astype(np.float32)
            if width == 1:
                samples = ((samples - 128) / 128).astype(np.float32)
            else:
                samples /= float(2 ** (width * 8 - 1))
            samples = samples.reshape(-1, channels).mean(axis=1)
            if audio.getframerate() != sample_rate:
                duration = len(samples) / audio.getframerate()
                target_length = round(duration * sample_rate)
                samples = np.interp(
                    np.linspace(0, len(samples) - 1, target_length),
                    np.arange(len(samples)),
                    samples,
                ).astype(np.float32)
        return AudioChunk(
            start=0,
            end=metadata.duration_seconds,
            sample_rate=sample_rate,
            samples=samples.tolist(),
        )
    try:
        import subprocess

        import imageio_ffmpeg

        process = subprocess.run(
            [
                imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(path), "-f", "f32le",
                "-ac", "1", "-ar", str(sample_rate), "pipe:1",
            ],
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            raise MediaError(f"Unable to decode audio: {path.name}")
        import numpy as np

        samples = np.frombuffer(process.stdout, dtype=np.float32)
        return AudioChunk(
            start=0,
            end=len(samples) / sample_rate,
            sample_rate=sample_rate,
            samples=samples.tolist(),
        )
    except ImportError as exc:
        raise MediaError("Video decoding requires the audio dependency group") from exc
