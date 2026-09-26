"""Model-free audio evidence for hallucination and transition checks."""

import numpy as np

from kothon.contracts import AudioChunk, AudioEvidence


def extract_evidence(
    audio: AudioChunk,
    *,
    frame_seconds: float = 0.02,
    activity_threshold: float = 0.015,
) -> list[AudioEvidence]:
    """Extract normalized energy/spectral evidence from mono PCM audio."""
    samples = np.asarray(audio.samples, dtype=np.float32)
    frame_size = max(1, round(audio.sample_rate * frame_seconds))
    if samples.size == 0:
        return []
    frames = [samples[start : start + frame_size] for start in range(0, len(samples), frame_size)]
    energies = np.asarray([float(np.sqrt(np.mean(frame * frame))) for frame in frames])
    peak = max(float(np.max(energies)), activity_threshold)
    normalized = np.clip(energies / peak, 0, 1)
    evidence: list[AudioEvidence] = []
    previous = 0.0
    for index, activity in enumerate(normalized):
        start = index * frame_seconds
        end = min(audio.end, start + frame_seconds)
        transition = float(abs(activity - previous))
        previous = float(activity)
        silence = float(1 - activity)
        evidence.append(
            AudioEvidence(
                start=start,
                end=max(end, start + 1 / audio.sample_rate),
                speech_activity=float(activity),
                silence_score=silence,
                music_score=0.0,
                transition_score=min(transition, 1.0),
                evidence_type="speech_activity" if activity >= activity_threshold else "silence",
            )
        )
    return evidence

