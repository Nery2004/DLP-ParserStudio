from pathlib import Path

import pytest

from dlp_parserstudio.ide.app import create_app
from dlp_parserstudio.ide.analysis import analyze_source, loads_yalex


YALEX = r"""
NUMBER [0-9]+
PLUS \+
WS [ \t\r\n]+ skip
"""

YAPAR = """
%token NUMBER PLUS
%ignore WS
%start expr

%%
expr : NUMBER PLUS NUMBER ;
"""


def test_ide_analysis_returns_tokens_steps_and_tree() -> None:
    result = analyze_source(YALEX, YAPAR, "12 + 7", "SLR(1)")

    assert result["accepted"]
    assert result["errors"] == []
    assert [token["type"] for token in result["tokens"]] == ["NUMBER", "PLUS", "NUMBER"]
    assert result["first"]["expr"] == ["NUMBER"]
    assert result["follow"]["expr"] == ["$"]
    assert result["tables"]["action"]
    assert result["tables"]["goto"]
    assert result["steps"][-1]["action"] == "accept"
    assert result["syntax_tree"]["json"]["symbol"] == "expr"


@pytest.mark.parametrize("method", ["LL(1)", "LR(0)", "SLR(1)", "LALR(1)"])
def test_ide_analysis_supports_all_methods(method: str) -> None:
    result = analyze_source(YALEX, YAPAR, "12 + 7", method)

    assert result["accepted"]
    assert result["errors"] == []
    assert result["syntax_tree"] is not None


def test_ide_analysis_detects_mini_antlr_grammar() -> None:
    grammar = Path("examples/calc.mini.g4").read_text(encoding="utf-8")
    result = analyze_source("", grammar, "12 + 7", "SLR(1)")

    assert result["accepted"]
    assert result["format_detected"] == "antlr"
    assert [token["type"] for token in result["tokens"]] == ["NUMBER", "PLUS", "NUMBER"]


def test_ide_analysis_builds_translation_from_lexicon_text() -> None:
    result = analyze_source(
        YALEX,
        YAPAR,
        "12 + 7",
        "SLR(1)",
        "original\ttraduccion\n12\tdoce\n+\tmas\n7\tsiete\n",
    )

    assert result["translation"]["original"] == "12 + 7"
    assert result["translation"]["translated"] == "doce mas siete"
    assert result["translation"]["token_map"][1] == {
        "original": "+",
        "translated": "mas",
        "type": "PLUS",
    }


def test_ide_analysis_reports_lexical_error_with_location() -> None:
    result = analyze_source(YALEX, YAPAR, "12 ? 7", "SLR(1)")

    assert not result["accepted"]
    assert result["errors"][0]["source"] == "lexer"
    assert result["errors"][0]["line"] == 1
    assert result["errors"][0]["column"] == 4
    assert result["errors"][0]["token"] == "?"


def test_ide_analysis_reports_multiple_lexical_errors() -> None:
    result = analyze_source(YALEX, YAPAR, "12 ? + @ 7", "SLR(1)")

    lexical_errors = [error for error in result["errors"] if error["source"] == "lexer"]
    assert [error["token"] for error in lexical_errors] == ["?", "@"]
    assert [error["column"] for error in lexical_errors] == [4, 8]


def test_ide_analysis_reports_multiple_parser_errors_when_recoverable() -> None:
    result = analyze_source(YALEX, YAPAR, "12 7 8", "SLR(1)")

    parser_errors = [error for error in result["errors"] if error["source"] == "parser"]
    assert len(parser_errors) >= 2
    assert [error["token"] for error in parser_errors[:2]] == ["NUMBER", "NUMBER"]


def test_ide_lalr_includes_lr0_lr1_and_merged_lalr_automata() -> None:
    result = analyze_source(YALEX, YAPAR, "12 + 7", "LALR(1)")

    assert result["lr0_automaton"]["kind"] == "LR(0)"
    assert result["lr1_automaton"]["kind"] == "LR(1) canonico"
    assert result["lalr_automaton"]["kind"] == "LALR(1) fusionado por nucleo"
    assert "digraph" in result["lr1_automaton"]["dot"]
    assert "digraph" in result["lalr_automaton"]["dot"]


