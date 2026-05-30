import pytest

from dlp_parserstudio.core.grammar import Grammar, NonTerminal, Production, Terminal
from dlp_parserstudio.lexer.yalex import Token
from dlp_parserstudio.parser.first_follow import EOF
from dlp_parserstudio.parser.slr import (
    SLRAction,
    SLRConflictError,
    SLRParser,
    build_slr_table,
)


def build_slr_grammar() -> Grammar:
    return Grammar.desde_estructura(
        {
            "start": "S",
            "productions": {
                "S": [["C", "C"]],
                "C": [["c", "C"], ["d"]],
            },
        }
    )


def test_build_table_for_slr_accepted_grammar() -> None:
    table = build_slr_table(build_slr_grammar())

    assert table.conflicts == ()
    assert table.action_for(0, Terminal("c")).kind == "shift"
    assert table.action_for(0, Terminal("d")).kind == "shift"
    assert table.goto_for(0, NonTerminal("S")) is not None
    assert table.goto_for(0, NonTerminal("C")) is not None


def test_parse_accepts_valid_slr_chain() -> None:
    parser = SLRParser(build_slr_grammar())
    tokens = [
        Token("c", "c", 1, 1),
        Token("d", "d", 1, 2),
        Token("d", "d", 1, 3),
    ]

    result = parser.parse(tokens)

    assert result.accepted
    assert result.conflicts == ()
    assert result.errors == ()
    assert result.steps[-1].action == "accept"
    assert any(step.action.startswith("reduce C -> d") for step in result.steps)


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

    result = SLRParser(grammar).parse([])

    assert result.accepted
    assert any(step.action == "reduce A -> epsilon" for step in result.steps)


def test_parse_rejects_invalid_slr_chain_with_token_location() -> None:
    parser = SLRParser(build_slr_grammar())

    result = parser.parse(
        [
            Token("c", "c", 3, 4),
            Token("c", "c", 3, 5),
        ]
    )

    assert not result.accepted
    assert result.error is not None
    assert result.error.token == "$"
    assert result.error.line == 3
    assert result.error.column == 6
    assert result.steps[-1].action == f"error: {result.error.message}"


def test_detects_shift_reduce_conflict() -> None:
    grammar = Grammar.desde_estructura(
        {
            "start": "E",
            "productions": {
                "E": [["E", "PLUS", "E"], ["ID"]],
            },
        }
    )

    table = build_slr_table(grammar)

    assert any(conflict.kind == "shift/reduce" for conflict in table.conflicts)

    with pytest.raises(SLRConflictError):
        build_slr_table(grammar, raise_on_conflicts=True)

    result = SLRParser(grammar).parse(["ID", "PLUS", "ID"])

    assert result.conflicts
    assert {conflict.kind for conflict in result.conflicts} == {"shift/reduce"}


def test_detects_reduce_reduce_conflict() -> None:
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

    table = build_slr_table(grammar)

    assert any(conflict.kind == "reduce/reduce" for conflict in table.conflicts)


def test_uses_follow_sets_for_reduction_lookaheads() -> None:
    grammar = Grammar.desde_estructura(
        {
            "start": "S",
            "productions": {
                "S": [["A", "B"]],
                "A": [["a"], []],
                "B": [["b"]],
            },
        }
    )

    table = build_slr_table(grammar)
    epsilon_reduce_states = [
        state_id
        for (state_id, lookahead), action in table.action.items()
        if action == SLRAction.reduce(Production(NonTerminal("A"), ()))
        and lookahead == Terminal("b")
    ]

    assert table.conflicts == ()
    assert epsilon_reduce_states
    for state_id in epsilon_reduce_states:
        assert table.action_for(state_id, Terminal("a")) != SLRAction.reduce(
            Production(NonTerminal("A"), ())
        )
        assert table.action_for(state_id, EOF) != SLRAction.reduce(
            Production(NonTerminal("A"), ())
        )
