from kothon.contracts import AudioEvidence, TranscriptSegment
from kothon.speech.alignment import align_segment_words
from kothon.speech.diarization import diarize


def test_diarization_assigns_stable_ids_and_alignment_marks_estimates() -> None:
    segments = [
        TranscriptSegment(segment_id="a", text="ওর office-এ", start=0, end=2, confidence=0.8),
        TranscriptSegment(segment_id="b", text="meeting আছে", start=2, end=4, confidence=0.8),
    ]
    turns = diarize(
        segments,
        [
            AudioEvidence(
                start=2,
                end=2.02,
                speech_activity=1,
                silence_score=0,
                music_score=0,
                transition_score=0.9,
                evidence_type="transition",
            )
        ],
    )
    words = align_segment_words(segments[0], turns)

    assert [turn.speaker_id for turn in turns] == ["Speaker 1", "Speaker 2"]
    assert all(word.alignment_method == "duration_weighted_estimate" for word in words)
    assert all(word.speaker_id == "Speaker 1" for word in words)
