from pathlib import Path

from kothon.assembly.report import build_report, write_report
from kothon.assembly.subtitles import render_srt, render_vtt
from kothon.contracts import SubtitleCard


def cards() -> list[SubtitleCard]:
    return [
        SubtitleCard(
            card_id="card-1",
            lines=["বাংলা code"],
            start=0,
            end=2.5,
            source_segment_ids=["segment-1"],
        )
    ]


def test_srt_contains_standard_timestamps() -> None:
    rendered = render_srt(cards())

    assert rendered == "1\n00:00:00,000 --> 00:00:02,500\nবাংলা code\n"


def test_vtt_contains_header_and_dot_milliseconds() -> None:
    rendered = render_vtt(cards())

    assert rendered == "WEBVTT\n\n00:00:00.000 --> 00:00:02.500\nবাংলা code\n"


def test_report_summary_and_unicode_json(tmp_path: Path) -> None:
    report = build_report("run-1", "bn", [])
    target = tmp_path / "report.json"
    write_report(report, target)

    assert report.summary.total_cards == 0
    assert "run-1" in target.read_text(encoding="utf-8")

