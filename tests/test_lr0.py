from dlp_parserstudio.core.grammar import Grammar, NonTerminal, Production, Terminal
from dlp_parserstudio.parser.lr0 import LR0Item, build_lr0_automaton, closure, goto


def build_simple_lr0_grammar() -> Grammar:
    return Grammar.desde_estructura(
        {
            "start": "S",
            "productions": {
                "S": [["C", "C"]],
                "C": [["c", "C"], ["d"]],
            },
        }
    )


def test_initial_closure_uses_augmented_grammar() -> None:
    grammar = build_simple_lr0_grammar().aumentar()
    state = closure({LR0Item(grammar.productions[0])}, grammar)

    assert state.items == {
        LR0Item(Production(NonTerminal("S'"), (NonTerminal("S"),)), 0),
        LR0Item(Production(NonTerminal("S"), (NonTerminal("C"), NonTerminal("C"))), 0),
        LR0Item(Production(NonTerminal("C"), (Terminal("c"), NonTerminal("C"))), 0),
        LR0Item(Production(NonTerminal("C"), (Terminal("d"),)), 0),
    }


def test_goto_with_terminal() -> None:
    grammar = build_simple_lr0_grammar().aumentar()
    initial = closure({LR0Item(grammar.productions[0])}, grammar)

    target = goto(initial, Terminal("c"))

    assert LR0Item(
        Production(NonTerminal("C"), (Terminal("c"), NonTerminal("C"))),
        1,
    ) in target.items
    assert LR0Item(
        Production(NonTerminal("C"), (Terminal("c"), NonTerminal("C"))),
        0,
    ) in target.items
    assert LR0Item(Production(NonTerminal("C"), (Terminal("d"),)), 0) in target.items


def test_goto_with_non_terminal() -> None:
    grammar = build_simple_lr0_grammar().aumentar()
    initial = closure({LR0Item(grammar.productions[0])}, grammar)

    target = goto(initial, NonTerminal("C"))

    assert LR0Item(
        Production(NonTerminal("S"), (NonTerminal("C"), NonTerminal("C"))),
        1,
    ) in target.items
    assert LR0Item(
        Production(NonTerminal("C"), (Terminal("c"), NonTerminal("C"))),
        0,
    ) in target.items
    assert LR0Item(Production(NonTerminal("C"), (Terminal("d"),)), 0) in target.items


def test_build_lr0_automaton_state_count_for_simple_grammar() -> None:
    automaton = build_lr0_automaton(build_simple_lr0_grammar())

    assert len(automaton.states) == 7
    assert automaton.transition(0, NonTerminal("S")) is not None
    assert automaton.transition(0, Terminal("c")) is not None


def test_export_dot_is_not_empty() -> None:
    automaton = build_lr0_automaton(build_simple_lr0_grammar())

    dot = automaton.to_dot()

    assert dot.strip()
    assert "digraph LR0" in dot
    assert "I0" in dot
    assert "->" in dot
