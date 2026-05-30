"""SLR parsing table construction and bottom-up parsing."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from dlp_parserstudio.core.grammar import Grammar, NonTerminal, Production, Symbol, Terminal
from dlp_parserstudio.parser.first_follow import EOF, EPSILON_NAMES, calculate_follow_sets
from dlp_parserstudio.parser.lr0 import LR0Automaton, build_lr0_automaton
from dlp_parserstudio.parser.syntax_tree import SyntaxTree, TreeNode


@dataclass(frozen=True)
class SLRAction:
    """ACTION table entry."""

    kind: str
    target: int | None = None
    production: Production | None = None

    @classmethod
    def shift(cls, target: int) -> SLRAction:
        return cls("shift", target=target)

    @classmethod
    def reduce(cls, production: Production) -> SLRAction:
        return cls("reduce", production=production)

    @classmethod
    def accept(cls) -> SLRAction:
        return cls("accept")

    @classmethod
    def error(cls) -> SLRAction:
        return cls("error")

    def __str__(self) -> str:
        if self.kind == "shift":
            return f"shift {self.target}"
        if self.kind == "reduce" and self.production is not None:
            return f"reduce {_format_production(self.production)}"
        return self.kind


@dataclass(frozen=True)
class SLRConflict:
    """Conflict found while filling an SLR ACTION cell."""

    kind: str
    state: int
    lookahead: Terminal
    existing: SLRAction
    incoming: SLRAction


class SLRConflictError(ValueError):
    """Raised when an SLR table has conflicts."""

    def __init__(self, conflicts: Iterable[SLRConflict]) -> None:
        self.conflicts = tuple(conflicts)
        message = "; ".join(
            (
                f"{conflict.kind} conflict at ACTION[{conflict.state}, "
                f"{conflict.lookahead.name}] between {conflict.existing} "
                f"and {conflict.incoming}"
            )
            for conflict in self.conflicts
        )
        super().__init__(f"Grammar is not SLR(1): {message}")


@dataclass(frozen=True)
class SLRParsingTable:
    """SLR ACTION/GOTO table."""

    action: Mapping[tuple[int, Terminal], SLRAction]
    goto: Mapping[tuple[int, NonTerminal], int]
    conflicts: tuple[SLRConflict, ...] = ()
    automaton: LR0Automaton | None = None

    def action_for(self, state: int, lookahead: Terminal) -> SLRAction:
        return self.action.get((state, lookahead), SLRAction.error())

    def goto_for(self, state: int, non_terminal: NonTerminal) -> int | None:
        return self.goto.get((state, non_terminal))


SLRTable = SLRParsingTable


@dataclass(frozen=True)
class SLRParseStep:
    """One SLR parse step."""

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
class SLRParseError:
    """Syntax error with token position."""

    token: str
    line: int
    column: int
    message: str


@dataclass(frozen=True)
class SLRParseResult:
    """Result returned by the SLR parser."""

    accepted: bool
    steps: tuple[SLRParseStep, ...]
    conflicts: tuple[SLRConflict, ...] = ()
    errors: tuple[SLRParseError, ...] = ()
    syntax_tree: SyntaxTree | None = None

    @property
    def error(self) -> SLRParseError | None:
        return self.errors[0] if self.errors else None

    @property
    def tree(self) -> SyntaxTree | None:
        return self.syntax_tree


class SLRParser:
    """SLR parser backed by ACTION/GOTO tables."""

    def __init__(
        self,
        grammar: Grammar,
        table: SLRParsingTable | None = None,
        *,
        raise_on_conflicts: bool = False,
    ) -> None:
        self.table = table or build_slr_table(grammar)
        self.grammar = self.table.automaton.grammar if self.table.automaton else grammar

        if raise_on_conflicts and self.table.conflicts:
            raise SLRConflictError(self.table.conflicts)

    @property
    def conflicts(self) -> tuple[SLRConflict, ...]:
        return self.table.conflicts

    def parse(self, tokens: Iterable[object]) -> SLRParseResult:
        input_tokens = _normalize_input(tokens)
        stack: list[int | Symbol] = [0]
        nodes: list[TreeNode] = []
        position = 0
        steps: list[SLRParseStep] = []

        while True:
            state = _top_state(stack)
            current_token = input_tokens[position]
            action = self.table.action_for(state, current_token.terminal)
            stack_view = tuple(_stack_entry_name(entry) for entry in stack)
            remaining_input = tuple(token.terminal.name for token in input_tokens[position:])

            if action.kind == "shift":
                assert action.target is not None
                steps.append(
                    SLRParseStep(
                        stack_view,
                        remaining_input,
                        f"shift {current_token.terminal.name} and go to {action.target}",
                    )
                )
                stack.extend([current_token.terminal, action.target])
                nodes.append(
                    TreeNode(
                        current_token.terminal.name,
                        current_token.lexeme,
                        current_token.line,
                        current_token.column,
                    )
                )
                position += 1
                continue

            if action.kind == "reduce":
                assert action.production is not None
                production = action.production
                rhs_length = len(production.rhs)
                children = nodes[-rhs_length:] if rhs_length else []
                if rhs_length:
                    del stack[-2 * rhs_length :]
                    del nodes[-rhs_length:]

                goto_source = _top_state(stack)
                target = self.table.goto_for(goto_source, production.lhs)
                if target is None:
                    error = SLRParseError(
                        current_token.terminal.name,
                        current_token.line,
                        current_token.column,
                        f"Missing GOTO[{goto_source}, {production.lhs.name}] after reduction",
                    )
                    steps.append(
                        SLRParseStep(
                            stack_view,
                            remaining_input,
                            f"error: {error.message}",
                        )
                    )
                    return SLRParseResult(
                        False,
                        tuple(steps),
                        self.table.conflicts,
                        (error,),
                    )

                steps.append(
                    SLRParseStep(
                        stack_view,
                        remaining_input,
                        f"reduce {_format_production(production)}",
                    )
                )
                parent = TreeNode(production.lhs.name, children=children)
                stack.extend([production.lhs, target])
                nodes.append(parent)
                continue

            if action.kind == "accept":
                steps.append(SLRParseStep(stack_view, remaining_input, "accept"))
                syntax_tree = SyntaxTree(nodes[-1]) if nodes else None
                return SLRParseResult(
                    True,
                    tuple(steps),
                    self.table.conflicts,
                    syntax_tree=syntax_tree,
                )

            error = SLRParseError(
                current_token.terminal.name,
                current_token.line,
                current_token.column,
                f"Unexpected token {current_token.terminal.name} in state {state}",
            )
            steps.append(SLRParseStep(stack_view, remaining_input, f"error: {error.message}"))
            return SLRParseResult(False, tuple(steps), self.table.conflicts, (error,))


def build_slr_table(
    grammar: Grammar,
    *,
    raise_on_conflicts: bool = False,
) -> SLRParsingTable:
    """Build SLR ACTION/GOTO tables from the LR(0) automaton and FOLLOW sets."""

    automaton = build_lr0_automaton(_normalize_epsilon_grammar(grammar))
    follow_sets = calculate_follow_sets(automaton.grammar)
    action: dict[tuple[int, Terminal], SLRAction] = {}
    goto_table: dict[tuple[int, NonTerminal], int] = {}
    conflicts: list[SLRConflict] = []
    augmented_start = automaton.grammar.start_symbol

    for (source, symbol), target in automaton.transitions.items():
        if isinstance(symbol, Terminal):
            _set_action(
                action,
                conflicts,
                source,
                symbol,
                SLRAction.shift(target),
            )
        elif isinstance(symbol, NonTerminal):
            goto_table[(source, symbol)] = target

    for state_id, state in enumerate(automaton.states):
        for item in state.items:
            if not item.is_complete:
                continue

            if item.production.lhs == augmented_start:
                _set_action(action, conflicts, state_id, EOF, SLRAction.accept())
                continue

            for lookahead in sorted(
                follow_sets[item.production.lhs],
                key=lambda terminal: terminal.name,
            ):
                _set_action(
                    action,
                    conflicts,
                    state_id,
                    lookahead,
                    SLRAction.reduce(item.production),
                )

    table = SLRParsingTable(action, goto_table, tuple(conflicts), automaton)
    if raise_on_conflicts and conflicts:
        raise SLRConflictError(conflicts)
    return table


def _set_action(
    table: dict[tuple[int, Terminal], SLRAction],
    conflicts: list[SLRConflict],
    state: int,
    lookahead: Terminal,
    incoming: SLRAction,
) -> None:
    key = (state, lookahead)
    existing = table.get(key)

    if existing is None:
        table[key] = incoming
        return

    if existing == incoming:
        return

    conflicts.append(
        SLRConflict(_conflict_kind(existing, incoming), state, lookahead, existing, incoming)
    )


def _conflict_kind(existing: SLRAction, incoming: SLRAction) -> str:
    kinds = {existing.kind, incoming.kind}
    if kinds == {"shift", "reduce"}:
        return "shift/reduce"
    if existing.kind == "reduce" and incoming.kind == "reduce":
        return "reduce/reduce"
    return "/".join(sorted(kinds))


def _normalize_epsilon_grammar(grammar: Grammar) -> Grammar:
    productions: list[Production] = []

    for production in grammar.productions:
        rhs = production.rhs
        if len(rhs) == 1 and rhs[0].name.lower() in EPSILON_NAMES:
            rhs = ()
        productions.append(Production(production.lhs, rhs))

    return Grammar(
        non_terminals=set(grammar.non_terminals),
        terminals={
            terminal
            for terminal in grammar.terminals
            if terminal.name.lower() not in EPSILON_NAMES
        },
        start_symbol=grammar.start_symbol,
        productions=productions,
    )


@dataclass(frozen=True)
class _InputToken:
    terminal: Terminal
    lexeme: str
    line: int
    column: int


def _normalize_input(tokens: Iterable[object]) -> list[_InputToken]:
    input_tokens = [_as_input_token(token) for token in tokens]
    if input_tokens and input_tokens[-1].terminal == EOF:
        return input_tokens

    line, column = _eof_location(input_tokens)
    input_tokens.append(_InputToken(EOF, EOF.name, line, column))
    return input_tokens


def _as_input_token(token: object) -> _InputToken:
    if isinstance(token, Terminal):
        terminal = EOF if token.name == EOF.name else token
        return _InputToken(terminal, terminal.name, 1, 1)

    if isinstance(token, str):
        terminal = EOF if token == EOF.name else Terminal(token)
        return _InputToken(terminal, token, 1, 1)

    token_type = getattr(token, "type", None)
    if isinstance(token_type, str):
        lexeme = getattr(token, "lexeme", token_type)
        line = getattr(token, "line", 1)
        column = getattr(token, "column", 1)
        terminal = EOF if token_type == EOF.name else Terminal(token_type)
        return _InputToken(terminal, str(lexeme), int(line), int(column))

    raise TypeError("SLR parser input must contain token-like objects, Terminal, or str values.")


def _eof_location(tokens: list[_InputToken]) -> tuple[int, int]:
    if not tokens:
        return 1, 1

    last = tokens[-1]
    line = last.line
    column = last.column
    for character in last.lexeme:
        if character == "\n":
            line += 1
            column = 1
        else:
            column += 1
    return line, column


def _top_state(stack: list[int | Symbol]) -> int:
    state = stack[-1]
    if not isinstance(state, int):
        raise ValueError("Invalid SLR stack: top entry is not a state.")
    return state


def _stack_entry_name(entry: int | Symbol) -> str:
    if isinstance(entry, int):
        return str(entry)
    return entry.name


def _format_production(production: Production) -> str:
    rhs = " ".join(symbol.name for symbol in production.rhs)
    return f"{production.lhs.name} -> {rhs or 'epsilon'}"
