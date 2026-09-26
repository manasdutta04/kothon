"""Small, schema-validating Groq HTTP client.

The client intentionally uses HTTPX rather than a model SDK so the core
package remains easy to test and the provider's wire contract is explicit.
"""

import json
import mimetypes
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

from kothon.config import SubtitleRules
from kothon.contracts import (
    ComplianceResult,
    CorrectionResult,
    SubtitleCard,
    TaggingResult,
    Transcript,
    TranslatedCue,
)
from kothon.media import read_audio, write_audio_chunks


class GroqConfigurationError(RuntimeError):
    """Raised when Groq is selected without safe configuration."""


class GroqClient:
    """Groq provider adapter with no secret values in error messages."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        transcription_model: str | None = None,
        text_model: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        request_interval_seconds: float | None = None,
        client: httpx.Client | None = None,
        base_url: str = "https://api.groq.com/openai/v1",
    ) -> None:
        self.api_key: str = (
            os.getenv("GROQ_API_KEY", "") if api_key is None else api_key
        )
        self.transcription_model: str = (
            os.getenv("GROQ_TRANSCRIPTION_MODEL", "")
            if transcription_model is None
            else transcription_model
        )
        self.text_model: str = (
            os.getenv("GROQ_TEXT_MODEL", "") if text_model is None else text_model
        )
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=timeout)
        self.max_retries = max_retries
        self.request_interval_seconds = (
            float(os.getenv("GROQ_MIN_REQUEST_INTERVAL_SECONDS", "3.1"))
            if request_interval_seconds is None
            else request_interval_seconds
        )
        self._last_request_at = 0.0

    def _require(self, model: str) -> None:
        if not self.api_key:
            raise GroqConfigurationError("GROQ_API_KEY is not configured")
        if not model:
            raise GroqConfigurationError("A Groq model is not configured")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _json_request(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._request_with_retries(
            endpoint,
            headers={**self._headers(), "Content-Type": "application/json"},
            json=payload,
        )
        if response.is_error:
            raise RuntimeError(f"Groq request failed with HTTP {response.status_code}")
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("Groq returned an invalid JSON object")
        return data

    def _request_with_retries(self, endpoint: str, **kwargs: Any) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                elapsed = time.monotonic() - self._last_request_at
                wait_for_interval = self.request_interval_seconds - elapsed
                if wait_for_interval > 0:
                    time.sleep(wait_for_interval)
                response = self.client.post(
                    f"{self.base_url}/{endpoint.lstrip('/')}",
                    **kwargs,
                )
                self._last_request_at = time.monotonic()
                if response.status_code == 429:
                    if attempt < self.max_retries:
                        time.sleep(
                            max(
                                self._retry_after_seconds(response),
                                self.request_interval_seconds,
                            )
                        )
                        continue
                    raise RuntimeError(
                        "Groq rate limit reached (HTTP 429). Wait for the free-tier quota "
                        "to reset, then retry the run."
                    )
                if response.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(max(1.0, self.request_interval_seconds) * (2**attempt))
                    continue
                return response
            except httpx.TransportError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(0.2 * (2**attempt))
                    continue
                raise RuntimeError("Groq request failed due to a transport error") from exc
        if last_error is not None:
            raise RuntimeError("Groq request failed due to a transport error") from last_error
        raise RuntimeError("Groq request failed without a response")

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float:
        value = response.headers.get("retry-after", "")
        try:
            return max(0.0, float(value))
        except ValueError:
            return 3.1

    def transcribe(self, media_path: Path, language_hint: str) -> Transcript:
        self._require(self.transcription_model)
        # Groq's speech endpoint has a per-request upload ceiling.  Decode
        # locally and stitch short timestamped requests for long media so a
        # 150 MB video remains usable without local model weights.
        if media_path.stat().st_size > 24_000_000:
            audio = read_audio(media_path)
            with tempfile.TemporaryDirectory(prefix="kothon-groq-") as directory:
                chunks = write_audio_chunks(audio, Path(directory))
                transcripts = [
                    self._transcribe_single(chunk_path, language_hint, offset)
                    for chunk_path, offset in chunks
                ]
            return self._merge_transcripts(transcripts)
        return self._transcribe_single(media_path, language_hint, 0.0)

    def _transcribe_single(
        self, media_path: Path, language_hint: str, offset: float
    ) -> Transcript:
        with media_path.open("rb") as media:
            response = self._request_with_retries(
                "audio/transcriptions",
                headers=self._headers(),
                data={
                    "model": self.transcription_model,
                    "language": language_hint,
                    "response_format": "verbose_json",
                    "timestamp_granularities[]": ["segment", "word"],
                },
                files={
                    "file": (
                        media_path.name,
                        media,
                        mimetypes.guess_type(media_path.name)[0] or "application/octet-stream",
                    )
                },
            )
        if response.is_error:
            raise RuntimeError(f"Groq transcription failed with HTTP {response.status_code}")
        raw = response.json()
        if not isinstance(raw, dict):
            raise RuntimeError("Groq returned an invalid transcription object")
        segments = raw.get("segments", [])
        if not isinstance(segments, list):
            raise RuntimeError("Groq transcription did not contain a segment list")
        normalized = []
        for index, segment in enumerate(segments):
            if not isinstance(segment, dict):
                raise RuntimeError("Groq returned an invalid transcription segment")
            text = str(segment.get("text", "")).strip()
            words = segment.get("words", [])
            confidence = float(segment.get("avg_logprob") or 0.0)
            confidence = max(0.0, min(1.0, (confidence + 1.0)))
            normalized.append(
                {
                    "segment_id": f"segment-{index + 1:04d}",
                    "text": text,
                    "start": float(segment.get("start", 0)) + offset,
                    "end": float(segment.get("end", 0)) + offset,
                    "confidence": float(segment.get("confidence") or confidence),
                    "contains_code_mixing": any(
                        any("a" <= char.lower() <= "z" for char in str(word.get("word", "")))
                        for word in words if isinstance(word, dict)
                    ),
                    "words": [
                        {
                            "text": str(word.get("word", "")).strip(),
                            "start": (
                                float(word.get("start") or segment.get("start") or 0.0)
                                + offset
                            ),
                            "end": (
                                float(word.get("end") or segment.get("end") or 0.0)
                                + offset
                            ),
                            "alignment_method": "provider_word_timestamp",
                            "confidence": float(word.get("confidence") or 0.8),
                        }
                        for word in words
                        if isinstance(word, dict) and str(word.get("word", "")).strip()
                    ],
                }
            )
        return Transcript.model_validate({"segments": normalized})

    @staticmethod
    def _merge_transcripts(transcripts: list[Transcript]) -> Transcript:
        merged = []
        seen: set[tuple[str, int]] = set()
        for transcript in transcripts:
            for segment in transcript.segments:
                key = (" ".join(segment.text.split()).casefold(), round(segment.start * 10))
                if not segment.text or key in seen:
                    continue
                seen.add(key)
                merged.append(segment)
        merged.sort(key=lambda segment: (segment.start, segment.end))
        normalized = [
            segment.model_copy(update={"segment_id": f"segment-{index:04d}"})
            for index, segment in enumerate(merged, start=1)
        ]
        return Transcript(segments=normalized)

    def structured_text(self, system_prompt: str, user_payload: object) -> dict[str, Any]:
        self._require(self.text_model)
        raw = self._json_request(
            "chat/completions",
            {
                "model": self.text_model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(user_payload, ensure_ascii=False),
                    },
                ],
            },
        )
        choices = raw.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("Groq returned no chat choices")
        content = (
            choices[0].get("message", {}).get("content")
            if isinstance(choices[0], dict)
            else None
        )
        if not isinstance(content, str):
            raise RuntimeError("Groq returned no structured message content")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Groq returned invalid structured JSON") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("Groq structured response was not a JSON object")
        return parsed

    def segment(self, transcript: Transcript, rules: SubtitleRules) -> list[SubtitleCard]:
        raw = self.structured_text(
            "Return subtitle cards as strict JSON.",
            {"transcript": transcript.model_dump(), "rules": rules.model_dump()},
        )
        return [SubtitleCard.model_validate(item) for item in raw.get("cards", [])]

    def correct(self, card: SubtitleCard, failures: object) -> CorrectionResult:
        raw = self.structured_text(
            "Return a strict correction JSON object.",
            {"card": card.model_dump(), "failures": failures},
        )
        return CorrectionResult.model_validate(raw)

    def tag(self, card: SubtitleCard, features: object) -> TaggingResult:
        raw = self.structured_text(
            "Return strict accessibility tagging JSON.",
            {"card": card.model_dump(), "features": features},
        )
        return TaggingResult.model_validate(raw)

    def analyze(self, card: SubtitleCard) -> ComplianceResult:
        raw = self.structured_text(
            "Return strict sensitivity analysis JSON.",
            {"card": card.model_dump()},
        )
        return ComplianceResult.model_validate(raw)

    def translate(self, card: SubtitleCard, language: str) -> TranslatedCue:
        raw = self.structured_text(
            "Translate this cue and return strict JSON with cue_id, language, lines, "
            "source_cue_id, and translation_confidence.",
            {"card": card.model_dump(), "target_language": language},
        )
        translated = TranslatedCue.model_validate(raw)
        if translated.cue_id != card.card_id or translated.source_cue_id != card.card_id:
            raise RuntimeError("Groq translation changed the source cue ID")
        if translated.language != language:
            raise RuntimeError("Groq translation returned the wrong target language")
        return translated
