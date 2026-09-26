"""Provider protocols used by the pipeline orchestrator."""

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from kothon.config import SubtitleRules
from kothon.contracts import (
    ComplianceResult,
    CorrectionResult,
    SubtitleCard,
    TaggingResult,
    Transcript,
)


class TranscriptionProvider(Protocol):
    def transcribe(self, media_path: Path, language_hint: str) -> Transcript:
        ...


class SegmentationProvider(Protocol):
    def segment(self, transcript: Transcript, rules: SubtitleRules) -> Sequence[SubtitleCard]:
        ...


class CorrectionProvider(Protocol):
    def correct(self, card: SubtitleCard, failures: object) -> CorrectionResult:
        ...


class TaggingProvider(Protocol):
    def tag(self, card: SubtitleCard, features: object) -> TaggingResult:
        ...


class ComplianceProvider(Protocol):
    def analyze(self, card: SubtitleCard) -> ComplianceResult:
        ...
