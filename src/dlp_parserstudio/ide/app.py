"""FastAPI application for the DLP-ParserStudio web IDE."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dlp_parserstudio.ide.analysis import (
    _build_lr0_table,
    _detect_grammar_format,
    _ll1_conflict_to_dict,
    _lr_conflict_to_dict,
    analyze_source,
)
from dlp_parserstudio.mini_antlr.loader import MiniANTLRLoaderError, loads_mini_antlr
from dlp_parserstudio.parser.disambiguation import (
    analyze_disambiguation,
    auto_resolve_disambiguation,
)
from dlp_parserstudio.parser.lalr import build_lalr_table
from dlp_parserstudio.parser.ll1 import build_ll1_table
from dlp_parserstudio.parser.slr import build_slr_table
from dlp_parserstudio.parser.yapar_loader import YaparLoaderError, loads_yapar

STATIC_DIR = Path(__file__).with_name("static")


class AnalyzeRequest(BaseModel):
    yalex_text: str
    yapar_text: str
    input_text: str
    method: str = "SLR(1)"
    lexicon_text: str = ""


class DisambiguateRequest(BaseModel):
    yapar_text: str
    method: str = "SLR(1)"
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    parallel_branches: list[dict[str, Any]] = Field(default_factory=list)


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
            request.lexicon_text,
        )

    @app.post("/api/disambiguate")
    def disambiguate(request: DisambiguateRequest) -> dict[str, Any]:
        try:
            grammar = _load_grammar(request.yapar_text)
            conflicts = request.conflicts or _build_conflicts(grammar, request.method)
            return analyze_disambiguation(
                grammar,
                conflicts=conflicts,
                method=request.method,
                branch_results=request.parallel_branches,
            )
        except (YaparLoaderError, MiniANTLRLoaderError) as error:
            return _grammar_error_response(error)

    @app.post("/api/disambiguate/resolve")
    def resolve_disambiguation(request: DisambiguateRequest) -> dict[str, Any]:
        try:
            grammar = _load_grammar(request.yapar_text)
            conflicts = request.conflicts or _build_conflicts(grammar, request.method)
            return auto_resolve_disambiguation(
                grammar,
                conflicts=conflicts,
                method=request.method,
                branch_results=request.parallel_branches,
            )
        except (YaparLoaderError, MiniANTLRLoaderError) as error:
            return {
                **_grammar_error_response(error),
                "resolved": False,
                "resolved_yapar": "",
                "applied_suggestion": None,
                "limitations": "Primero debe existir una gramatica valida.",
            }

    return app


app = create_app()


def _load_grammar(yapar_text: str) -> Any:
    if _detect_grammar_format(yapar_text) == "antlr":
        return loads_mini_antlr(yapar_text).grammar
    return loads_yapar(yapar_text)


def _build_conflicts(grammar: Any, method: str) -> list[dict[str, Any]]:
    method_key = method.lower()

    try:
        if method_key in {"ll1", "ll(1)"}:
            return [_ll1_conflict_to_dict(conflict) for conflict in build_ll1_table(grammar).conflicts]
        if method_key in {"lr0", "lr(0)"}:
            return [_lr_conflict_to_dict(conflict) for conflict in _build_lr0_table(grammar).conflicts]
        if method_key in {"slr", "slr1", "slr(1)"}:
            return [_lr_conflict_to_dict(conflict) for conflict in build_slr_table(grammar).conflicts]
        if method_key in {"lalr", "lalr1", "lalr(1)"}:
            return [_lr_conflict_to_dict(conflict) for conflict in build_lalr_table(grammar).conflicts]
    except Exception:
        return []

    return []


def _grammar_error_response(error: Exception) -> dict[str, Any]:
    return {
        "has_suggestions": True,
        "summary": "La gramatica no se pudo cargar; revise primero la sintaxis.",
        "suggestions": [
            {
                "kind": "grammar_error",
                "title": "Error en la definicion de la gramatica",
                "problem": str(error),
                "explanation": (
                    "La desambiguacion necesita una gramatica valida para revisar "
                    "producciones, FIRST y conflictos."
                ),
                "recommended_method": "Corregir la gramatica YAPar/MiniANTLR y ejecutar de nuevo.",
                "suggested_grammar": "",
                "confidence": "high",
                "can_apply": False,
            }
        ],
    }


def run_server(host: str = "127.0.0.1", port: int = 8001, reload: bool = False) -> None:
    import uvicorn

    uvicorn.run(
        "dlp_parserstudio.ide.app:app",
        host=host,
        port=port,
        reload=reload,
    )
