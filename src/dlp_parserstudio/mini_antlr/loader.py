"""Loader for a small educational subset of ANTLR grammars."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from dlp_parserstudio.core.grammar import Grammar, NonTerminal, Terminal
from dlp_parserstudio.lexer.yalex import LexerRule


@dataclass(frozen=True)
class MiniANTLRSpec:
    """Converted Mini-ANTLR grammar."""

    name: str
    lexer_rules: tuple[LexerRule, ...]
    grammar: Grammar


class MiniANTLRLoaderError(ValueError):
    """Raised when a Mini-ANTLR source cannot be loaded."""


class MiniANTLRLoader:
    """Object-oriented facade for Mini-ANTLR loading."""

    def load(self, path: str | Path) -> MiniANTLRSpec:
        return load_mini_antlr(path)

    def loads(self, text: str) -> MiniANTLRSpec:
        return loads_mini_antlr(text)


@dataclass(frozen=True)
class _Rule:
    name: str
    body: str


def load_mini_antlr(path: str | Path) -> MiniANTLRSpec:
    """Load a Mini-ANTLR source file from disk."""

    source_path = Path(path)
    return loads_mini_antlr(source_path.read_text(encoding="utf-8"))


def loads_mini_antlr(text: str) -> MiniANTLRSpec:
    """Convert Mini-ANTLR source text into YALex rules and a Grammar."""

    source = _strip_comments(text)
    statements = _split_statements(source)
    if not statements:
        raise MiniANTLRLoaderError("Mini-ANTLR source is empty.")

    grammar_name = _parse_header(statements[0])
    raw_rules = [_parse_rule(statement) for statement in statements[1:]]
    if not raw_rules:
        raise MiniANTLRLoaderError("Mini-ANTLR source must define at least one rule.")

    lexer_rule_defs = [rule for rule in raw_rules if _is_lexer_rule(rule.name)]
    parser_rule_defs = [rule for rule in raw_rules if _is_parser_rule(rule.name)]

    if not lexer_rule_defs:
        raise MiniANTLRLoaderError("Mini-ANTLR source must define lexer rules.")
    if not parser_rule_defs:
        raise MiniANTLRLoaderError("Mini-ANTLR source must define parser rules.")

    token_names = {rule.name for rule in lexer_rule_defs}
    parser_names = {rule.name for rule in parser_rule_defs}
    lexer_rules = tuple(_build_lexer_rule(rule) for rule in lexer_rule_defs)
    skip_tokens = {rule.type for rule in lexer_rules if rule.skip}
    grammar = _build_grammar(parser_rule_defs, token_names, parser_names, skip_tokens)

    return MiniANTLRSpec(grammar_name, lexer_rules, grammar)


def _strip_comments(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        lines.append(line.split("//", 1)[0].split("#", 1)[0])
    return "\n".join(lines)


def _split_statements(source: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_quote = False
    in_charset = False
    escaped = False

    for character in source:
        current.append(character)

        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == "'" and not in_charset:
            in_quote = not in_quote
            continue
        if character == "[" and not in_quote:
            in_charset = True
            continue
        if character == "]" and in_charset:
            in_charset = False
            continue
        if character == ";" and not in_quote and not in_charset:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []

    trailing = "".join(current).strip()
    if trailing:
        raise MiniANTLRLoaderError("Expected ';' at the end of Mini-ANTLR statement.")

    return statements


def _parse_header(statement: str) -> str:
    match = re.fullmatch(r"grammar\s+([A-Za-z_][A-Za-z0-9_]*)\s*;", statement.strip())
    if match is None:
        raise MiniANTLRLoaderError("Mini-ANTLR source must start with 'grammar Name;'.")
    return match.group(1)


def _parse_rule(statement: str) -> _Rule:
    match = re.fullmatch(
        r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*?)\s*;\s*",
        statement,
        flags=re.DOTALL,
    )
    if match is None:
        raise MiniANTLRLoaderError(f"Malformed Mini-ANTLR rule: {statement!r}.")

    name = match.group(1)
    body = " ".join(match.group(2).strip().split())
    if not body:
        raise MiniANTLRLoaderError(f"Rule {name!r} must have a body.")
    return _Rule(name, body)


def _build_lexer_rule(rule: _Rule) -> LexerRule:
    body, skip = _split_skip_action(rule.body)
    return LexerRule(rule.name, _antlr_regex_to_python(body), skip=skip)


def _split_skip_action(body: str) -> tuple[str, bool]:
    match = re.fullmatch(r"(.*?)\s*->\s*skip\s*", body)
    if match is None:
        return body.strip(), False
    return match.group(1).strip(), True


def _antlr_regex_to_python(pattern: str) -> str:
    pattern = pattern.strip()
    if not pattern:
        raise MiniANTLRLoaderError("Lexer pattern cannot be empty.")

    if pattern.startswith("'") and pattern.endswith("'"):
        return re.escape(_decode_quoted_literal(pattern))

    return _remove_regex_whitespace(pattern)


def _decode_quoted_literal(value: str) -> str:
    inner = value[1:-1]
    return bytes(inner, "utf-8").decode("unicode_escape")


def _remove_regex_whitespace(pattern: str) -> str:
    cleaned: list[str] = []
    in_charset = False
    escaped = False

    for character in pattern:
        if escaped:
            cleaned.append(character)
            escaped = False
            continue
        if character == "\\":
            cleaned.append(character)
            escaped = True
            continue
        if character == "[":
            in_charset = True
            cleaned.append(character)
            continue
        if character == "]":
            in_charset = False
            cleaned.append(character)
            continue
        if character.isspace() and not in_charset:
            continue
        cleaned.append(character)

    return "".join(cleaned)


def _build_grammar(
    parser_rules: list[_Rule],
    token_names: set[str],
    parser_names: set[str],
    skip_tokens: set[str],
) -> Grammar:
    start_symbol = parser_rules[0].name
    grammar_token_names = token_names - skip_tokens
    terminals = {Terminal(name) for name in grammar_token_names}
    grammar = Grammar(
        non_terminals={NonTerminal(name) for name in parser_names},
        terminals=terminals,
        start_symbol=NonTerminal(start_symbol),
    )

    generated_counter = 0
    for rule in parser_rules:
        for alternative in _split_alternatives(rule.body):
            expanded_rhs, generated = _expand_parser_alternative(
                rule.name,
                alternative,
                grammar_token_names,
                parser_names,
                generated_counter,
            )
            generated_counter += len(generated)
            for generated_name, _generated_alternatives in generated:
                grammar.non_terminals.add(NonTerminal(generated_name))
            grammar.agregar_produccion(rule.name, expanded_rhs)
            for generated_name, generated_alternatives in generated:
                for generated_rhs in generated_alternatives:
                    grammar.agregar_produccion(generated_name, generated_rhs)

    return grammar


def _split_alternatives(body: str) -> list[str]:
    alternatives: list[str] = []
    current: list[str] = []
    depth = 0

    for token in _parser_tokens(body):
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
        if token == "|" and depth == 0:
            alternatives.append(" ".join(current).strip())
            current = []
            continue
        current.append(token)

    alternatives.append(" ".join(current).strip())
    return alternatives


def _expand_parser_alternative(
    owner: str,
    alternative: str,
    token_names: set[str],
    parser_names: set[str],
    generated_counter: int,
) -> tuple[list[str], list[tuple[str, list[list[str]]]]]:
    tokens = _parser_tokens(alternative)
    rhs: list[str] = []
    generated: list[tuple[str, list[list[str]]]] = []
    index = 0

    while index < len(tokens):
        token = tokens[index]

        if token == "(":
            group_tokens: list[str] = []
            index += 1
            while index < len(tokens) and tokens[index] != ")":
                if tokens[index] in {"(", ")", "|"}:
                    raise MiniANTLRLoaderError("Only simple '*' groups are supported.")
                group_tokens.append(tokens[index])
                index += 1
            if index >= len(tokens):
                raise MiniANTLRLoaderError("Unclosed parser group.")
            index += 1

            if index >= len(tokens) or tokens[index] != "*":
                raise MiniANTLRLoaderError("Only groups followed by '*' are supported.")
            index += 1

            if not group_tokens:
                raise MiniANTLRLoaderError("Empty '*' groups are not supported.")

            for group_token in group_tokens:
                _validate_parser_symbol(group_token, token_names, parser_names)

            generated_name = f"{owner}__repeat_{generated_counter + len(generated) + 1}"
            rhs.append(generated_name)
            generated.append(
                (
                    generated_name,
                    [
                        [*group_tokens, generated_name],
                        [],
                    ],
                )
            )
            parser_names.add(generated_name)
            continue

        if token in {")", "*"}:
            raise MiniANTLRLoaderError(f"Unexpected parser token {token!r}.")

        _validate_parser_symbol(token, token_names, parser_names)
        rhs.append(token)
        index += 1

    return rhs, generated


def _parser_tokens(body: str) -> list[str]:
    tokens: list[str] = []
    index = 0

    while index < len(body):
        character = body[index]

        if character.isspace():
            index += 1
            continue
        if character in {"(", ")", "|", "*"}:
            tokens.append(character)
            index += 1
            continue
        if character.isalpha() or character == "_":
            start = index
            index += 1
            while index < len(body) and (body[index].isalnum() or body[index] == "_"):
                index += 1
            tokens.append(body[start:index])
            continue

        raise MiniANTLRLoaderError(f"Unexpected parser character {character!r}.")

    return tokens


def _validate_parser_symbol(
    symbol: str,
    token_names: set[str],
    parser_names: set[str],
) -> None:
    if symbol in token_names or symbol in parser_names:
        return
    raise MiniANTLRLoaderError(f"Unknown parser symbol {symbol!r}.")


def _is_lexer_rule(name: str) -> bool:
    return name[0].isupper()


def _is_parser_rule(name: str) -> bool:
    return name[0].islower()
