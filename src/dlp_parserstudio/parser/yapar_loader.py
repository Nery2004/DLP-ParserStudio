"""Loader for the educational YAPar grammar format."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dlp_parserstudio.core.grammar import Grammar, NonTerminal, Symbol, Terminal

EPSILON_NAME = "epsilon"


class YaparLoaderError(ValueError):
    """Raised when a .yapar file cannot be converted into a Grammar."""

    def __init__(self, message: str, line: int, column: int) -> None:
        self.line = line
        self.column = column
        super().__init__(f"{message} at line {line}, column {column}.")


@dataclass(frozen=True)
class _LocatedToken:
    value: str
    line: int
    column: int


@dataclass(frozen=True)
class _RawProduction:
    lhs: _LocatedToken
    alternatives: tuple[tuple[_LocatedToken, ...], ...]


def load_yapar(path: str | Path) -> Grammar:
    """Load a .yapar file from disk."""

    source_path = Path(path)
    return loads_yapar(source_path.read_text(encoding="utf-8"))


def loads_yapar(text: str) -> Grammar:
    """Parse .yapar source text and return a Grammar instance."""

    lines = text.splitlines()
    separator_index = _find_separator(lines)
    declarations = lines[:separator_index]
    body = lines[separator_index + 1 :]

    tokens, _ignored_tokens, start_symbol, start_location = _parse_declarations(
        declarations
    )
    productions = _parse_productions(body, first_line=separator_index + 2)

    if start_symbol is None or start_location is None:
        raise YaparLoaderError(
            "Missing required %start declaration",
            separator_index + 1,
            1,
        )
    if not productions:
        raise YaparLoaderError(
            "Expected at least one production after %%",
            separator_index + 1,
            1,
        )

    return _build_grammar(tokens, start_symbol, start_location, productions)


class YaparLoader:
    """Object-oriented facade for loading educational YAPar grammars."""

    def load(self, path: str | Path) -> Grammar:
        return load_yapar(path)

    def loads(self, text: str) -> Grammar:
        return loads_yapar(text)


def _find_separator(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if _strip_comment(line).strip() == "%%":
            return index

    line = len(lines) if lines else 1
    column = len(lines[-1]) + 1 if lines else 1
    raise YaparLoaderError("Missing required %% separator", line, column)


def _parse_declarations(
    lines: list[str],
) -> tuple[set[str], set[str], str | None, _LocatedToken | None]:
    tokens: set[str] = set()
    ignored_tokens: set[str] = set()
    start_symbol: str | None = None
    start_location: _LocatedToken | None = None

    for line_number, line in enumerate(lines, start=1):
        clean_line = _strip_comment(line)
        stripped = clean_line.strip()
        if not stripped:
            continue

        parts = stripped.split()
        directive = parts[0]
        directive_column = clean_line.index(directive) + 1

        if directive == "%token":
            if len(parts) == 1:
                raise YaparLoaderError(
                    "Expected at least one token name",
                    line_number,
                    directive_column,
                )
            for name in parts[1:]:
                _validate_identifier(name, line_number, _column_of(clean_line, name))
                tokens.add(name)
        elif directive == "%ignore":
            if len(parts) == 1:
                raise YaparLoaderError(
                    "Expected at least one ignored token name",
                    line_number,
                    directive_column,
                )
            for name in parts[1:]:
                _validate_identifier(name, line_number, _column_of(clean_line, name))
                ignored_tokens.add(name)
        elif directive == "%start":
            if len(parts) != 2:
                column = (
                    _column_of(clean_line, parts[2])
                    if len(parts) > 2
                    else directive_column + len(directive)
                )
                raise YaparLoaderError(
                    "Expected exactly one start symbol",
                    line_number,
                    column,
                )
            _validate_identifier(parts[1], line_number, _column_of(clean_line, parts[1]))
            start_symbol = parts[1]
            start_location = _LocatedToken(
                parts[1],
                line_number,
                _column_of(clean_line, parts[1]),
            )
        elif directive.startswith("%"):
            raise YaparLoaderError(
                f"Unknown directive {directive!r}",
                line_number,
                directive_column,
            )
        else:
            raise YaparLoaderError(
                "Expected a declaration before %%",
                line_number,
                directive_column,
            )

    if start_symbol is None:
        return tokens, ignored_tokens, None, None

    return tokens, ignored_tokens, start_symbol, start_location


def _parse_productions(lines: list[str], first_line: int) -> list[_RawProduction]:
    tokens = _scan_body_tokens(lines, first_line)
    productions: list[_RawProduction] = []
    index = 0

    while index < len(tokens):
        lhs = tokens[index]
        if lhs.value in {":", "|", ";"}:
            raise YaparLoaderError("Expected production left-hand side", lhs.line, lhs.column)
        _validate_identifier(lhs.value, lhs.line, lhs.column)
        index += 1

        if index >= len(tokens):
            raise YaparLoaderError(
                "Expected ':' after production left-hand side",
                lhs.line,
                lhs.column,
            )

        colon = tokens[index]
        if colon.value != ":":
            raise YaparLoaderError(
                "Expected ':' after production left-hand side",
                colon.line,
                colon.column,
            )
        index += 1

        alternatives: list[tuple[_LocatedToken, ...]] = []
        current: list[_LocatedToken] = []

        while index < len(tokens) and tokens[index].value != ";":
            token = tokens[index]

            if token.value == "|":
                if not current:
                    raise YaparLoaderError("Expected symbols before '|'", token.line, token.column)
                alternatives.append(tuple(current))
                current = []
                index += 1
                continue

            if token.value == ":":
                raise YaparLoaderError("Unexpected ':' inside production", token.line, token.column)

            _validate_identifier(token.value, token.line, token.column)
            current.append(token)
            index += 1

        if index >= len(tokens):
            line, column = _end_location(lines, first_line)
            raise YaparLoaderError("Expected ';' at the end of production", line, column)

        semicolon = tokens[index]
        if not current:
            raise YaparLoaderError("Expected symbols before ';'", semicolon.line, semicolon.column)

        alternatives.append(tuple(current))
        productions.append(_RawProduction(lhs, tuple(alternatives)))
        index += 1

    return productions


def _scan_body_tokens(lines: list[str], first_line: int) -> list[_LocatedToken]:
    tokens: list[_LocatedToken] = []

    for offset, line in enumerate(lines):
        line_number = first_line + offset
        column = 1

        while column <= len(line):
            character = line[column - 1]

            if character == "#":
                break
            if character.isspace():
                column += 1
                continue
            if character in ":|;":
                tokens.append(_LocatedToken(character, line_number, column))
                column += 1
                continue
            if _is_identifier_start(character):
                start_column = column
                value = character
                column += 1
                while column <= len(line) and _is_identifier_part(line[column - 1]):
                    value += line[column - 1]
                    column += 1
                tokens.append(_LocatedToken(value, line_number, start_column))
                continue

            raise YaparLoaderError(
                f"Unexpected character {character!r} in production section",
                line_number,
                column,
            )

    return tokens


def _build_grammar(
    token_names: set[str],
    start_symbol: str,
    start_location: _LocatedToken,
    productions: list[_RawProduction],
) -> Grammar:
    non_terminal_names = {production.lhs.value for production in productions}

    if start_symbol not in non_terminal_names:
        raise YaparLoaderError(
            f"Start symbol {start_symbol!r} does not have a production",
            start_location.line,
            start_location.column,
        )

    grammar = Grammar(
        non_terminals={NonTerminal(name) for name in non_terminal_names},
        terminals={Terminal(name) for name in token_names},
        start_symbol=NonTerminal(start_symbol),
    )

    for production in productions:
        for alternative in production.alternatives:
            grammar.agregar_produccion(
                production.lhs.value,
                _resolve_rhs(alternative, non_terminal_names, token_names),
            )

    return grammar


def _resolve_rhs(
    symbols: tuple[_LocatedToken, ...],
    non_terminal_names: set[str],
    token_names: set[str],
) -> tuple[Symbol, ...]:
    if len(symbols) == 1 and symbols[0].value == EPSILON_NAME:
        return ()

    for symbol in symbols:
        if symbol.value == EPSILON_NAME:
            raise YaparLoaderError(
                "epsilon must appear alone in an alternative",
                symbol.line,
                symbol.column,
            )

    resolved: list[Symbol] = []
    for symbol in symbols:
        if symbol.value in non_terminal_names:
            resolved.append(NonTerminal(symbol.value))
        elif symbol.value in token_names:
            resolved.append(Terminal(symbol.value))
        else:
            raise YaparLoaderError(
                f"Symbol {symbol.value!r} is neither a production lhs nor a declared token",
                symbol.line,
                symbol.column,
            )

    return tuple(resolved)


def _strip_comment(line: str) -> str:
    return line.split("#", 1)[0]


def _validate_identifier(value: str, line: int, column: int) -> None:
    if not value or not _is_identifier_start(value[0]):
        raise YaparLoaderError(f"Invalid symbol name {value!r}", line, column)
    if not all(_is_identifier_part(character) for character in value[1:]):
        raise YaparLoaderError(f"Invalid symbol name {value!r}", line, column)


def _column_of(line: str, value: str) -> int:
    return line.index(value) + 1


def _end_location(lines: list[str], first_line: int) -> tuple[int, int]:
    if not lines:
        return first_line, 1
    return first_line + len(lines) - 1, len(lines[-1]) + 1


def _is_identifier_start(character: str) -> bool:
    return character.isalpha() or character == "_"


def _is_identifier_part(character: str) -> bool:
    return character.isalnum() or character in {"_", "'"}
