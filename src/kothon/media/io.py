"""Container-aware media utilities with no model dependencies."""

import wave
from pathlib import Path

from kothon.contracts import AudioChunk, MediaMetadata


class MediaError(RuntimeError):
    """Raised when media cannot be inspected or decoded."""


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
        import imageio_ffmpeg  # type: ignore[import-untyped]
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
