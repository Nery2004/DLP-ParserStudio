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
