from pathlib import Path

import httpx
import pytest

from kothon.providers.groq import GroqClient, GroqConfigurationError


def test_missing_groq_key_fails_without_network_call() -> None:
    client = GroqClient(api_key="", transcription_model="whisper")

    with pytest.raises(GroqConfigurationError, match="GROQ_API_KEY"):
        client.transcribe(Path("missing.wav"), "bn")


def test_structured_text_validates_provider_response() -> None:
    requested_path = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requested_path
        requested_path = request.url.path
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
    assert requested_path == "/openai/v1/chat/completions"


def test_structured_text_retries_transient_provider_failure() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok": true}'}}]},
        )

    client = GroqClient(
        api_key="test-key",
        text_model="text-model",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=1,
    )

    assert client.structured_text("system", {"value": 1}) == {"ok": True}
    assert attempts == 2
