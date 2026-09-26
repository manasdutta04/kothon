"""Thin HTTP interface over the Kothon pipeline."""

import json
import os
import tempfile
from pathlib import Path
from typing import Annotated, Any, cast
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from kothon.config import KothonConfig, ProviderConfig, load_runtime_config
from kothon.contracts import PipelineResult, TraceEvent
from kothon.media import MediaError, inspect_media
from kothon.pipeline import run_pipeline

RUNS: dict[str, Any] = {}


def _execute_run(run_id: str, media_path: Path) -> None:
    RUNS[run_id]["status"] = "running"

    def receive_event(event: TraceEvent) -> None:
        RUNS[run_id].setdefault("events", []).append(event)

    try:
        config = runtime_config()
        result = run_pipeline(
            media_path,
            config,
            run_id=run_id,
            event_sink=receive_event,
        )
        RUNS[run_id] = {
            "status": "completed",
            "result": result,
            "events": result.trace,
            "mode": "groq" if "groq" in config.providers.model_dump().values() else "fixture",
        }
    except Exception as exc:
        if os.getenv("KOTHON_DEMO_FALLBACK_FIXTURE", "false").lower() == "true":
            try:
                fallback_config = config.model_copy(update={"providers": ProviderConfig()})
                result = run_pipeline(media_path, fallback_config, run_id=run_id)
                RUNS[run_id] = {
                    "status": "completed",
                    "result": result,
                    "events": result.trace,
                    "mode": "fixture-fallback",
                    "warning": f"Groq was unavailable; fixture mode was used: {exc}",
                }
            except Exception as fallback_exc:
                RUNS[run_id]["status"] = "failed"
                RUNS[run_id]["error"] = f"Groq failed: {exc}; fallback failed: {fallback_exc}"
        else:
            RUNS[run_id]["status"] = "failed"
            RUNS[run_id]["error"] = str(exc)
    finally:
        media_path.unlink(missing_ok=True)


def runtime_config() -> KothonConfig:
    return load_runtime_config()


def create_app() -> FastAPI:
    app = FastAPI(title="Kothon API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/providers")
    def providers() -> dict[str, list[str]]:
        return {"available": ["fixture", "groq"]}

    @app.post("/api/runs")
    async def create_run(
        background_tasks: BackgroundTasks,
        file: Annotated[UploadFile, File(...)],
    ) -> dict[str, str]:
        run_id = str(uuid4())
        suffix = Path(file.filename or "upload.bin").suffix
        maximum_bytes = int(os.getenv("KOTHON_MAX_UPLOAD_BYTES", str(500 * 1024 * 1024)))
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
            total_bytes = 0
            while block := await file.read(1024 * 1024):
                total_bytes += len(block)
                if total_bytes > maximum_bytes:
                    temporary.close()
                    Path(temporary.name).unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail={
                            "code": "upload_too_large",
                            "message": f"Upload exceeds the {maximum_bytes} byte limit.",
                        },
                    )
                temporary.write(block)
            media_path = Path(temporary.name)
        try:
            if not media_path.is_file():
                raise MediaError("Uploaded media could not be stored")
            inspect_media(media_path)
        except MediaError as exc:
            media_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid_media", "message": str(exc)},
            ) from exc
        RUNS[run_id] = {"status": "queued", "events": [], "media_path": str(media_path)}
        background_tasks.add_task(_execute_run, run_id, media_path)
        return {"run_id": run_id, "status": "queued"}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        run = RUNS.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return {
            "run_id": run_id,
            "status": run["status"],
            "error": run.get("error"),
            "events": [event.model_dump(mode="json") for event in run.get("events", [])],
        }

    @app.get("/api/runs/{run_id}/result")
    def get_result(run_id: str) -> dict[str, Any]:
        run = RUNS.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if run["status"] != "completed":
            raise HTTPException(status_code=409, detail=run.get("error", "Run not completed"))
        result = cast(PipelineResult, run["result"])
        payload = result.report.model_dump(mode="json")
        active_config = runtime_config()
        default_mode = (
            "groq" if "groq" in active_config.providers.model_dump().values() else "fixture"
        )
        payload["mode"] = run.get("mode", default_mode)
        payload["warning"] = run.get("warning")
        payload["qc_report"] = result.qc_report
        payload["tracks"] = {
            "bn": result.bengali_lines or [card.card.lines for card in result.report.cards],
            "en": result.english_lines,
            "hi": result.hindi_lines,
        }
        payload["events"] = [event.model_dump(mode="json") for event in result.trace]
        return payload

    @app.get("/api/runs/{run_id}/events")
    def get_events(run_id: str) -> list[dict[str, Any]]:
        run = RUNS.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if run["status"] != "completed":
            raise HTTPException(status_code=409, detail=run.get("error", "Run not completed"))
        events = run.get("events", [])
        return [event.model_dump(mode="json") for event in events]

    @app.get("/api/runs/{run_id}/files/{file_type}")
    def get_file(run_id: str, file_type: str) -> Response:
        run = RUNS.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if run["status"] != "completed":
            raise HTTPException(status_code=409, detail="Run not completed")
        result = cast(PipelineResult, run["result"])
        if file_type == "srt":
            return PlainTextResponse(
                result.english_srt or result.srt,
                media_type="application/x-subrip",
            )
        if file_type == "vtt":
            return PlainTextResponse(result.bengali_vtt or result.vtt, media_type="text/vtt")
        if file_type == "bengali-vtt":
            return PlainTextResponse(result.bengali_vtt, media_type="text/vtt")
        if file_type == "english-srt":
            return PlainTextResponse(result.english_srt, media_type="application/x-subrip")
        if file_type == "hindi-srt":
            return PlainTextResponse(result.hindi_srt, media_type="application/x-subrip")
        if file_type == "qc-json":
            return Response(
                json.dumps(result.qc_report, ensure_ascii=False, indent=2),
                media_type="application/json",
            )
        if file_type == "json":
            return Response(result.report.model_dump_json(indent=2), media_type="application/json")
        raise HTTPException(status_code=404, detail="Unknown file type")

    frontend_dist = Path("frontend/dist")
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    return app


app = create_app()
