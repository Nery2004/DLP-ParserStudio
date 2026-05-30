"""Regex-based lexer inspired by YALex token definitions."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Pattern


@dataclass(frozen=True)
class Token:
    """Token produced by the lexer."""

    type: str
    lexeme: str
    line: int
    column: int


@dataclass(frozen=True, init=False)
class LexerRule:
    """Lexer rule with priority defined by its position in the rules list."""

    type: str
    pattern: str
    skip: bool = False
    regex: Pattern[str] = field(init=False, repr=False, compare=False)

    def __init__(
        self,
        type: str | None = None,
        pattern: str | None = None,
        skip: bool = False,
        *,
        name: str | None = None,
    ) -> None:
        token_type = type if type is not None else name
        if type is not None and name is not None and type != name:
            raise ValueError("Lexer rule type and name must match when both are provided.")
        if not token_type:
            raise ValueError("Lexer rule type must be a non-empty string.")
        if not pattern:
            raise ValueError("Lexer rule pattern must be a non-empty string.")

        object.__setattr__(self, "type", token_type)
        object.__setattr__(self, "pattern", pattern)
        object.__setattr__(self, "skip", skip)
        object.__setattr__(self, "regex", re.compile(pattern))

    @property
    def name(self) -> str:
        return self.type


class LexicalError(ValueError):
    """Raised when the lexer cannot match a character at the current position."""

    def __init__(self, character: str, line: int, column: int) -> None:
        self.character = character
        self.line = line
        self.column = column
        super().__init__(
            f"Lexical error at line {line}, column {column}: unexpected character {character!r}."
        )


class YALexLexer:
    """Tokenizes text using ordered regular-expression rules."""

    def __init__(self, rules: Iterable[LexerRule]) -> None:
        self.rules = list(rules)
        if not self.rules:
            raise ValueError("YALexLexer requires at least one lexer rule.")

    def tokenize(self, text: str) -> list[Token]:
        tokens: list[Token] = []
        position = 0
        line = 1
        column = 1

        while position < len(text):
            match = self._best_match(text, position)

            if match is None:
                raise LexicalError(text[position], line, column)

            rule, lexeme = match
            token_line = line
            token_column = column

            line, column = _advance_position(lexeme, line, column)
            position += len(lexeme)

            if rule.skip:
                continue

            tokens.append(Token(rule.type, lexeme, token_line, token_column))

        return tokens

    def _best_match(self, text: str, position: int) -> tuple[LexerRule, str] | None:
        best_rule: LexerRule | None = None
        best_lexeme = ""

        for rule in self.rules:
            match = rule.regex.match(text, position)
            if match is None:
                continue

            lexeme = match.group(0)
            if not lexeme:
                continue

            if len(lexeme) > len(best_lexeme):
                best_rule = rule
                best_lexeme = lexeme

        if best_rule is None:
            return None

        return best_rule, best_lexeme


def _advance_position(lexeme: str, line: int, column: int) -> tuple[int, int]:
    for character in lexeme:
        if character == "\n":
            line += 1
            column = 1
        else:
            column += 1

    return line, column
