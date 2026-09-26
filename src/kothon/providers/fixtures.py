"""Deterministic providers used for offline development and tests."""

from pathlib import Path
from typing import Any

from kothon.config import SubtitleRules
from kothon.contracts import (
    ComplianceResult,
    CorrectionApplied,
    CorrectionResult,
    SubtitleCard,
    TaggingResult,
    Transcript,
    TranscriptSegment,
    TranslatedCue,
)


class FixtureTranscriptionProvider:
    def transcribe(self, media_path: Path, language_hint: str) -> Transcript:
        del media_path, language_hint
        return Transcript(
            segments=[
                TranscriptSegment(
                    segment_id="segment-0001",
                    text="এটা একটি বাংলা subtitle demo.",
                    start=0,
                    end=2.2,
                    confidence=0.98,
                    contains_code_mixing=True,
                ),
                TranscriptSegment(
                    segment_id="segment-0002",
                    text="ওর office-এ একটা meeting আছে।",
                    start=2.2,
                    end=4.6,
                    confidence=0.91,
                    contains_code_mixing=True,
                ),
                TranscriptSegment(
                    segment_id="segment-0003",
                    text="সবাই ready তো?",
                    start=4.6,
                    end=6.2,
                    confidence=0.88,
                    contains_code_mixing=True,
                ),
            ]
        )


class FixtureSegmentationProvider:
    def segment(self, transcript: Transcript, rules: SubtitleRules) -> list[SubtitleCard]:
        del rules
        return [
            SubtitleCard(
                card_id=f"card-{index:04d}",
                lines=[segment.text],
                start=segment.start,
                end=segment.end,
                source_segment_ids=[segment.segment_id],
            )
            for index, segment in enumerate(transcript.segments, start=1)
        ]


class FixtureCorrectionProvider:
    def correct(self, card: SubtitleCard, failures: Any) -> CorrectionResult:
        del failures
        return CorrectionResult(
            card_id=card.card_id,
            corrected_lines=card.lines,
            correction_applied=CorrectionApplied.NONE_POSSIBLE,
            explanation="Fixture provider does not alter cards.",
            resolved=False,
        )


class FixtureTaggingProvider:
    def tag(self, card: SubtitleCard, features: Any) -> TaggingResult:
        del features
        return TaggingResult(card_id=card.card_id, non_speech_tags=[], speaker_label=None)


class FixtureComplianceProvider:
    def analyze(self, card: SubtitleCard) -> ComplianceResult:
        return ComplianceResult(card_id=card.card_id, flags=[])


class FixtureTranslationProvider:
    def translate(self, card: SubtitleCard, language: str) -> TranslatedCue:
        translations = {
            "এটা একটি বাংলা subtitle demo.": {
                "en": "This is a Bengali subtitle demo.",
                "hi": "यह एक बंगाली उपशीर्षक डेमो है।",
            },
            "ওর office-এ একটা meeting আছে।": {
                "en": "He has an office meeting.",
                "hi": "उसकी एक ऑफिस मीटिंग है।",
            },
            "সবাই ready তো?": {
                "en": "Is everyone ready?",
                "hi": "सब तैयार हैं?",
            },
        }
        text = translations.get(card.lines[0], {}).get(language, card.lines[0])
        return TranslatedCue(
            cue_id=card.card_id,
            language=language,
            lines=[text],
            source_cue_id=card.card_id,
            translation_confidence=0.75,
        )
