"""LALR(1) automaton, ACTION/GOTO table, and parser."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from dlp_parserstudio.core.grammar import Grammar, NonTerminal, Production, Symbol, Terminal
from dlp_parserstudio.parser.first_follow import (
    EOF,
    EPSILON_NAMES,
    calculate_first_sets,
    first_of_sequence,
)
from dlp_parserstudio.parser.syntax_tree import SyntaxTree, TreeNode


@dataclass(frozen=True)
class LR1Item:
    """LR(1) item of the form A -> alpha . beta, lookahead."""

    production: Production
    dot: int = 0
    lookahead: Terminal = EOF

    def __post_init__(self) -> None:
        if self.dot < 0 or self.dot > len(self.production.rhs):
            raise ValueError("LR(1) item dot position is outside the production body.")
        if not isinstance(self.lookahead, Terminal):
            raise TypeError("LR(1) item lookahead must be a Terminal.")

    @property
    def next_symbol(self) -> Symbol | None:
        if self.is_complete:
            return None
        return self.production.rhs[self.dot]

    @property
    def is_complete(self) -> bool:
        return self.dot == len(self.production.rhs)

    @property
    def core(self) -> tuple[Production, int]:
        return self.production, self.dot

    def advance(self) -> LR1Item:
        if self.is_complete:
            raise ValueError("Cannot advance a complete LR(1) item.")
        return LR1Item(self.production, self.dot + 1, self.lookahead)

    def __str__(self) -> str:
        rhs = [symbol.name for symbol in self.production.rhs]
        rhs.insert(self.dot, ".")
        return f"{self.production.lhs.name} -> {' '.join(rhs)}, {self.lookahead.name}"


@dataclass(frozen=True, init=False)
class LR1State:
    """Set of LR(1) items."""

    items: frozenset[LR1Item]
    grammar: Grammar | None = field(default=None, compare=False, hash=False, repr=False)

    def __init__(
        self,
        items: Iterable[LR1Item],
        grammar: Grammar | None = None,
    ) -> None:
        object.__setattr__(self, "items", frozenset(items))
        object.__setattr__(self, "grammar", grammar)

    @property
    def core(self) -> frozenset[tuple[Production, int]]:
        return frozenset(item.core for item in self.items)

    def next_symbols(self) -> set[Symbol]:
        return {
            item.next_symbol
            for item in self.items
            if item.next_symbol is not None
        }

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)


@dataclass(frozen=True)
class LR1Automaton:
    """Canonical LR(1) automaton for an augmented grammar."""

    grammar: Grammar
    states: tuple[LR1State, ...]
    transitions: Mapping[tuple[int, Symbol], int]

    def transition(self, state_id: int, symbol: Symbol) -> int | None:
        return self.transitions.get((state_id, symbol))


@dataclass(frozen=True)
class LALRAutomaton:
    """LALR(1) automaton obtained by merging LR(1) states with equal cores."""

    grammar: Grammar
    states: tuple[LR1State, ...]
    transitions: Mapping[tuple[int, Symbol], int]
    canonical_automaton: LR1Automaton

    def transition(self, state_id: int, symbol: Symbol) -> int | None:
        return self.transitions.get((state_id, symbol))


@dataclass(frozen=True)
class LALRAction:
    """ACTION table entry."""

    kind: str
    target: int | None = None
    production: Production | None = None

    @classmethod
    def shift(cls, target: int) -> LALRAction:
        return cls("shift", target=target)

    @classmethod
    def reduce(cls, production: Production) -> LALRAction:
        return cls("reduce", production=production)

    @classmethod
    def accept(cls) -> LALRAction:
        return cls("accept")

    @classmethod
    def error(cls) -> LALRAction:
        return cls("error")

    def __str__(self) -> str:
        if self.kind == "shift":
            return f"shift {self.target}"
        if self.kind == "reduce" and self.production is not None:
            return f"reduce {_format_production(self.production)}"
        return self.kind


@dataclass(frozen=True)
class LALRConflict:
    """Conflict found while filling a LALR ACTION cell."""

    kind: str
    state: int
    lookahead: Terminal
    existing: LALRAction
    incoming: LALRAction


class LALRConflictError(ValueError):
    """Raised when a LALR table has conflicts."""

    def __init__(self, conflicts: Iterable[LALRConflict]) -> None:
        self.conflicts = tuple(conflicts)
        message = "; ".join(
            (
                f"{conflict.kind} conflict at ACTION[{conflict.state}, "
                f"{conflict.lookahead.name}] between {conflict.existing} "
                f"and {conflict.incoming}"
            )
            for conflict in self.conflicts
        )
        super().__init__(f"Grammar is not LALR(1): {message}")


@dataclass(frozen=True)
class LALRParsingTable:
    """LALR ACTION/GOTO table."""

    action: Mapping[tuple[int, Terminal], LALRAction]
    goto: Mapping[tuple[int, NonTerminal], int]
    conflicts: tuple[LALRConflict, ...] = ()
    automaton: LALRAutomaton | None = None

    def action_for(self, state: int, lookahead: Terminal) -> LALRAction:
        return self.action.get((state, lookahead), LALRAction.error())

    def goto_for(self, state: int, non_terminal: NonTerminal) -> int | None:
        return self.goto.get((state, non_terminal))


LALRTable = LALRParsingTable


@dataclass(frozen=True)
class LALRParseStep:
    """One LALR parse step."""

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
class LALRParseError:
    """Syntax error with token position."""

    token: str
    line: int
    column: int
    message: str


@dataclass(frozen=True)
class LALRParseResult:
    """Result returned by the LALR parser."""

    accepted: bool
    steps: tuple[LALRParseStep, ...]
    conflicts: tuple[LALRConflict, ...] = ()
    errors: tuple[LALRParseError, ...] = ()
    syntax_tree: SyntaxTree | None = None

    @property
    def error(self) -> LALRParseError | None:
        return self.errors[0] if self.errors else None

    @property
    def tree(self) -> SyntaxTree | None:
        return self.syntax_tree


class LALRParser:
    """LALR parser backed by ACTION/GOTO tables."""

    def __init__(
        self,
        grammar: Grammar,
        table: LALRParsingTable | None = None,
        *,
        raise_on_conflicts: bool = False,
    ) -> None:
        self.table = table or build_lalr_table(grammar)
        self.grammar = self.table.automaton.grammar if self.table.automaton else grammar

        if raise_on_conflicts and self.table.conflicts:
            raise LALRConflictError(self.table.conflicts)

    @property
    def conflicts(self) -> tuple[LALRConflict, ...]:
        return self.table.conflicts

    def parse(self, tokens: Iterable[object]) -> LALRParseResult:
        input_tokens = _normalize_input(tokens)
        stack: list[int | Symbol] = [0]
        nodes: list[TreeNode] = []
        position = 0
        steps: list[LALRParseStep] = []

        while True:
            state = _top_state(stack)
            current_token = input_tokens[position]
            action = self.table.action_for(state, current_token.terminal)
            stack_view = tuple(_stack_entry_name(entry) for entry in stack)
            remaining_input = tuple(token.terminal.name for token in input_tokens[position:])

            if action.kind == "shift":
                assert action.target is not None
                steps.append(
                    LALRParseStep(
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
                    error = LALRParseError(
                        current_token.terminal.name,
                        current_token.line,
                        current_token.column,
                        f"Missing GOTO[{goto_source}, {production.lhs.name}] after reduction",
                    )
                    steps.append(
                        LALRParseStep(
                            stack_view,
                            remaining_input,
                            f"error: {error.message}",
                        )
                    )
                    return LALRParseResult(
                        False,
                        tuple(steps),
                        self.table.conflicts,
                        (error,),
                    )

                steps.append(
                    LALRParseStep(
                        stack_view,
                        remaining_input,
                        f"reduce {_format_production(production)}",
                    )
                )
                stack.extend([production.lhs, target])
                nodes.append(TreeNode(production.lhs.name, children=children))
                continue

            if action.kind == "accept":
                steps.append(LALRParseStep(stack_view, remaining_input, "accept"))
                syntax_tree = SyntaxTree(nodes[-1]) if nodes else None
                return LALRParseResult(
                    True,
                    tuple(steps),
                    self.table.conflicts,
                    syntax_tree=syntax_tree,
                )

            error = LALRParseError(
                current_token.terminal.name,
                current_token.line,
                current_token.column,
                f"Unexpected token {current_token.terminal.name} in state {state}",
            )
            steps.append(LALRParseStep(stack_view, remaining_input, f"error: {error.message}"))
            return LALRParseResult(False, tuple(steps), self.table.conflicts, (error,))


def closure_lr1(
    items: Iterable[LR1Item] | LR1State,
    grammar: Grammar | None = None,
    first_sets: Mapping[Symbol, set[Symbol]] | None = None,
) -> LR1State:
    """Compute LR(1) closure."""

    if isinstance(items, LR1State):
        grammar = grammar or items.grammar
        item_set = set(items.items)
    else:
        item_set = set(items)

    if grammar is None:
        raise ValueError("closure_lr1 requires a Grammar.")

    first_sets = first_sets or calculate_first_sets(grammar)

    changed = True
    while changed:
        changed = False

        for item in tuple(item_set):
            next_symbol = item.next_symbol
            if not isinstance(next_symbol, NonTerminal):
                continue

            beta = item.production.rhs[item.dot + 1 :]
            lookaheads = {
                symbol
                for symbol in first_of_sequence((*beta, item.lookahead), first_sets)
                if isinstance(symbol, Terminal)
            }

            for production in grammar.producciones_de(next_symbol):
                for lookahead in lookaheads:
                    candidate = LR1Item(production, 0, lookahead)
                    if candidate not in item_set:
                        item_set.add(candidate)
                        changed = True

    return LR1State(item_set, grammar)


def goto_lr1(
    state: LR1State | Iterable[LR1Item],
    symbol: Symbol,
    grammar: Grammar | None = None,
    first_sets: Mapping[Symbol, set[Symbol]] | None = None,
) -> LR1State:
    """Compute LR(1) GOTO(state, symbol)."""

    if isinstance(state, LR1State):
        grammar = grammar or state.grammar
        items = state.items
    else:
        items = frozenset(state)

    if grammar is None:
        raise ValueError("goto_lr1 requires a Grammar.")

    advanced_items = [
        item.advance()
        for item in items
        if item.next_symbol == symbol
    ]
    return closure_lr1(advanced_items, grammar, first_sets)


def build_lr1_automaton(grammar: Grammar) -> LR1Automaton:
    """Build the canonical LR(1) automaton using G' with S' -> S."""

    augmented_grammar = _normalize_epsilon_grammar(grammar).aumentar()
    first_sets = calculate_first_sets(augmented_grammar)
    start_production = augmented_grammar.productions[0]
    start_state = closure_lr1(
        {LR1Item(start_production, 0, EOF)},
        augmented_grammar,
        first_sets,
    )

    states: list[LR1State] = [start_state]
    state_by_items: dict[frozenset[LR1Item], int] = {start_state.items: 0}
    transitions: dict[tuple[int, Symbol], int] = {}
    pending = deque([0])

    while pending:
        source_id = pending.popleft()
        state = states[source_id]

        for symbol in sorted(state.next_symbols(), key=_symbol_sort_key):
            target_state = goto_lr1(state, symbol, augmented_grammar, first_sets)
            if not target_state.items:
                continue

            target_id = state_by_items.get(target_state.items)
            if target_id is None:
                target_id = len(states)
                states.append(target_state)
                state_by_items[target_state.items] = target_id
                pending.append(target_id)

            transitions[(source_id, symbol)] = target_id

    return LR1Automaton(augmented_grammar, tuple(states), transitions)


def build_lalr_automaton(grammar: Grammar) -> LALRAutomaton:
    """Merge canonical LR(1) states with equal LR(0) cores."""

    canonical = build_lr1_automaton(grammar)
    core_to_merged_id: dict[frozenset[tuple[Production, int]], int] = {}
    canonical_to_merged: dict[int, int] = {}
    merged_items: list[set[LR1Item]] = []

    for state_id, state in enumerate(canonical.states):
        merged_id = core_to_merged_id.get(state.core)
        if merged_id is None:
            merged_id = len(merged_items)
            core_to_merged_id[state.core] = merged_id
            merged_items.append(set())
        canonical_to_merged[state_id] = merged_id
        merged_items[merged_id].update(state.items)

    merged_states = tuple(
        LR1State(items, canonical.grammar)
        for items in merged_items
    )
    merged_transitions: dict[tuple[int, Symbol], int] = {}

    for (source, symbol), target in canonical.transitions.items():
        merged_source = canonical_to_merged[source]
        merged_target = canonical_to_merged[target]
        key = (merged_source, symbol)
        existing = merged_transitions.get(key)
        if existing is not None and existing != merged_target:
            raise ValueError("Inconsistent LALR transition while merging LR(1) cores.")
        merged_transitions[key] = merged_target

    return LALRAutomaton(canonical.grammar, merged_states, merged_transitions, canonical)


def build_lalr_table(
    grammar: Grammar,
    *,
    raise_on_conflicts: bool = False,
) -> LALRParsingTable:
    """Build LALR ACTION/GOTO tables."""

    automaton = build_lalr_automaton(grammar)
    action: dict[tuple[int, Terminal], LALRAction] = {}
    goto_table: dict[tuple[int, NonTerminal], int] = {}
    conflicts: list[LALRConflict] = []
    augmented_start = automaton.grammar.start_symbol

    for (source, symbol), target in automaton.transitions.items():
        if isinstance(symbol, Terminal):
            _set_action(
                action,
                conflicts,
                source,
                symbol,
                LALRAction.shift(target),
            )
        elif isinstance(symbol, NonTerminal):
            goto_table[(source, symbol)] = target

    for state_id, state in enumerate(automaton.states):
        for item in state.items:
            if not item.is_complete:
                continue

            if item.production.lhs == augmented_start and item.lookahead == EOF:
                _set_action(action, conflicts, state_id, EOF, LALRAction.accept())
                continue

            if item.production.lhs == augmented_start:
                continue

            _set_action(
                action,
                conflicts,
                state_id,
                item.lookahead,
                LALRAction.reduce(item.production),
            )

    table = LALRParsingTable(action, goto_table, tuple(conflicts), automaton)
    if raise_on_conflicts and conflicts:
        raise LALRConflictError(conflicts)
    return table


def _set_action(
    table: dict[tuple[int, Terminal], LALRAction],
    conflicts: list[LALRConflict],
    state: int,
    lookahead: Terminal,
    incoming: LALRAction,
) -> None:
    key = (state, lookahead)
    existing = table.get(key)

    if existing is None:
        table[key] = incoming
        return

    if existing == incoming:
        return

    conflicts.append(
        LALRConflict(_conflict_kind(existing, incoming), state, lookahead, existing, incoming)
    )


def _conflict_kind(existing: LALRAction, incoming: LALRAction) -> str:
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

    raise TypeError("LALR parser input must contain token-like objects, Terminal, or str values.")


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
        raise ValueError("Invalid LALR stack: top entry is not a state.")
    return state


def _stack_entry_name(entry: int | Symbol) -> str:
    if isinstance(entry, int):
        return str(entry)
    return entry.name


def _format_production(production: Production) -> str:
    rhs = " ".join(symbol.name for symbol in production.rhs)
    return f"{production.lhs.name} -> {rhs or 'epsilon'}"


def _symbol_sort_key(symbol: Symbol) -> tuple[int, str]:
    return (0 if isinstance(symbol, NonTerminal) else 1, symbol.name)
