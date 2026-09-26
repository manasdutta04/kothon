"""SRT and WebVTT renderers."""

from collections.abc import Iterable
from datetime import timedelta

from kothon.contracts import SubtitleCard


def _timestamp(seconds: float, *, vtt: bool = False) -> str:
    value = max(0.0, seconds)
    delta = timedelta(seconds=value)
    total_ms = round(delta.total_seconds() * 1000)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    millis = remainder % 1000
    seconds_part = remainder // 1000
    separator = "." if vtt else ","
    return f"{hours:02d}:{minutes:02d}:{seconds_part:02d}{separator}{millis:03d}"


def _text(card: SubtitleCard) -> str:
    return "\n".join(card.lines)


def render_srt(cards: Iterable[SubtitleCard]) -> str:
    """Render cards in input order as a UTF-8 SRT document."""
    blocks = []
    for index, card in enumerate(cards, start=1):
        blocks.append(
            f"{index}\n"
            f"{_timestamp(card.start)} --> {_timestamp(card.end)}\n"
            f"{_text(card)}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def render_vtt(cards: Iterable[SubtitleCard]) -> str:
    """Render cards in input order as a UTF-8 WebVTT document."""
    blocks = []
    for card in cards:
        blocks.append(
            f"{_timestamp(card.start, vtt=True)} --> {_timestamp(card.end, vtt=True)}\n"
            f"{_text(card)}"
        )
    body = "\n\n".join(blocks)
    return f"WEBVTT\n\n{body}\n" if body else "WEBVTT\n"

