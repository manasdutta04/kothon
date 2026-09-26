"""Deterministic CPU-only speaker turn estimation."""

from collections.abc import Sequence

from kothon.contracts import AudioEvidence, SpeakerTurn, TranscriptSegment


def diarize(
    segments: Sequence[TranscriptSegment],
    evidence: Sequence[AudioEvidence] = (),
) -> list[SpeakerTurn]:
    """Return stable speaker turns without downloading diarization models.

    This conservative baseline keeps one speaker until a strong acoustic
    transition is observed. It prefers an explicit low-confidence turn over
    swapping identities silently.
    """
    if not segments:
        return []
    transitions = {round(item.start, 2) for item in evidence if item.transition_score >= 0.8}
    turns: list[SpeakerTurn] = []
    speaker_number = 1
    for index, segment in enumerate(segments):
        if index and round(segment.start, 2) in transitions:
            speaker_number += 1
        turns.append(
            SpeakerTurn(
                speaker_id=f"Speaker {speaker_number}",
                start=segment.start,
                end=segment.end,
                confidence=0.55 if index and round(segment.start, 2) in transitions else 0.7,
                evidence=(
                    "acoustic transition"
                    if index and round(segment.start, 2) in transitions
                    else "segment continuity"
                ),
            )
        )
    return turns
