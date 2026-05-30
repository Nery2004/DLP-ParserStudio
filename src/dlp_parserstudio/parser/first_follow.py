"""FIRST and FOLLOW set computation for context-free grammars."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from dlp_parserstudio.core.grammar import Grammar, NonTerminal, Symbol, Terminal

EPSILON = Symbol("epsilon")
EOF = Terminal("$")
EPSILON_NAMES = {"epsilon", "eps", "\u03b5"}


class FirstFollowCalculator:
    """Computes FIRST and FOLLOW sets for a grammar."""

    def __init__(self, grammar: Grammar) -> None:
        self.grammar = grammar
        self.first_sets = calculate_first_sets(grammar)
        self.follow_sets = calculate_follow_sets(grammar, self.first_sets)

    def first(self, symbol: Symbol | str | Iterable[Symbol | str]) -> set[Symbol]:
        if isinstance(symbol, Iterable) and not isinstance(symbol, (str, Symbol)):
            sequence = tuple(self._resolve_symbol(item) for item in symbol)
            return first_of_sequence(sequence, self.first_sets)

        resolved = self._resolve_symbol(symbol)
        if _is_epsilon_symbol(resolved):
            return {EPSILON}
        if resolved not in self.first_sets:
            return {resolved} if isinstance(resolved, Terminal) else set()
        return set(self.first_sets[resolved])

    def follow(self, non_terminal: NonTerminal | str) -> set[Terminal]:
        resolved = self._resolve_non_terminal(non_terminal)
        return set(self.follow_sets.get(resolved, set()))

    def _resolve_symbol(self, value: Symbol | str) -> Symbol:
        if isinstance(value, Symbol):
            return value
        if _is_epsilon_name(value):
            return EPSILON
        if value == EOF.name:
            return EOF

        for non_terminal in self.grammar.non_terminals:
            if non_terminal.name == value:
                return non_terminal
        for terminal in self.grammar.terminals:
            if terminal.name == value:
                return terminal
        return Terminal(value)

    def _resolve_non_terminal(self, value: NonTerminal | str) -> NonTerminal:
        if isinstance(value, NonTerminal):
            return value
        if isinstance(value, Terminal):
            raise TypeError("FOLLOW is defined only for non-terminal symbols.")

        for non_terminal in self.grammar.non_terminals:
            if non_terminal.name == value:
                return non_terminal
        return NonTerminal(value)


def calculate_first_sets(grammar: Grammar) -> dict[Symbol, set[Symbol]]:
    first_sets: dict[Symbol, set[Symbol]] = {
        non_terminal: set() for non_terminal in grammar.non_terminals
    }
    first_sets.update({terminal: {terminal} for terminal in grammar.terminals})
    first_sets[EPSILON] = {EPSILON}
    first_sets[EOF] = {EOF}

    changed = True
    while changed:
        changed = False

        for production in grammar.productions:
            before = len(first_sets[production.lhs])
            first_sets[production.lhs].update(
                first_of_sequence(_effective_rhs(production.rhs), first_sets)
            )
            if len(first_sets[production.lhs]) != before:
                changed = True

    return first_sets


def calculate_follow_sets(
    grammar: Grammar,
    first_sets: Mapping[Symbol, set[Symbol]] | None = None,
) -> dict[NonTerminal, set[Terminal]]:
    first_sets = first_sets or calculate_first_sets(grammar)
    follow_sets: dict[NonTerminal, set[Terminal]] = {
        non_terminal: set() for non_terminal in grammar.non_terminals
    }
    follow_sets[grammar.start_symbol].add(EOF)

    changed = True
    while changed:
        changed = False

        for production in grammar.productions:
            rhs = _effective_rhs(production.rhs)

            for index, symbol in enumerate(rhs):
                if not isinstance(symbol, NonTerminal):
                    continue

                beta = rhs[index + 1 :]
                first_beta = first_of_sequence(beta, first_sets)
                terminals_to_add = {
                    item for item in first_beta if isinstance(item, Terminal) and item != EOF
                }

                before = len(follow_sets[symbol])
                follow_sets[symbol].update(terminals_to_add)

                if EPSILON in first_beta:
                    follow_sets[symbol].update(follow_sets[production.lhs])

                if len(follow_sets[symbol]) != before:
                    changed = True

    return follow_sets


def first_of_sequence(
    symbols: Iterable[Symbol],
    first_sets: Mapping[Symbol, set[Symbol]],
) -> set[Symbol]:
    sequence = _effective_rhs(symbols)
    if not sequence:
        return {EPSILON}

    result: set[Symbol] = set()

    for symbol in sequence:
        if _is_epsilon_symbol(symbol):
            result.add(EPSILON)
            continue

        symbol_first = first_sets.get(symbol)
        if symbol_first is None:
            symbol_first = {symbol} if isinstance(symbol, Terminal) else set()

        result.update(item for item in symbol_first if item != EPSILON)
        if EPSILON not in symbol_first:
            break
    else:
        result.add(EPSILON)

    return result


def _effective_rhs(symbols: Iterable[Symbol]) -> tuple[Symbol, ...]:
    return tuple(symbol for symbol in symbols if not _is_epsilon_symbol(symbol))


def _is_epsilon_symbol(symbol: Symbol) -> bool:
    return _is_epsilon_name(symbol.name)


def _is_epsilon_name(name: str) -> bool:
    return name.lower() in EPSILON_NAMES
