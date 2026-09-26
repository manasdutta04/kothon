"""Provider-independent Kothon pipeline orchestration."""

from pathlib import Path
from uuid import uuid4

from kothon.assembly.report import build_report
from kothon.assembly.subtitles import render_srt, render_vtt
from kothon.config import KothonConfig
from kothon.contracts import (
    CardReport,
    PipelineResult,
    SubtitleCard,
    VerificationRecord,
    Violation,
)
from kothon.providers.fixtures import (
    FixtureComplianceProvider,
    FixtureCorrectionProvider,
    FixtureSegmentationProvider,
    FixtureTaggingProvider,
    FixtureTranscriptionProvider,
)
from kothon.verification.rules import check_card


def run_pipeline(
    media_path: Path,
    config: KothonConfig,
    *,
    run_id: str | None = None,
) -> PipelineResult:
    """Run the offline fixture pipeline with deterministic verification.

    Provider selection is intentionally explicit. Real remote providers are
    added behind the same interfaces; the fixture path is the safe default for
    local development and CI.
    """
    if not media_path.exists():
        raise FileNotFoundError(media_path)
    if config.providers.transcription != "fixture":
        raise NotImplementedError("Only the fixture transcription provider is wired in this stage")

    transcription = FixtureTranscriptionProvider().transcribe(media_path, config.language_hint)
    proposed = FixtureSegmentationProvider().segment(transcription, config.subtitle_rules)
    correction_provider = FixtureCorrectionProvider()
    tagging_provider = FixtureTaggingProvider()
    compliance_provider = FixtureComplianceProvider()
    reports: list[CardReport] = []
    final_cards: list[SubtitleCard] = []

    confidence_by_segment = {
        segment.segment_id: segment.confidence for segment in transcription.segments
    }
    for card in proposed:
        original = check_card(card, config.subtitle_rules)
        correction = None
        final_card = card
        if original.violations != [Violation.NONE]:
            correction = correction_provider.correct(card, original.model_dump(mode="json"))
            final_card = card.model_copy(update={"lines": correction.corrected_lines})
        final_check = check_card(final_card, config.subtitle_rules)
        verification = VerificationRecord(
            original=original,
            correction=correction,
            final=final_check,
            verified=final_check.violations == [Violation.NONE],
        )
        tagging = tagging_provider.tag(final_card, {})
        compliance = compliance_provider.analyze(final_card)
        reports.append(
            CardReport(
                card=final_card,
                verification=verification,
                tagging=tagging,
                compliance=compliance,
                transcription_confidence=min(
                    confidence_by_segment[source_id] for source_id in final_card.source_segment_ids
                ),
            )
        )
        final_cards.append(final_card)

    report = build_report(run_id or str(uuid4()), config.language_hint, reports)
    return PipelineResult(report=report, srt=render_srt(final_cards), vtt=render_vtt(final_cards))
