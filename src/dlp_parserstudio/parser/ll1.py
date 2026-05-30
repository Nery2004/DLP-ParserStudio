"""LL(1) parsing table construction and predictive parsing."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from dlp_parserstudio.core.grammar import Grammar, NonTerminal, Production, Symbol, Terminal
from dlp_parserstudio.parser.first_follow import (
    EOF,
    EPSILON,
    EPSILON_NAMES,
    calculate_first_sets,
    calculate_follow_sets,
    first_of_sequence,
)


@dataclass(frozen=True)
class LL1Conflict:
    """Conflict found while filling one LL(1) table cell."""

    non_terminal: NonTerminal
    lookahead: Terminal
    existing: Production
    incoming: Production


class LL1ConflictError(ValueError):
    """Raised when a grammar is not LL(1)."""

    def __init__(self, conflicts: Iterable[LL1Conflict]) -> None:
        self.conflicts = tuple(conflicts)
        message = "; ".join(
            (
                f"M[{conflict.non_terminal.name}, {conflict.lookahead.name}] has "
                f"{conflict.existing} and {conflict.incoming}"
            )
            for conflict in self.conflicts
        )
        super().__init__(f"Grammar is not LL(1): {message}")


@dataclass(frozen=True)
class LL1ParsingTable:
    """Predictive parsing table indexed by (non-terminal, lookahead)."""

    entries: Mapping[tuple[NonTerminal, Terminal], Production]
    conflicts: tuple[LL1Conflict, ...] = ()

    def get(self, non_terminal: NonTerminal, lookahead: Terminal) -> Production | None:
        return self.entries.get((non_terminal, lookahead))

    def __contains__(self, key: tuple[NonTerminal, Terminal]) -> bool:
        return key in self.entries

    def __getitem__(self, key: tuple[NonTerminal, Terminal]) -> Production:
        return self.entries[key]


LL1Table = LL1ParsingTable


@dataclass(frozen=True)
class ParseStep:
    """One step of the LL(1) analysis trace."""

    stack: tuple[str, ...]
    remaining_input: tuple[str, ...]
    action: str

    @property
    def input_remaining(self) -> tuple[str, ...]:
        return self.remaining_input

    @property
    def input_restante(self) -> tuple[str, ...]:
        return self.remaining_input

    @property
    def accion(self) -> str:
        return self.action


@dataclass(frozen=True)
class ParseResult:
    """Result of predictive parsing."""

    accepted: bool
    steps: tuple[ParseStep, ...]
    error: str | None = None


class LL1Parser:
    """Predictive parser that uses an LL(1) table."""

    def __init__(
        self,
        grammar: Grammar,
        table: LL1ParsingTable | None = None,
        *,
        raise_on_conflicts: bool = True,
    ) -> None:
        self.grammar = grammar
        self.table = table or build_ll1_table(grammar)

        if raise_on_conflicts and self.table.conflicts:
            raise LL1ConflictError(self.table.conflicts)

    def parse(self, tokens: Iterable[object]) -> ParseResult:
        input_symbols = _normalize_input(tokens)
        stack: list[Symbol] = [EOF, self.grammar.start_symbol]
        position = 0
        steps: list[ParseStep] = []

        while stack:
            top = stack.pop()
            lookahead = input_symbols[position]
            current_stack = tuple(_symbol_name(symbol) for symbol in [*stack, top])
            remaining_input = tuple(
                _symbol_name(symbol) for symbol in input_symbols[position:]
            )

            if top == EOF and lookahead == EOF:
                steps.append(ParseStep(current_stack, remaining_input, "accept"))
                return ParseResult(True, tuple(steps))

            if isinstance(top, Terminal):
                if top == lookahead:
                    steps.append(
                        ParseStep(current_stack, remaining_input, f"match {lookahead.name}")
                    )
                    position += 1
                    continue

                error = f"Expected {top.name}, found {lookahead.name}"
                steps.append(ParseStep(current_stack, remaining_input, f"error: {error}"))
                return ParseResult(False, tuple(steps), error)

            if isinstance(top, NonTerminal):
                production = self.table.get(top, lookahead)
                if production is None:
                    error = f"No LL(1) production for {top.name} with lookahead {lookahead.name}"
                    steps.append(ParseStep(current_stack, remaining_input, f"error: {error}"))
                    return ParseResult(False, tuple(steps), error)

                rhs = tuple(
                    symbol for symbol in production.rhs if not _is_epsilon_symbol(symbol)
                )
                action = _format_production(production)
                steps.append(ParseStep(current_stack, remaining_input, action))
                stack.extend(reversed(rhs))
                continue

            error = f"Unsupported stack symbol {top.name}"
            steps.append(ParseStep(current_stack, remaining_input, f"error: {error}"))
            return ParseResult(False, tuple(steps), error)

        error = "Parser stack emptied before accepting input"
        remaining_input = tuple(_symbol_name(symbol) for symbol in input_symbols[position:])
        steps.append(ParseStep((), remaining_input, f"error: {error}"))
        return ParseResult(False, tuple(steps), error)


def build_ll1_table(
    grammar: Grammar,
    *,
    raise_on_conflicts: bool = False,
) -> LL1ParsingTable:
    """Build an LL(1) table using FIRST and FOLLOW sets."""

    first_sets = calculate_first_sets(grammar)
    follow_sets = calculate_follow_sets(grammar, first_sets)
    entries: dict[tuple[NonTerminal, Terminal], Production] = {}
    conflicts: list[LL1Conflict] = []

    for production in grammar.productions:
        first_alpha = first_of_sequence(production.rhs, first_sets)
        lookaheads = {
            symbol for symbol in first_alpha if isinstance(symbol, Terminal) and symbol != EOF
        }

        if EPSILON in first_alpha:
            lookaheads.update(follow_sets[production.lhs])

        for lookahead in lookaheads:
            key = (production.lhs, lookahead)
            existing = entries.get(key)

            if existing is None:
                entries[key] = production
            elif existing != production:
                conflicts.append(LL1Conflict(production.lhs, lookahead, existing, production))

    table = LL1ParsingTable(entries, tuple(conflicts))
    if raise_on_conflicts and conflicts:
        raise LL1ConflictError(conflicts)
    return table


def _normalize_input(tokens: Iterable[object]) -> list[Terminal]:
    input_symbols = [_as_terminal(token) for token in tokens]
    if not input_symbols or input_symbols[-1] != EOF:
        input_symbols.append(EOF)
    return input_symbols


def _as_terminal(token: object) -> Terminal:
    if isinstance(token, Terminal):
        return EOF if token.name == EOF.name else token
    if isinstance(token, str):
        return EOF if token == EOF.name else Terminal(token)

    token_type = getattr(token, "type", None)
    if isinstance(token_type, str):
        return EOF if token_type == EOF.name else Terminal(token_type)

    raise TypeError("Parser input must contain token-like objects, Terminal, or str values.")


def _symbol_name(symbol: Symbol) -> str:
    return symbol.name


def _format_production(production: Production) -> str:
    rhs = " ".join(
        symbol.name for symbol in production.rhs if not _is_epsilon_symbol(symbol)
    )
    return f"{production.lhs.name} -> {rhs or 'epsilon'}"


def _is_epsilon_symbol(symbol: Symbol) -> bool:
    return symbol == EPSILON or symbol.name.lower() in EPSILON_NAMES
