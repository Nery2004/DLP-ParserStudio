"""LR(0) items, states, canonical automaton construction, and DOT export."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from dlp_parserstudio.core.grammar import Grammar, NonTerminal, Production, Symbol


@dataclass(frozen=True)
class LR0Item:
    """LR(0) item of the form A -> alpha . beta."""

    production: Production
    dot: int = 0

    def __post_init__(self) -> None:
        if self.dot < 0 or self.dot > len(self.production.rhs):
            raise ValueError("LR(0) item dot position is outside the production body.")

    @property
    def next_symbol(self) -> Symbol | None:
        if self.is_complete:
            return None
        return self.production.rhs[self.dot]

    @property
    def is_complete(self) -> bool:
        return self.dot == len(self.production.rhs)

    def advance(self) -> LR0Item:
        if self.is_complete:
            raise ValueError("Cannot advance a complete LR(0) item.")
        return LR0Item(self.production, self.dot + 1)

    def __str__(self) -> str:
        rhs = [symbol.name for symbol in self.production.rhs]
        rhs.insert(self.dot, ".")
        return f"{self.production.lhs.name} -> {' '.join(rhs)}"


@dataclass(frozen=True, init=False)
class LR0State:
    """Set of LR(0) items."""

    items: frozenset[LR0Item]
    grammar: Grammar | None = field(default=None, compare=False, hash=False, repr=False)

    def __init__(
        self,
        items: Iterable[LR0Item],
        grammar: Grammar | None = None,
    ) -> None:
        object.__setattr__(self, "items", frozenset(items))
        object.__setattr__(self, "grammar", grammar)

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
class LR0Automaton:
    """Canonical LR(0) automaton for an augmented grammar."""

    grammar: Grammar
    states: tuple[LR0State, ...]
    transitions: Mapping[tuple[int, Symbol], int]

    def transition(self, state_id: int, symbol: Symbol) -> int | None:
        return self.transitions.get((state_id, symbol))

    def to_dot(self) -> str:
        lines = [
            "digraph LR0 {",
            "  rankdir=LR;",
            "  node [shape=box];",
        ]

        for index, state in enumerate(self.states):
            label = "\\n".join(_dot_escape(str(item)) for item in _sorted_items(state.items))
            lines.append(f'  I{index} [label="I{index}\\n{label}"];')

        for (source, symbol), target in sorted(
            self.transitions.items(),
            key=lambda item: (item[0][0], _symbol_sort_key(item[0][1]), item[1]),
        ):
            lines.append(
                f'  I{source} -> I{target} [label="{_dot_escape(symbol.name)}"];'
            )

        lines.append("}")
        return "\n".join(lines)

    def export_dot(self) -> str:
        return self.to_dot()


def closure(items: Iterable[LR0Item] | LR0State, grammar: Grammar | None = None) -> LR0State:
    """Compute the LR(0) closure for a set of items."""

    if isinstance(items, LR0State):
        grammar = grammar or items.grammar
        item_set = set(items.items)
    else:
        item_set = set(items)

    if grammar is None:
        raise ValueError("closure requires a Grammar.")

    changed = True
    while changed:
        changed = False

        for item in tuple(item_set):
            next_symbol = item.next_symbol
            if not isinstance(next_symbol, NonTerminal):
                continue

            for production in grammar.producciones_de(next_symbol):
                candidate = LR0Item(production, 0)
                if candidate not in item_set:
                    item_set.add(candidate)
                    changed = True

    return LR0State(item_set, grammar)


def goto(
    state: LR0State | Iterable[LR0Item],
    symbol: Symbol,
    grammar: Grammar | None = None,
) -> LR0State:
    """Compute GOTO(state, symbol)."""

    if isinstance(state, LR0State):
        grammar = grammar or state.grammar
        items = state.items
    else:
        items = frozenset(state)

    if grammar is None:
        raise ValueError("goto requires a Grammar.")

    advanced_items = [
        item.advance()
        for item in items
        if item.next_symbol == symbol
    ]
    return closure(advanced_items, grammar)


def build_lr0_automaton(grammar: Grammar) -> LR0Automaton:
    """Build the full canonical LR(0) automaton using G' with S' -> S."""

    augmented_grammar = grammar.aumentar()
    start_production = augmented_grammar.productions[0]
    start_state = closure({LR0Item(start_production)}, augmented_grammar)

    states: list[LR0State] = [start_state]
    state_by_items: dict[frozenset[LR0Item], int] = {start_state.items: 0}
    transitions: dict[tuple[int, Symbol], int] = {}
    pending = deque([0])

    while pending:
        source_id = pending.popleft()
        state = states[source_id]

        for symbol in sorted(state.next_symbols(), key=_symbol_sort_key):
            target_state = goto(state, symbol, augmented_grammar)
            if not target_state.items:
                continue

            target_id = state_by_items.get(target_state.items)
            if target_id is None:
                target_id = len(states)
                states.append(target_state)
                state_by_items[target_state.items] = target_id
                pending.append(target_id)

            transitions[(source_id, symbol)] = target_id

    return LR0Automaton(augmented_grammar, tuple(states), transitions)


def _sorted_items(items: Iterable[LR0Item]) -> list[LR0Item]:
    return sorted(
        items,
        key=lambda item: (
            item.production.lhs.name,
            tuple(symbol.name for symbol in item.production.rhs),
            item.dot,
        ),
    )


def _symbol_sort_key(symbol: Symbol) -> tuple[int, str]:
    return (0 if isinstance(symbol, NonTerminal) else 1, symbol.name)


def _dot_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
