"""FastAPI application for the DLP-ParserStudio web IDE."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from dlp_parserstudio.ide.analysis import analyze_source

STATIC_DIR = Path(__file__).with_name("static")


class AnalyzeRequest(BaseModel):
    yalex_text: str
    yapar_text: str
    input_text: str
    method: str = "SLR(1)"


def create_app() -> FastAPI:
    app = FastAPI(title="DLP-ParserStudio IDE")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.post("/api/analyze")
    def analyze(request: AnalyzeRequest) -> dict[str, Any]:
        return analyze_source(
            request.yalex_text,
            request.yapar_text,
            request.input_text,
            request.method,
        )

    return app


app = create_app()


def run_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    import uvicorn

    uvicorn.run(
        "dlp_parserstudio.ide.app:app",
        host=host,
        port=port,
        reload=reload,
    )
