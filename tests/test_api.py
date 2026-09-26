import io
import wave

from fastapi.testclient import TestClient

from kothon.api import RUNS, create_app


def wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16_000)
        audio.writeframes(b"\x00\x00" * 16_000 * 7)
    return buffer.getvalue()


def test_health_and_fixture_run_api() -> None:
    RUNS.clear()
    client = TestClient(create_app())

    assert client.get("/api/health").json() == {"status": "ok"}
    response = client.post(
        "/api/runs",
        files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    assert client.get(f"/api/runs/{run_id}").json()["status"] == "completed"
    assert "WEBVTT" in client.get(f"/api/runs/{run_id}/files/vtt").text
    result = client.get(f"/api/runs/{run_id}/result").json()
    assert result["summary"]["total_cards"] == 3
    assert {key: len(value) for key, value in result["tracks"].items()} == {
        "bn": 3,
        "en": 3,
        "hi": 3,
    }
    assert result["tracks"]["en"][1] == ["He has an office meeting."]
    assert result["media_metadata"]["media_type"] == "audio/wav"
    events = client.get(f"/api/runs/{run_id}/events")
    assert events.status_code == 200
    assert [event["stage"] for event in events.json()] == [
        "transcription",
        "segmentation",
        "verification",
        "accessibility",
        "compliance",
        "translation",
        "assembly",
    ]


def test_api_rejects_malformed_media() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/runs",
        files={"file": ("broken.wav", b"not-a-wave", "audio/wav")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_media"


def test_fixture_result_reports_fixture_mode(monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    RUNS.clear()
    client = TestClient(create_app())

    response = client.post(
        "/api/runs",
        files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
    )

    run_id = response.json()["run_id"]
    assert client.get(f"/api/runs/{run_id}/result").json()["mode"] == "fixture"
