from kothon.config import SubtitleRules
from kothon.contracts import SubtitleCard, Violation
from kothon.verification.rules import check_card, check_cards, visible_char_count

RULES = SubtitleRules(
    max_chars_per_line=10,
    max_lines_per_card=2,
    min_duration_seconds=1,
    max_duration_seconds=5,
    max_reading_speed_cps=10,
)


def card(lines: list[str], start: float = 0, end: float = 2) -> SubtitleCard:
    return SubtitleCard(
        card_id="card-1",
        lines=lines,
        start=start,
        end=end,
        source_segment_ids=["segment-1"],
    )


def test_counts_bengali_and_latin_text_without_transliteration() -> None:
    text = "বাংলা code"
    assert visible_char_count(text) == len(text)


def test_compliant_card_has_only_none_violation() -> None:
    result = check_card(card(["বাংলা", "code"]), RULES)

    assert result.violations == [Violation.NONE]
    assert result.char_count_per_line == [5, 4]
    assert result.duration == 2


def test_card_reports_all_numeric_violations() -> None:
    result = check_card(card(["12345678901", "12345678901", "x"], end=0.5), RULES)

    assert result.violations == [
        Violation.MAX_CHARS,
        Violation.MAX_LINES,
        Violation.MIN_DURATION,
        Violation.MAX_CPS,
    ]
    assert result.line_count == 3
    assert result.reading_speed_cps > RULES.max_reading_speed_cps


def test_cards_detect_timeline_overlap_without_skipping_card_check() -> None:
    first = card(["ok"], start=0, end=3)
    second = card(["ok"], start=2, end=4).model_copy(update={"card_id": "card-2"})

    results = check_cards([first, second], RULES)

    assert results[0].violations == [Violation.NONE]
    assert results[1].violations == [Violation.TIMESTAMP_OVERLAP]
