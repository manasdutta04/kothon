"""Provider-independent Kothon pipeline orchestration."""

from pathlib import Path
from uuid import uuid4

from kothon.assembly.report import build_report
from kothon.assembly.subtitles import render_srt, render_vtt
from kothon.config import KothonConfig
from kothon.contracts import (
    CardReport,
    PipelineResult,
    QCIssue,
    QCReport,
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
    FixtureTranslationProvider,
)
from kothon.providers.groq import GroqClient
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
    provider_names = config.providers.model_dump()
    groq_needed = "groq" in provider_names.values()
    groq = (
        GroqClient(
            transcription_model=config.providers.transcription_model,
            text_model=config.providers.text_model,
            timeout=config.runtime.request_timeout_seconds,
        )
        if groq_needed
        else None
    )
    transcription_provider = (
        groq
        if config.providers.transcription == "groq" and groq is not None
        else FixtureTranscriptionProvider()
    )
    segmentation_provider = (
        groq
        if config.providers.segmentation == "groq" and groq is not None
        else FixtureSegmentationProvider()
    )
    correction_provider = (
        groq
        if config.providers.correction == "groq" and groq is not None
        else FixtureCorrectionProvider()
    )
    tagging_provider = (
        groq
        if config.providers.tagging == "groq" and groq is not None
        else FixtureTaggingProvider()
    )
    compliance_provider = (
        groq
        if config.providers.compliance == "groq" and groq is not None
        else FixtureComplianceProvider()
    )
    transcription = transcription_provider.transcribe(media_path, config.language_hint)
    proposed = segmentation_provider.segment(transcription, config.subtitle_rules)
    reports: list[CardReport] = []
    final_cards: list[SubtitleCard] = []
    translation_provider = groq if groq is not None else FixtureTranslationProvider()
    translated: dict[str, list[str]] = {"en": [], "hi": []}
    issues: list[QCIssue] = []

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
        if tagging.speaker_label is None:
            tagging.speaker_label = "Speaker 1"
        if original.reading_speed_cps > config.subtitle_rules.max_reading_speed_cps:
            issues.append(QCIssue(
                issue_id=f"qc-{final_card.card_id}-cps", severity="medium", score=60,
                category="cps", cue_id=final_card.card_id, start=final_card.start,
                end=final_card.end, evidence=f"Measured {original.reading_speed_cps:.2f} CPS.",
                recommended_action="Review line breaks or timing.",
                affected_tracks=["bn", "en", "hi"],
            ))
        for language in translated:
            translated[language].append(
                translation_provider.translate(final_card, language).lines[0]
            )
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
    speaker_labels = [
        item.tagging.speaker_label if item.tagging else "Speaker 1" for item in reports
    ]
    bengali_cards = [
        card.model_copy(
            update={"lines": [f"[{speaker_labels[index]}] {line}" for line in card.lines]}
        )
        for index, card in enumerate(final_cards)
    ]
    english_cards = [
        card.model_copy(update={"lines": [translated["en"][index]]})
        for index, card in enumerate(final_cards)
    ]
    hindi_cards = [
        card.model_copy(update={"lines": [translated["hi"][index]]})
        for index, card in enumerate(final_cards)
    ]
    qc = QCReport(
        issues=issues,
        review_queue=sorted(issues, key=lambda item: item.score, reverse=True),
    )
    return PipelineResult(
        report=report,
        srt=render_srt(english_cards),
        vtt=render_vtt(bengali_cards),
        bengali_vtt=render_vtt(bengali_cards),
        english_srt=render_srt(english_cards),
        hindi_srt=render_srt(hindi_cards),
        english_lines=[[line] for line in translated["en"]],
        hindi_lines=[[line] for line in translated["hi"]],
        qc_report=qc.model_dump(mode="json"),
    )
