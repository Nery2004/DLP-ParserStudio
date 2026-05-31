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
    slr = analyze_source(YALEX, YAPAR, "12 + 7", "SLR(1)")
    lalr = analyze_source(YALEX, YAPAR, "12 + 7", "LALR(1)")

    assert slr["tables"]["reductions"]
    assert lalr["tables"]["reductions"]
    assert {entry["source"] for entry in slr["tables"]["reductions"]} == {
        "SLR(1): FOLLOW global del LHS"
    }
    assert {entry["source"] for entry in lalr["tables"]["reductions"]} == {
        "LALR(1): lookahead LR(1) fusionado"
    }


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
