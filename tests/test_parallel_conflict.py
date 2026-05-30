from dlp_parserstudio.core.grammar import Grammar
from dlp_parserstudio.lexer.yalex import Token
from dlp_parserstudio.parser.parallel_conflict import (
    ParallelConflictExplorer,
    explore_shift_reduce_branches,
    explore_shift_reduce_conflict,
)
from dlp_parserstudio.parser.slr import build_slr_table


def build_ambiguous_expression_grammar() -> Grammar:
    return Grammar.desde_estructura(
        {
            "start": "E",
            "productions": {
                "E": [["E", "+", "E"], ["id"]],
            },
        }
    )


def test_parallel_conflict_explores_shift_and_reduce_branches() -> None:
    grammar = build_ambiguous_expression_grammar()
    table = build_slr_table(grammar)
    tokens = [
        Token("id", "id", 1, 1),
        Token("+", "+", 1, 4),
        Token("id", "id", 1, 6),
        Token("+", "+", 1, 9),
        Token("id", "id", 1, 11),
    ]

    result = explore_shift_reduce_conflict(grammar, tokens, table=table)

    assert result.conflict_state is not None
    assert result.lookahead == "+"
    assert len(result.branches) == 2
    assert {branch.name for branch in result.branches} == {"shift", "reduce"}
    assert {branch.result for branch in result.branches} == {"accepted"}

    for branch in result.branches:
        assert branch.chosen_action.startswith(branch.name)
        assert branch.stack
        assert branch.remaining_input == ("$",)
        assert branch.steps
        assert any("shift/reduce conflict" in step.action for step in branch.steps)
        assert any(step.action.startswith(f"choose {branch.name}") for step in branch.steps)


def test_parallel_conflict_can_be_used_from_explorer_class() -> None:
    grammar = build_ambiguous_expression_grammar()
    explorer = ParallelConflictExplorer.from_grammar(grammar)

    result = explorer.explore(["id", "+", "id", "+", "id"])

    assert len(result) == 2
    assert [branch.name for branch in result] == ["shift", "reduce"]


def test_parallel_conflict_can_return_only_branches() -> None:
    branches = explore_shift_reduce_branches(
        build_ambiguous_expression_grammar(),
        ["id", "+", "id", "+", "id"],
    )

    assert len(branches) == 2
    assert {branch.name for branch in branches} == {"shift", "reduce"}


def test_parallel_conflict_marks_rejected_branches() -> None:
    grammar = build_ambiguous_expression_grammar()

    result = explore_shift_reduce_conflict(grammar, ["id", "+", "id", "+"])

    assert len(result.branches) == 2
    assert {branch.result for branch in result.branches} == {"rejected"}
    assert all(branch.error for branch in result.branches)
