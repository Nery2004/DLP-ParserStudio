from pathlib import Path

from dlp_parserstudio.ide.analysis import analyze_source
from dlp_parserstudio.ide.app import DisambiguateRequest, create_app
from dlp_parserstudio.parser.disambiguation import (
    analyze_disambiguation,
    auto_resolve_disambiguation,
)
from dlp_parserstudio.parser.yapar_loader import loads_yapar


AMBIGUOUS_EXPR = """
%token ID NUMBER PLUS TIMES LPAREN RPAREN
%ignore WS
%start expr

%%
expr : expr PLUS expr
     | expr TIMES expr
     | LPAREN expr RPAREN
     | ID
     | NUMBER ;
"""


def test_detects_ambiguous_expression_and_suggests_precedence_grammar() -> None:
    result = analyze_disambiguation(loads_yapar(AMBIGUOUS_EXPR))

    suggestion = next(
        suggestion for suggestion in result["suggestions"]
        if suggestion["kind"] == "precedence_grammar"
    )

    assert result["has_suggestions"]
    assert "expr : term exprp ;" in suggestion["suggested_grammar"]
    assert "term : factor termp ;" in suggestion["suggested_grammar"]
    assert "PLUS" in suggestion["suggested_grammar"]
    assert "TIMES" in suggestion["suggested_grammar"]


def test_auto_resolve_applies_expression_rewrite() -> None:
    result = auto_resolve_disambiguation(loads_yapar(AMBIGUOUS_EXPR), method="SLR(1)")

    assert result["resolved"]
    assert result["applied_suggestion"]["kind"] == "precedence_grammar"
    assert "expr : term exprp ;" in result["resolved_yapar"]
    assert "factor : NUMBER | ID | LPAREN expr RPAREN ;" in result["resolved_yapar"]


def test_disambiguate_resolve_endpoint_returns_resolved_yapar() -> None:
    app = create_app()
    route = next(route for route in app.routes if route.path == "/api/disambiguate/resolve")

    data = route.endpoint(DisambiguateRequest(yapar_text=AMBIGUOUS_EXPR, method="SLR(1)"))

    assert data["resolved"]
    assert data["resolved_yapar"]
    assert data["applied_suggestion"]["kind"] == "precedence_grammar"


def test_ambiguity_expression_example_can_be_resolved_and_accepted() -> None:
    base = Path("examples/ambiguity_expression")
    yalex = (base / "ambiguous_expression.yalex").read_text(encoding="utf-8")
    yapar = (base / "ambiguous_expression.yapar").read_text(encoding="utf-8")
    input_text = (base / "ambiguous_expression_input.txt").read_text(encoding="utf-8")

    initial = analyze_source(yalex, yapar, input_text, "SLR(1)")
    resolved = auto_resolve_disambiguation(
        loads_yapar(yapar),
        conflicts=initial["conflicts"],
        method="SLR(1)",
        branch_results=initial["parallel_branches"],
    )
    final = analyze_source(yalex, resolved["resolved_yapar"], input_text, "SLR(1)")

    assert any(conflict["kind"] == "shift/reduce" for conflict in initial["conflicts"])
    assert resolved["resolved"]
    assert final["accepted"]
    assert final["conflicts"] == []
