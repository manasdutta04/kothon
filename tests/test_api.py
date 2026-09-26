from fastapi.testclient import TestClient

from kothon.api import RUNS, create_app


def test_health_and_fixture_run_api() -> None:
    RUNS.clear()
    client = TestClient(create_app())

    assert client.get("/api/health").json() == {"status": "ok"}
    response = client.post(
        "/api/runs",
        files={"file": ("sample.wav", b"fixture", "audio/wav")},
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
