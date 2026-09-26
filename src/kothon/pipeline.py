"""Provider-independent Kothon pipeline orchestration."""

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from kothon.assembly.report import build_report
from kothon.assembly.subtitles import render_srt, render_vtt
from kothon.audio import extract_evidence
from kothon.config import KothonConfig
from kothon.contracts import (
    CardReport,
    PipelineResult,
    QCIssue,
    QCReport,
    SubtitleCard,
    TraceEvent,
    VerificationRecord,
    Violation,
)
from kothon.media import inspect_media, read_audio
from kothon.providers.fixtures import (
    FixtureComplianceProvider,
    FixtureCorrectionProvider,
    FixtureSegmentationProvider,
    FixtureTaggingProvider,
    FixtureTranscriptionProvider,
    FixtureTranslationProvider,
)
from kothon.providers.groq import GroqClient
from kothon.speech.alignment import align_segment_words
from kothon.speech.diarization import diarize
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
    media_metadata = inspect_media(media_path).model_copy(update={"path": media_path.name})
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
    trace: list[TraceEvent] = []

    def record_trace(
        stage: str,
        provider: str,
        model: str | None,
        payload: dict[str, object],
        started_at: float,
    ) -> None:
        trace.append(
            TraceEvent(
                event_id=f"trace-{len(trace) + 1:04d}",
                stage=stage,
                status="completed",
                provider=provider,
                model=model,
                recorded_at=datetime.now(UTC),
                duration_ms=(perf_counter() - started_at) * 1000,
                payload=payload,
            )
        )

    transcription_started = perf_counter()
    transcription = transcription_provider.transcribe(media_path, config.language_hint)
    record_trace(
        "transcription",
        config.providers.transcription,
        config.providers.transcription_model or None,
        {"segments": transcription.model_dump(mode="json")["segments"]},
        transcription_started,
    )
    segmentation_started = perf_counter()
    proposed = segmentation_provider.segment(transcription, config.subtitle_rules)
    record_trace(
        "segmentation",
        config.providers.segmentation,
        config.providers.text_model or None,
        {"cards": [card.model_dump(mode="json") for card in proposed]},
        segmentation_started,
    )
    audio = read_audio(media_path)
    audio_evidence = extract_evidence(audio)
    speaker_turns = diarize(transcription.segments, audio_evidence)
    reports: list[CardReport] = []
    final_cards: list[SubtitleCard] = []
    translation_provider = groq if groq is not None else FixtureTranslationProvider()
    translated: dict[str, list[str]] = {"en": [], "hi": []}
    issues: list[QCIssue] = []

    verification_started = perf_counter()
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
        compliance = compliance_provider.analyze(final_card)
        matching_turns = [
            turn for turn in speaker_turns
            if turn.start < final_card.end and turn.end > final_card.start
        ]
        source_segments = [
            segment
            for segment in transcription.segments
            if segment.segment_id in final_card.source_segment_ids
        ]
        aligned_words = [
            word
            for segment in source_segments
            for word in align_segment_words(segment, matching_turns)
        ]
        card_evidence = [
            item
            for item in audio_evidence
            if item.start < final_card.end and item.end > final_card.start
        ]
        tagging = tagging_provider.tag(
            final_card,
            {
                "audio_evidence": [item.model_dump(mode="json") for item in card_evidence],
                "speaker_turns": [item.model_dump(mode="json") for item in matching_turns],
            },
        )
        if matching_turns:
            tagging.speaker_label = matching_turns[0].speaker_id
            if matching_turns[0].confidence < 0.6:
                tagging.low_confidence = True
        elif tagging.speaker_label is None:
            tagging.speaker_label = "Speaker 1"
        if any(word.alignment_method == "duration_weighted_estimate" for word in aligned_words):
            issues.append(QCIssue(
                issue_id=f"qc-{final_card.card_id}-alignment",
                severity="low",
                score=30,
                category="estimated_alignment",
                cue_id=final_card.card_id,
                start=final_card.start,
                end=final_card.end,
                evidence="Word timestamps were estimated from the segment duration.",
                recommended_action="Review timing if the cue is near a shot or speaker change.",
                affected_tracks=["bn", "en", "hi"],
            ))
        supporting_audio = card_evidence
        if supporting_audio and max(item.speech_activity for item in supporting_audio) < 0.05:
            issues.append(QCIssue(
                issue_id=f"qc-{final_card.card_id}-silence",
                severity="critical",
                score=100,
                category="hallucination_over_silence",
                cue_id=final_card.card_id,
                start=final_card.start,
                end=final_card.end,
                evidence="No speech activity supports this cue window.",
                recommended_action="Listen to the source before approving the cue.",
                affected_tracks=["bn", "en", "hi"],
            ))
        if (
            supporting_audio
            and any(item.evidence_type == "music_candidate" for item in supporting_audio)
            and not any(item.evidence_type == "speech_activity" for item in supporting_audio)
        ):
            issues.append(QCIssue(
                issue_id=f"qc-{final_card.card_id}-music",
                severity="critical",
                score=95,
                category="hallucination_over_music",
                cue_id=final_card.card_id,
                start=final_card.start,
                end=final_card.end,
                evidence=(
                    "The cue overlaps audio classified as music candidate without speech activity."
                ),
                recommended_action=(
                    "Listen to the source and remove the cue unless speech is audible."
                ),
                affected_tracks=["bn", "en", "hi"],
            ))
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
                speaker_id=tagging.speaker_label,
                aligned_words=aligned_words,
                audio_evidence=card_evidence,
            )
        )
        final_cards.append(final_card)

    record_trace(
        "verification",
        config.providers.correction,
        config.providers.text_model or None,
        {"cards": [item.model_dump(mode="json") for item in reports]},
        verification_started,
    )
    record_trace(
        "accessibility",
        config.providers.tagging,
        config.providers.text_model or None,
        {"cards": [item.tagging.model_dump(mode="json") for item in reports if item.tagging]},
        verification_started,
    )
    record_trace(
        "compliance",
        config.providers.compliance,
        config.providers.text_model or None,
        {"cards": [item.compliance.model_dump(mode="json") for item in reports if item.compliance]},
        verification_started,
    )
    record_trace(
        "translation",
        "groq" if groq is not None else "fixture",
        config.providers.text_model or None,
        {"english_cues": len(translated["en"]), "hindi_cues": len(translated["hi"])},
        verification_started,
    )

    assembly_started = perf_counter()
    report = build_report(run_id or str(uuid4()), config.language_hint, reports)
    report = report.model_copy(update={"media_metadata": media_metadata})
    speaker_labels = [
        item.tagging.speaker_label if item.tagging else "Speaker 1" for item in reports
    ]
    bengali_cards: list[SubtitleCard] = []
    for index, card in enumerate(final_cards):
        card_tagging = reports[index].tagging
        tags = card_tagging.non_speech_tags if card_tagging is not None else []
        bengali_cards.append(
            card.model_copy(
                update={
                    "lines": [
                        " ".join([f"[{speaker_labels[index]}]"] + tags + [line])
                        for line in card.lines
                    ]
                }
            )
        )
    english_cards = [
        card.model_copy(update={"lines": [translated["en"][index]]})
        for index, card in enumerate(final_cards)
    ]
    hindi_cards = [
        card.model_copy(update={"lines": [translated["hi"][index]]})
        for index, card in enumerate(final_cards)
    ]
    for card in bengali_cards:
        presentation_check = check_card(card, config.subtitle_rules)
        if presentation_check.violations != [Violation.NONE]:
            issues.append(QCIssue(
                issue_id=f"qc-{card.card_id}-presentation",
                severity="high",
                score=75,
                category="presentation_after_tagging",
                cue_id=card.card_id,
                start=card.start,
                end=card.end,
                evidence=f"Final Bengali CC has violations after speaker/sound tags: "
                f"{[item.value for item in presentation_check.violations]}.",
                recommended_action="Rebreak the final CC while keeping evidence-backed tags.",
                affected_tracks=["bn"],
            ))
    qc = QCReport(
        issues=issues,
        review_queue=sorted(issues, key=lambda item: item.score, reverse=True),
    )
    record_trace(
        "assembly",
        "local",
        None,
        {
            "bengali_cues": len(bengali_cards),
            "english_cues": len(english_cards),
            "hindi_cues": len(hindi_cards),
            "qc_issues": len(issues),
        },
        assembly_started,
    )
    return PipelineResult(
        report=report,
        srt=render_srt(english_cards),
        vtt=render_vtt(bengali_cards),
        bengali_vtt=render_vtt(bengali_cards),
        english_srt=render_srt(english_cards),
        hindi_srt=render_srt(hindi_cards),
        bengali_lines=[card.lines for card in bengali_cards],
        english_lines=[[line] for line in translated["en"]],
        hindi_lines=[[line] for line in translated["hi"]],
        qc_report=qc.model_dump(mode="json"),
        trace=trace,
    )
