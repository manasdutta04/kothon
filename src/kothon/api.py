"""Thin HTTP interface over the Kothon pipeline."""

import tempfile
from pathlib import Path
from typing import Annotated, Any, cast
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response

from kothon.config import load_config
from kothon.contracts import PipelineResult
from kothon.pipeline import run_pipeline

RUNS: dict[str, Any] = {}


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
    async def create_run(file: Annotated[UploadFile, File(...)]) -> dict[str, str]:
        run_id = str(uuid4())
        suffix = Path(file.filename or "upload.bin").suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
            temporary.write(await file.read())
            media_path = Path(temporary.name)
        try:
            result = run_pipeline(
                media_path,
                load_config(Path("config/default.yaml")),
                run_id=run_id,
            )
            RUNS[run_id] = {"status": "completed", "result": result}
        except Exception as exc:
            RUNS[run_id] = {"status": "failed", "error": str(exc)}
        finally:
            media_path.unlink(missing_ok=True)
        return {"run_id": run_id, "status": str(RUNS[run_id]["status"])}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        run = RUNS.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return {"run_id": run_id, "status": run["status"]}

    @app.get("/api/runs/{run_id}/result")
    def get_result(run_id: str) -> dict[str, Any]:
        run = RUNS.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if run["status"] != "completed":
            raise HTTPException(status_code=409, detail=run.get("error", "Run not completed"))
        result = cast(PipelineResult, run["result"])
        return result.report.model_dump(mode="json")

    @app.get("/api/runs/{run_id}/files/{file_type}")
    def get_file(run_id: str, file_type: str) -> Response:
        run = RUNS.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if run["status"] != "completed":
            raise HTTPException(status_code=409, detail="Run not completed")
        result = cast(PipelineResult, run["result"])
        if file_type == "srt":
            return PlainTextResponse(result.srt, media_type="application/x-subrip")
        if file_type == "vtt":
            return PlainTextResponse(result.vtt, media_type="text/vtt")
        if file_type == "json":
            return Response(result.report.model_dump_json(indent=2), media_type="application/json")
        raise HTTPException(status_code=404, detail="Unknown file type")

    return app


app = create_app()
