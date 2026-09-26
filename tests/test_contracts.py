import pytest
from pydantic import ValidationError

from kothon.contracts import TranscriptSegment


def test_transcript_segment_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        TranscriptSegment(
            segment_id="s1",
            text="hello",
            start=0,
            end=1,
            confidence=0.9,
            unexpected=True,
        )

