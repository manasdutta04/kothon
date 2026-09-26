from pathlib import Path

import httpx
import pytest

from kothon.providers.groq import GroqClient, GroqConfigurationError


def test_missing_groq_key_fails_without_network_call() -> None:
    client = GroqClient(api_key="", transcription_model="whisper")

    with pytest.raises(GroqConfigurationError, match="GROQ_API_KEY"):
        client.transcribe(Path("missing.wav"), "bn")


def test_structured_text_validates_provider_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok": true}'}}]},
        )

    transport = httpx.MockTransport(handler)
    client = GroqClient(
        api_key="test-key",
        text_model="text-model",
        client=httpx.Client(transport=transport),
    )

    assert client.structured_text("system", {"value": 1}) == {"ok": True}

