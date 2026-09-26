import math

from kothon.audio import extract_evidence
from kothon.contracts import AudioChunk


def test_silence_is_marked_as_low_activity() -> None:
    evidence = extract_evidence(AudioChunk(start=0, end=1, sample_rate=100, samples=[0.0] * 100))

    assert evidence
    assert evidence[0].speech_activity == 0
    assert evidence[0].silence_score == 1
    assert evidence[0].evidence_type == "silence"


def test_signal_transition_is_recorded() -> None:
    samples = [0.0] * 50 + [0.5] * 50
    evidence = extract_evidence(AudioChunk(start=0, end=1, sample_rate=100, samples=samples))

    assert max(item.transition_score for item in evidence) > 0


def test_tonal_active_audio_is_marked_as_music_candidate() -> None:
    samples = [
        0.4 * math.sin(2 * math.pi * 10 * index / 1_000)
        for index in range(1_000)
    ]

    evidence = extract_evidence(AudioChunk(start=0, end=1, sample_rate=1_000, samples=samples))

    assert any(item.evidence_type == "music_candidate" for item in evidence)
