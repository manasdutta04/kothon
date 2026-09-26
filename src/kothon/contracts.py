"""Typed contracts shared by all pipeline stages."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TranscriptSegment(StrictModel):
    segment_id: str = Field(min_length=1)
    text: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    contains_code_mixing: bool = False
    words: list["AlignedWord"] = Field(default_factory=list)


class Transcript(StrictModel):
    segments: list[TranscriptSegment]


class SubtitleCard(StrictModel):
    card_id: str = Field(min_length=1)
    lines: list[str] = Field(min_length=1)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    source_segment_ids: list[str] = Field(min_length=1)


class Violation(StrEnum):
    MAX_CHARS = "max_chars"
    MAX_LINES = "max_lines"
    MIN_DURATION = "min_duration"
    MAX_DURATION = "max_duration"
    MAX_CPS = "max_cps"
    TIMESTAMP_OVERLAP = "timestamp_overlap"
    NONE = "none"


class RuleCheckResult(StrictModel):
    card_id: str
    char_count_per_line: list[int]
    line_count: int = Field(ge=0)
    duration: float
    reading_speed_cps: float
    violations: list[Violation]


class CorrectionApplied(StrEnum):
    LINE_REBREAK = "line_rebreak"
    CONDENSED_WORDING = "condensed_wording"
    NONE_POSSIBLE = "none_possible"


class CorrectionResult(StrictModel):
    card_id: str
    corrected_lines: list[str]
    correction_applied: CorrectionApplied
    explanation: str
    resolved: bool


class VerificationRecord(StrictModel):
    original: RuleCheckResult
    correction: CorrectionResult | None = None
    final: RuleCheckResult
    verified: bool


class AudioSignalFeatures(StrictModel):
    start: float
    end: float
    speech_activity: float = Field(ge=0, le=1)
    energy_change: float = Field(ge=0)
    spectral_change: float = Field(ge=0)
    candidate_events: list[str] = Field(default_factory=list)
    speaker_change_candidate: bool = False


class TaggingResult(StrictModel):
    card_id: str
    non_speech_tags: list[str]
    speaker_label: str | None = None
    low_confidence: bool = False


class SensitivityCategory(StrEnum):
    PROFANITY = "profanity"
    SEXUAL_CONTENT = "sexual_content"
    VIOLENCE = "violence"
    HATE_SPEECH = "hate_speech"
    SELF_HARM = "self_harm"


class SensitivityFlag(StrictModel):
    category: SensitivityCategory
    triggering_text: str = Field(min_length=1)


class ComplianceResult(StrictModel):
    card_id: str
    flags: list[SensitivityFlag]


class PipelineSummary(StrictModel):
    total_cards: int = 0
    cards_corrected: int = 0
    cards_with_unresolved_violations: int = 0
    cards_with_sensitivity_flags: int = 0


class CardReport(StrictModel):
    card: SubtitleCard
    verification: VerificationRecord | None = None
    tagging: TaggingResult | None = None
    compliance: ComplianceResult | None = None
    transcription_confidence: float | None = Field(default=None, ge=0, le=1)
    speaker_id: str | None = None
    aligned_words: list["AlignedWord"] = Field(default_factory=list)
    audio_evidence: list["AudioEvidence"] = Field(default_factory=list)


class PipelineReport(StrictModel):
    run_id: str
    language_hint: str
    cards: list[CardReport]
    summary: PipelineSummary


class PipelineResult(StrictModel):
    report: PipelineReport
    srt: str
    vtt: str
    bengali_vtt: str = ""
    english_srt: str = ""
    hindi_srt: str = ""
    bengali_lines: list[list[str]] = Field(default_factory=list)
    english_lines: list[list[str]] = Field(default_factory=list)
    hindi_lines: list[list[str]] = Field(default_factory=list)
    qc_report: dict[str, object] = Field(default_factory=dict)


class MediaMetadata(StrictModel):
    path: str
    media_type: str
    duration_seconds: float = Field(ge=0)
    sample_rate: int | None = Field(default=None, ge=1)
    channels: int | None = Field(default=None, ge=1)
    frame_rate: float | None = Field(default=None, ge=0)


class AudioChunk(StrictModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    sample_rate: int = Field(ge=1)
    samples: list[float]


class AudioEvidence(StrictModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    speech_activity: float = Field(ge=0, le=1)
    silence_score: float = Field(ge=0, le=1)
    music_score: float = Field(ge=0, le=1)
    transition_score: float = Field(ge=0, le=1)
    evidence_type: str


class SpeakerTurn(StrictModel):
    speaker_id: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    evidence: str


class AlignedWord(StrictModel):
    text: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    speaker_id: str | None = None
    alignment_method: str
    confidence: float = Field(ge=0, le=1)


class TranslatedCue(StrictModel):
    cue_id: str
    language: str
    lines: list[str]
    source_cue_id: str
    translation_confidence: float = Field(ge=0, le=1)


class QCIssue(StrictModel):
    issue_id: str
    severity: str
    score: float = Field(ge=0)
    category: str
    cue_id: str | None = None
    start: float | None = None
    end: float | None = None
    evidence: str
    recommended_action: str
    affected_tracks: list[str]


class QCReport(StrictModel):
    issues: list[QCIssue]
    review_queue: list[QCIssue]
