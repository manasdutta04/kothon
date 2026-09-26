"""Word-to-time and word-to-speaker alignment."""

import re
from collections.abc import Sequence

from kothon.contracts import AlignedWord, SpeakerTurn, TranscriptSegment


def align_segment_words(
    segment: TranscriptSegment,
    speaker_turns: Sequence[SpeakerTurn],
) -> list[AlignedWord]:
    """Align words proportionally when provider word timestamps are absent."""
    if segment.words:
        return [_assign_speaker(word, speaker_turns) for word in segment.words]
    words = re.findall(r"\S+", segment.text)
    if not words:
        return []
    duration = max(segment.end - segment.start, 0.001)
    step = duration / len(words)
    return [
        _assign_speaker(
            AlignedWord(
                text=text,
                start=segment.start + index * step,
                end=segment.start + (index + 1) * step,
                alignment_method="duration_weighted_estimate",
                confidence=0.45,
            ),
            speaker_turns,
        )
        for index, text in enumerate(words)
    ]


def _assign_speaker(word: AlignedWord, turns: Sequence[SpeakerTurn]) -> AlignedWord:
    overlaps = [
        (max(0.0, min(word.end, turn.end) - max(word.start, turn.start)), turn)
        for turn in turns
    ]
    if not overlaps:
        return word
    overlap, turn = max(overlaps, key=lambda item: item[0])
    if overlap <= 0:
        return word
    return word.model_copy(update={"speaker_id": turn.speaker_id})

