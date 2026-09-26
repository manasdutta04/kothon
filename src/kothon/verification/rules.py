"""Deterministic checks for subtitle engineering rules."""

from collections.abc import Iterable

from kothon.config import SubtitleRules
from kothon.contracts import RuleCheckResult, SubtitleCard, Violation


def visible_char_count(text: str) -> int:
    """Count visible subtitle characters, preserving mixed-script Unicode text.

    Spaces are part of the displayed subtitle and therefore count toward line
    length and reading speed. Newline characters are excluded because cards
    store lines separately and should never contain embedded line breaks.
    """
    return len(text.replace("\r", "").replace("\n", ""))


def _duration(card: SubtitleCard) -> float:
    return card.end - card.start


def _reading_speed(card: SubtitleCard, duration: float) -> float:
    total_characters = sum(visible_char_count(line) for line in card.lines)
    return total_characters / duration if duration > 0 else float("inf")


def check_card(card: SubtitleCard, rules: SubtitleRules) -> RuleCheckResult:
    """Check one card and return all violated rules with numeric evidence."""
    counts = [visible_char_count(line) for line in card.lines]
    duration = _duration(card)
    reading_speed = _reading_speed(card, duration)
    violations: list[Violation] = []

    if any(count > rules.max_chars_per_line for count in counts):
        violations.append(Violation.MAX_CHARS)
    if len(card.lines) > rules.max_lines_per_card:
        violations.append(Violation.MAX_LINES)
    if duration < rules.min_duration_seconds:
        violations.append(Violation.MIN_DURATION)
    if duration > rules.max_duration_seconds:
        violations.append(Violation.MAX_DURATION)
    if reading_speed > rules.max_reading_speed_cps:
        violations.append(Violation.MAX_CPS)

    return RuleCheckResult(
        card_id=card.card_id,
        char_count_per_line=counts,
        line_count=len(card.lines),
        duration=duration,
        reading_speed_cps=reading_speed,
        violations=violations or [Violation.NONE],
    )


def check_cards(cards: Iterable[SubtitleCard], rules: SubtitleRules) -> list[RuleCheckResult]:
    """Check cards in input order and additionally reject invalid timelines."""
    results: list[RuleCheckResult] = []
    previous_end = -1.0
    for card in cards:
        result = check_card(card, rules)
        if card.start < previous_end:
            result.violations = [
                *[v for v in result.violations if v != Violation.NONE],
                Violation.TIMESTAMP_OVERLAP,
            ]
        results.append(result)
        previous_end = max(previous_end, card.end)
    return results
