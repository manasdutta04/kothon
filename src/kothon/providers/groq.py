"""Small, schema-validating Groq HTTP client.

The client intentionally uses HTTPX rather than a model SDK so the core
package remains easy to test and the provider's wire contract is explicit.
"""

import json
import os
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
        client: httpx.Client | None = None,
        base_url: str = "https://api.groq.com/openai",
    ) -> None:
        self.api_key: str = api_key or os.getenv("GROQ_API_KEY") or ""
        self.transcription_model: str = (
            transcription_model or os.getenv("GROQ_TRANSCRIPTION_MODEL") or ""
        )
        self.text_model: str = text_model or os.getenv("GROQ_TEXT_MODEL") or ""
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=timeout)

    def _require(self, model: str) -> None:
        if not self.api_key:
            raise GroqConfigurationError("GROQ_API_KEY is not configured")
        if not model:
            raise GroqConfigurationError("A Groq model is not configured")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _json_request(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(
            f"{self.base_url}/{endpoint.lstrip('/')}",
            headers={**self._headers(), "Content-Type": "application/json"},
            json=payload,
        )
        if response.is_error:
            raise RuntimeError(f"Groq request failed with HTTP {response.status_code}")
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("Groq returned an invalid JSON object")
        return data

    def transcribe(self, media_path: Path, language_hint: str) -> Transcript:
        self._require(self.transcription_model)
        with media_path.open("rb") as media:
            response = self.client.post(
                f"{self.base_url}/audio/transcriptions",
                headers=self._headers(),
                data={
                    "model": self.transcription_model,
                    "language": language_hint,
                    "response_format": "verbose_json",
                    "timestamp_granularities[]": ["segment", "word"],
                },
                files={"file": (media_path.name, media, "application/octet-stream")},
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
            confidence = float(segment.get("avg_logprob", 0.0))
            confidence = max(0.0, min(1.0, (confidence + 1.0)))
            normalized.append(
                {
                    "segment_id": f"segment-{index + 1:04d}",
                    "text": text,
                    "start": float(segment.get("start", 0)),
                    "end": float(segment.get("end", 0)),
                    "confidence": float(segment.get("confidence", confidence)),
                    "contains_code_mixing": any(
                        any("a" <= char.lower() <= "z" for char in str(word.get("word", "")))
                        for word in words if isinstance(word, dict)
                    ),
                    "words": [
                        {
                            "text": str(word.get("word", "")).strip(),
                            "start": float(word.get("start") or segment.get("start") or 0.0),
                            "end": float(word.get("end") or segment.get("end") or 0.0),
                            "alignment_method": "provider_word_timestamp",
                            "confidence": float(word.get("confidence", 0.8)),
                        }
                        for word in words
                        if isinstance(word, dict) and str(word.get("word", "")).strip()
                    ],
                }
            )
        return Transcript.model_validate({"segments": normalized})

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
        return TranslatedCue.model_validate(raw)
