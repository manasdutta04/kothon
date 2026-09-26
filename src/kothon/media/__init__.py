"""Media inspection and audio extraction."""

from kothon.media.io import (
    MediaError,
    inspect_media,
    read_audio,
    write_audio_chunks,
    write_media_audio_chunks,
)

__all__ = [
    "MediaError",
    "inspect_media",
    "read_audio",
    "write_audio_chunks",
    "write_media_audio_chunks",
]
