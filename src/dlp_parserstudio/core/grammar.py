"""Formal grammar model used by DLP-ParserStudio.

This module represents a grammar as G = (V, T, P, S):

* V: non-terminal symbols
* T: terminal symbols
* P: productions
* S: start symbol
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class Symbol:
    """Base class for grammar symbols."""

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("A symbol name must be a non-empty string.")

    @property
    def is_terminal(self) -> bool:
        return isinstance(self, Terminal)

    @property
    def is_non_terminal(self) -> bool:
        return isinstance(self, NonTerminal)

    def __str__(self) -> str:
        return self.name


class Terminal(Symbol):
    """Terminal symbol from T."""


class NonTerminal(Symbol):
    """Non-terminal symbol from V."""


@dataclass(frozen=True)
class Production:
    """Production rule with a non-terminal left-hand side."""

    lhs: NonTerminal
    rhs: tuple[Symbol, ...] = field(default_factory=tuple)

    def __init__(self, lhs: NonTerminal, rhs: Iterable[Symbol] = ()) -> None:
        if not isinstance(lhs, NonTerminal):
            raise TypeError("Production lhs must be a NonTerminal.")

        rhs_tuple = tuple(rhs)
        if not all(isinstance(symbol, Symbol) for symbol in rhs_tuple):
            raise TypeError("Production rhs must contain only Symbol instances.")

        object.__setattr__(self, "lhs", lhs)
        object.__setattr__(self, "rhs", rhs_tuple)

    def __str__(self) -> str:
        rhs = " ".join(symbol.name for symbol in self.rhs) if self.rhs else "epsilon"
        return f"{self.lhs} -> {rhs}"


@dataclass
class Grammar:
    """Formal grammar G = (V, T, P, S)."""

    non_terminals: set[NonTerminal]
    terminals: set[Terminal]
    start_symbol: NonTerminal
    productions: list[Production] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.non_terminals = set(self.non_terminals)
        self.terminals = set(self.terminals)
        self.productions = list(self.productions)

        if not isinstance(self.start_symbol, NonTerminal):
            raise TypeError("Grammar start_symbol must be a NonTerminal.")
        if self.start_symbol not in self.non_terminals:
            self.non_terminals.add(self.start_symbol)

        for production in self.productions:
            self._register_production_symbols(production)

    @property
    def V(self) -> set[NonTerminal]:
        return set(self.non_terminals)

    @property
    def T(self) -> set[Terminal]:
        return set(self.terminals)

    @property
    def P(self) -> list[Production]:
        return list(self.productions)

    @property
    def S(self) -> NonTerminal:
        return self.start_symbol

    def agregar_produccion(
        self,
        lhs: NonTerminal | str,
        rhs: Iterable[Symbol | str] = (),
    ) -> Production:
        production = Production(
            self._as_non_terminal(lhs),
            tuple(self._as_known_symbol(symbol) for symbol in rhs),
        )
        self.productions.append(production)
        self._register_production_symbols(production)
        return production

    def add_production(
        self,
        lhs: NonTerminal | str,
        rhs: Iterable[Symbol | str] = (),
    ) -> Production:
        return self.agregar_produccion(lhs, rhs)

    def producciones_de(self, non_terminal: NonTerminal | str) -> list[Production]:
        target = self._as_non_terminal(non_terminal)
        return [production for production in self.productions if production.lhs == target]

    def productions_for(self, non_terminal: NonTerminal | str) -> list[Production]:
        return self.producciones_de(non_terminal)

    def es_terminal(self, symbol: Symbol | str) -> bool:
        if isinstance(symbol, Terminal):
            return True
        if isinstance(symbol, NonTerminal):
            return False
        return any(terminal.name == symbol for terminal in self.terminals)

    def es_no_terminal(self, symbol: Symbol | str) -> bool:
        if isinstance(symbol, NonTerminal):
            return True
        if isinstance(symbol, Terminal):
            return False
        return any(non_terminal.name == symbol for non_terminal in self.non_terminals)

    def is_terminal(self, symbol: Symbol | str) -> bool:
        return self.es_terminal(symbol)

    def is_non_terminal(self, symbol: Symbol | str) -> bool:
        return self.es_no_terminal(symbol)

    def aumentar(self) -> Grammar:
        original_start = self.start_symbol
        augmented_start = NonTerminal(self._unique_augmented_name(original_start.name))
        augmented_production = Production(augmented_start, (original_start,))

        return Grammar(
            non_terminals={augmented_start, *self.non_terminals},
            terminals=set(self.terminals),
            start_symbol=augmented_start,
            productions=[augmented_production, *self.productions],
        )

    def augment(self) -> Grammar:
        return self.aumentar()

    @classmethod
    def desde_estructura(cls, data: Mapping[str, Any]) -> Grammar:
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Grammar:
        if "start" not in data:
            raise ValueError("Grammar data must include a 'start' symbol.")
        if "productions" not in data:
            raise ValueError("Grammar data must include 'productions'.")

        production_entries = _normalize_production_entries(data["productions"])
        start_name = _symbol_name(data["start"])

        non_terminal_names = set(_names_from(data.get("non_terminals", ())))
        non_terminal_names.update(lhs for lhs, _rhs in production_entries)
        non_terminal_names.add(start_name)

        explicit_terminal_names = set(_names_from(data.get("terminals", ())))
        terminal_names = set(explicit_terminal_names)

        for _lhs, rhs in production_entries:
            for symbol in rhs:
                if isinstance(symbol, Terminal):
                    terminal_names.add(symbol.name)
                elif isinstance(symbol, NonTerminal):
                    non_terminal_names.add(symbol.name)
                else:
                    name = _symbol_name(symbol)
                    if name not in non_terminal_names:
                        terminal_names.add(name)

        non_terminals = {NonTerminal(name) for name in non_terminal_names}
        terminals = {Terminal(name) for name in terminal_names}
        grammar = cls(
            non_terminals=non_terminals,
            terminals=terminals,
            start_symbol=NonTerminal(start_name),
        )

        for lhs, rhs in production_entries:
            grammar.agregar_produccion(lhs, rhs)

        return grammar

    def _register_production_symbols(self, production: Production) -> None:
        self.non_terminals.add(production.lhs)
        for symbol in production.rhs:
            if isinstance(symbol, Terminal):
                self.terminals.add(symbol)
            elif isinstance(symbol, NonTerminal):
                self.non_terminals.add(symbol)

    def _as_non_terminal(self, value: NonTerminal | str) -> NonTerminal:
        if isinstance(value, NonTerminal):
            return value
        if isinstance(value, Terminal):
            raise TypeError("Expected a non-terminal symbol, got a terminal.")
        name = _symbol_name(value)
        for non_terminal in self.non_terminals:
            if non_terminal.name == name:
                return non_terminal
        return NonTerminal(name)

    def _as_known_symbol(self, value: Symbol | str) -> Symbol:
        if isinstance(value, Symbol):
            return value

        name = _symbol_name(value)
        for non_terminal in self.non_terminals:
            if non_terminal.name == name:
                return non_terminal
        for terminal in self.terminals:
            if terminal.name == name:
                return terminal
        return Terminal(name)

    def _unique_augmented_name(self, base_name: str) -> str:
        existing_names = {symbol.name for symbol in self.non_terminals}
        candidate = f"{base_name}'"
        while candidate in existing_names:
            candidate = f"{candidate}'"
        return candidate


def _normalize_production_entries(
    productions: Mapping[Any, Iterable[Iterable[Symbol | str]]] | Iterable[Any],
) -> list[tuple[str, tuple[Symbol | str, ...]]]:
    entries: list[tuple[str, tuple[Symbol | str, ...]]] = []

    if isinstance(productions, Mapping):
        for lhs, alternatives in productions.items():
            lhs_name = _symbol_name(lhs)
            for rhs in alternatives:
                entries.append((lhs_name, _normalize_rhs(rhs)))
        return entries

    for production in productions:
        if isinstance(production, Production):
            entries.append((production.lhs.name, production.rhs))
        else:
            lhs, rhs = production
            entries.append((_symbol_name(lhs), _normalize_rhs(rhs)))

    return entries


def _normalize_rhs(rhs: Iterable[Symbol | str] | Symbol | str) -> tuple[Symbol | str, ...]:
    if isinstance(rhs, Symbol):
        return (rhs,)
    if isinstance(rhs, str):
        return (rhs,)
    return tuple(rhs)


def _names_from(values: Iterable[Symbol | str]) -> set[str]:
    return {_symbol_name(value) for value in values}


def _symbol_name(value: Symbol | str) -> str:
    if isinstance(value, Symbol):
        return value.name
    if isinstance(value, str) and value:
        return value
    raise ValueError("Symbol names must be non-empty strings.")
