"""Deterministic provider stages that operate only on real pipeline data."""

from collections.abc import Sequence

from kothon.config import SubtitleRules
from kothon.contracts import SubtitleCard, Transcript


class DeterministicSegmentationProvider:
    """Create readable cards from the provider transcript without inventing text."""

    def segment(self, transcript: Transcript, rules: SubtitleRules) -> Sequence[SubtitleCard]:
        cards: list[SubtitleCard] = []
        for segment in transcript.segments:
            words = segment.text.split()
            lines: list[str] = []
            current = ""
            for word in words:
                candidate = f"{current} {word}".strip()
                if current and len(candidate) > rules.max_chars_per_line:
                    lines.append(current)
                    current = word
                else:
                    current = candidate
            if current or not lines:
                lines.append(current)
            while len(lines) > rules.max_lines_per_card:
                first = lines[: rules.max_lines_per_card - 1]
                remainder = " ".join(lines[rules.max_lines_per_card - 1 :])
                lines = first + [remainder]
            cards.append(
                SubtitleCard(
                    card_id=f"card-{len(cards) + 1:04d}",
                    lines=lines,
                    start=segment.start,
                    end=segment.end,
                    source_segment_ids=[segment.segment_id],
                )
            )
        return cards
