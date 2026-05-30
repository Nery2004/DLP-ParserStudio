import pytest

from dlp_parserstudio.core.grammar import Grammar, NonTerminal, Production, Terminal
from dlp_parserstudio.lexer.yalex import Token
from dlp_parserstudio.parser.first_follow import EOF
from dlp_parserstudio.parser.ll1 import LL1ConflictError, LL1Parser, build_ll1_table


def build_expression_grammar() -> Grammar:
    return Grammar.desde_estructura(
        {
            "start": "E",
            "productions": {
                "E": [["T", "Ep"]],
                "Ep": [["PLUS", "T", "Ep"], []],
                "T": [["ID"]],
            },
        }
    )


def test_build_table_for_valid_ll1_grammar() -> None:
    grammar = build_expression_grammar()

    table = build_ll1_table(grammar)

    assert table.conflicts == ()
    assert table[NonTerminal("E"), Terminal("ID")] == Production(
        NonTerminal("E"),
        (NonTerminal("T"), NonTerminal("Ep")),
    )
    assert table[NonTerminal("Ep"), Terminal("PLUS")] == Production(
        NonTerminal("Ep"),
        (Terminal("PLUS"), NonTerminal("T"), NonTerminal("Ep")),
    )
    assert table[NonTerminal("Ep"), EOF] == Production(NonTerminal("Ep"), ())


def test_parse_accepts_valid_token_sequence() -> None:
    parser = LL1Parser(build_expression_grammar())
    tokens = [
        Token("ID", "x", 1, 1),
        Token("PLUS", "+", 1, 3),
        Token("ID", "y", 1, 5),
    ]

    result = parser.parse(tokens)

    assert result.accepted
    assert result.error is None
    assert result.steps[-1].action == "accept"
    assert any(step.action == "Ep -> epsilon" for step in result.steps)


def test_parse_accepts_epsilon_written_as_symbol_name() -> None:
    grammar = Grammar.desde_estructura(
        {
            "start": "S",
            "productions": {
                "S": [["A"]],
                "A": [["epsilon"]],
            },
        }
    )
    parser = LL1Parser(grammar)

    result = parser.parse([])

    assert result.accepted
    assert any(step.action == "A -> epsilon" for step in result.steps)


def test_parse_rejects_invalid_token_sequence() -> None:
    parser = LL1Parser(build_expression_grammar())

    result = parser.parse(["PLUS", "ID"])

    assert not result.accepted
    assert result.error == "No LL(1) production for E with lookahead PLUS"
    assert result.steps[-1].action == f"error: {result.error}"


def test_detects_ll1_conflict() -> None:
    grammar = Grammar.desde_estructura(
        {
            "start": "S",
            "productions": {
                "S": [["A"], ["B"]],
                "A": [["ID"]],
                "B": [["ID"]],
            },
        }
    )

    table = build_ll1_table(grammar)

    assert len(table.conflicts) == 1
    assert table.conflicts[0].non_terminal == NonTerminal("S")
    assert table.conflicts[0].lookahead == Terminal("ID")

    with pytest.raises(LL1ConflictError) as error:
        LL1Parser(grammar)

    assert error.value.conflicts == table.conflicts
