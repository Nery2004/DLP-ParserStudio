from dlp_parserstudio.core.grammar import Grammar, NonTerminal, Production, Terminal
from dlp_parserstudio.lexer.yalex import Token
from dlp_parserstudio.parser.lalr import (
    LALRConflictError,
    LALRParser,
    LR1Item,
    build_lalr_automaton,
    build_lalr_table,
    build_lr1_automaton,
)
from dlp_parserstudio.parser.yapar_loader import load_yapar
from dlp_parserstudio.parser.slr import build_slr_table


def build_assignment_grammar() -> Grammar:
    return Grammar.desde_estructura(
        {
            "start": "S",
            "productions": {
                "S": [["L", "=", "R"], ["R"]],
                "L": [["*", "R"], ["id"]],
                "R": [["L"]],
            },
        }
    )


def leaf_pairs(node) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []

    def visit(current) -> None:
        if current.lexeme is not None:
            pairs.append((current.symbol, current.lexeme))
        for child in current.children:
            visit(child)

    visit(node)
    return pairs


def test_builds_lr1_items_with_lookahead() -> None:
    automaton = build_lr1_automaton(build_assignment_grammar())

    assert any(isinstance(item, LR1Item) for item in automaton.states[0].items)
    assert any(
        item.production == Production(NonTerminal("S'"), (NonTerminal("S"),))
        and item.lookahead == Terminal("$")
        for item in automaton.states[0].items
    )


def test_lalr_merges_lr1_states_with_same_core() -> None:
    grammar = build_assignment_grammar()
    lr1 = build_lr1_automaton(grammar)
    lalr = build_lalr_automaton(grammar)

    assert len(lalr.states) < len(lr1.states)
    assert len(lalr.states) == 10
    assert lalr.transitions


def test_assignment_grammar_slr_fails_but_lalr_has_no_conflicts() -> None:
    grammar = build_assignment_grammar()
    slr_table = build_slr_table(grammar)
    lalr_table = build_lalr_table(grammar)

    assert any(conflict.kind == "shift/reduce" for conflict in slr_table.conflicts)
    assert lalr_table.conflicts == ()


def test_lalr_parses_assignment_and_builds_syntax_tree() -> None:
    parser = LALRParser(build_assignment_grammar())
    tokens = [
        Token("id", "id", 1, 1),
        Token("=", "=", 1, 4),
        Token("id", "id", 1, 6),
    ]

    result = parser.parse(tokens)

    assert result.accepted
    assert result.errors == ()
    assert result.syntax_tree is not None
    assert result.syntax_tree.root.symbol == "S"
    assert leaf_pairs(result.syntax_tree.root) == [
        ("id", "id"),
        ("=", "="),
        ("id", "id"),
    ]
    assert result.syntax_tree.to_dict()["symbol"] == "S"
    assert "digraph SyntaxTree" in result.syntax_tree.to_dot()


def test_lalr_rejects_invalid_assignment_with_token_location() -> None:
    parser = LALRParser(build_assignment_grammar())

    result = parser.parse(
        [
            Token("id", "id", 2, 1),
            Token("=", "=", 2, 4),
            Token("=", "=", 2, 6),
        ]
    )

    assert not result.accepted
    assert result.error is not None
    assert result.error.token == "="
    assert result.error.line == 2
    assert result.error.column == 6


def test_lalr_loads_classic_assignment_example() -> None:
    grammar = load_yapar("examples/classic_assignment_lalr.yapar")
    parser = LALRParser(grammar)

    result = parser.parse(
        [
            Token("ID", "id", 1, 1),
            Token("EQUAL", "=", 1, 4),
            Token("ID", "id", 1, 6),
        ]
    )

    assert result.accepted
    assert result.syntax_tree is not None
    assert result.syntax_tree.root.symbol == "S"


def test_lalr_detects_conflicts() -> None:
    grammar = Grammar.desde_estructura(
        {
            "start": "E",
            "productions": {
                "E": [["E", "+", "E"], ["id"]],
            },
        }
    )

    table = build_lalr_table(grammar)

    assert any(conflict.kind == "shift/reduce" for conflict in table.conflicts)

    try:
        build_lalr_table(grammar, raise_on_conflicts=True)
    except LALRConflictError as error:
        assert error.conflicts == table.conflicts
    else:
        raise AssertionError("Expected LALRConflictError")
