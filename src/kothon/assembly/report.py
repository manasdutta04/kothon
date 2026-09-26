"""Serialization and summary helpers for pipeline reports."""

import json
from pathlib import Path

from kothon.contracts import CardReport, PipelineReport, PipelineSummary, Violation


def summarize(cards: list[CardReport]) -> PipelineSummary:
    """Compute summary counts from card-level evidence."""
    return PipelineSummary(
        total_cards=len(cards),
        cards_corrected=sum(
            card.verification is not None and card.verification.correction is not None
            for card in cards
        ),
        cards_with_unresolved_violations=sum(
            card.verification is not None
            and any(v != Violation.NONE for v in card.verification.final.violations)
            for card in cards
        ),
        cards_with_sensitivity_flags=sum(
            card.compliance is not None and bool(card.compliance.flags) for card in cards
        ),
    )


def build_report(run_id: str, language_hint: str, cards: list[CardReport]) -> PipelineReport:
    return PipelineReport(
        run_id=run_id,
        language_hint=language_hint,
        cards=cards,
        summary=summarize(cards),
    )


def write_report(report: PipelineReport, path: Path) -> None:
    path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

