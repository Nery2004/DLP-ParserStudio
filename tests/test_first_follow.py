from dlp_parserstudio.core.grammar import Grammar, NonTerminal, Terminal
from dlp_parserstudio.parser.first_follow import EOF, EPSILON, FirstFollowCalculator


def test_first_and_follow_for_expression_grammar() -> None:
    grammar = Grammar.desde_estructura(
        {
            "start": "E",
            "productions": {
                "E": [["T", "E'"]],
                "E'": [["+", "T", "E'"], ["epsilon"]],
                "T": [["id"]],
            },
        }
    )

    calculator = FirstFollowCalculator(grammar)

    assert calculator.first("E") == {Terminal("id")}
    assert calculator.first("E'") == {Terminal("+"), EPSILON}
    assert calculator.first("T") == {Terminal("id")}
    assert calculator.follow("E") == {EOF}
    assert calculator.follow("E'") == {EOF}
    assert calculator.follow("T") == {Terminal("+"), EOF}


def test_first_and_follow_for_simple_grammar() -> None:
    grammar = Grammar.desde_estructura(
        {
            "start": "S",
            "productions": {
                "S": [["A", "a"], ["b", "A", "c"], ["d", "c"], ["b", "d", "a"]],
                "A": [["d"]],
            },
        }
    )

    calculator = FirstFollowCalculator(grammar)

    assert calculator.first("S") == {Terminal("b"), Terminal("d")}
    assert calculator.first("A") == {Terminal("d")}
    assert calculator.follow("S") == {EOF}
    assert calculator.follow(NonTerminal("A")) == {Terminal("a"), Terminal("c")}
