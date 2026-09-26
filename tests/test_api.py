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
    assert client.get(f"/api/runs/{run_id}/result").json()["summary"]["total_cards"] == 3