def test_ide_tables_explain_reduction_sources() -> None:
    lr0 = analyze_source(YALEX, YAPAR, "12 + 7", "LR(0)")
    slr = analyze_source(YALEX, YAPAR, "12 + 7", "SLR(1)")
    lalr = analyze_source(YALEX, YAPAR, "12 + 7", "LALR(1)")

    assert lr0["tables"]["reductions"]
    assert slr["tables"]["reductions"]
    assert lalr["tables"]["reductions"]
    assert {entry["source"] for entry in lr0["tables"]["reductions"]} == {
        "LR(0): todos los terminales"
    }
    assert {entry["source"] for entry in slr["tables"]["reductions"]} == {
        "SLR(1): FOLLOW global del LHS"
    }
    assert {entry["source"] for entry in lalr["tables"]["reductions"]} == {
        "LALR(1): lookahead LR(1) fusionado"
    }


def test_ide_lr0_uses_reductions_for_all_terminals() -> None:
    result = analyze_source(YALEX, YAPAR, "12 + 7", "LR(0)")

    reductions = [
        entry
        for entry in result["tables"]["reductions"]
        if entry["production"] == "expr -> NUMBER PLUS NUMBER"
    ]

    assert result["accepted"]
    assert {"$", "NUMBER", "PLUS"}.issubset({entry["lookahead"] for entry in reductions})
    assert result["tables"]["meta"]["terminals"] == ["$", "NUMBER", "PLUS"]


def test_ide_lr0_reports_conflict_cells_and_parallel_branches() -> None:
    yalex = r"""
ID id
PLUS \+
WS [ \t\r\n]+ skip
"""
    yapar = """
%token ID PLUS
%ignore WS
%start E

%%
E : E PLUS E | ID ;
"""

    result = analyze_source(yalex, yapar, "id + id + id", "LR(0)")

    assert any(conflict["kind"] == "shift/reduce" for conflict in result["conflicts"])
    assert any("conflict" in entry["action"] for entry in result["tables"]["action"])
    assert {branch["name"] for branch in result["parallel_branches"]} == {"shift", "reduce"}
    assert result["parallel_executor"]["type"] in {"process", "thread"}
    assert result["parallel_executor"]["note"]


def test_ide_automaton_state_metadata_is_available() -> None:
    result = analyze_source(YALEX, YAPAR, "12 + 7", "LR(0)")

    states = result["lr0_automaton"]["states"]

    assert states[0]["is_initial"]
    assert any(state["has_reduction"] for state in states)
    assert any(state["is_accepting"] for state in states)


def test_yalex_text_loader_supports_skip_rules() -> None:
    rules = loads_yalex(YALEX)

    assert [rule.type for rule in rules] == ["NUMBER", "PLUS", "WS"]
    assert rules[-1].skip


def test_yalex_text_loader_supports_arrow_skip_rules() -> None:
    rules = loads_yalex("WS [ \\t\\r\\n]+ -> skip")

    assert rules[0].skip


def test_create_ide_app_exposes_expected_routes() -> None:
    app = create_app()
    paths = {route.path for route in app.routes}

    assert "/" in paths
    assert "/api/analyze" in paths


def test_ide_html_exposes_only_required_parser_methods() -> None:
    html = Path("src/dlp_parserstudio/ide/static/index.html").read_text(encoding="utf-8")

    assert "<option>LL(1)</option>" in html
    assert "<option>LR(0)</option>" in html
    assert "<option selected>SLR(1)</option>" in html
    assert "<option>LALR(1)</option>" in html
    assert 'id="automaton-title"' in html
    assert 'id="lexicon-text"' in html


def test_ide_frontend_classifies_error_types() -> None:
    app_js = Path("src/dlp_parserstudio/ide/static/app.js").read_text(encoding="utf-8")
    styles = Path("src/dlp_parserstudio/ide/static/styles.css").read_text(encoding="utf-8")

    assert "function normalizeErrorType" in app_js
    assert "function getErrorBadge" in app_js
    assert "function getErrorSeverity" in app_js
    assert "derivado por errores lexicos previos" in app_js
    assert ".error-summary" in styles
    assert ".error-badge" in styles
    assert ".errors-empty-success" in styles
    assert "function getResultStatus" in app_js
    assert "function getAutomatonTitle" in app_js
    assert ".cell-conflict" in styles
    assert ".state-tag" in styles
