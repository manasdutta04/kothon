"""Model-free audio evidence for hallucination and transition checks."""

import numpy as np

from kothon.contracts import AudioChunk, AudioEvidence


def extract_evidence(
    audio: AudioChunk,
    *,
    frame_seconds: float = 0.25,
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
    previous_spectrum: np.ndarray | None = None
    for index, activity in enumerate(normalized):
        frame = frames[index]
        window = frame * np.hanning(len(frame))
        spectrum = np.abs(np.fft.rfft(window))
        spectrum = spectrum / max(float(np.sum(spectrum)), 1e-9)
        spectral_flatness = float(
            np.exp(np.mean(np.log(np.maximum(spectrum, 1e-9))))
            / max(float(np.mean(spectrum)), 1e-9)
        )
        tonal_score = float(np.clip(1.0 - spectral_flatness, 0, 1))
        spectral_change = (
            0.0
            if previous_spectrum is None
            else float(np.clip(np.mean(np.abs(spectrum - previous_spectrum)) * 10, 0, 1))
        )
        previous_spectrum = spectrum
        start = index * frame_seconds
        end = min(audio.end, start + frame_seconds)
        transition = float(max(abs(activity - previous), spectral_change))
        previous = float(activity)
        silence = float(1 - activity)
        music_score = float(np.clip(activity * tonal_score, 0, 1))
        if activity < activity_threshold:
            evidence_type = "silence"
        elif music_score >= 0.7:
            evidence_type = "music_candidate"
        else:
            evidence_type = "speech_activity"
        evidence.append(
            AudioEvidence(
                start=start,
                end=max(end, start + 1 / audio.sample_rate),
                speech_activity=float(activity),
                silence_score=silence,
                music_score=music_score,
                transition_score=min(transition, 1.0),
                evidence_type=evidence_type,
            )
        )
    return evidence
