from pathlib import Path

import pytest

from dlp_parserstudio.lexer.yalex import LexicalError, LexerRule, YALexLexer
from dlp_parserstudio.parser.ll1 import LL1Parser, LL1ConflictError
from dlp_parserstudio.parser.slr import SLRParser
from dlp_parserstudio.parser.yapar_loader import load_yapar


JSX_DIR = Path("examples/jsx_react")


def build_jsx_lexer() -> YALexLexer:
    return YALexLexer(
        [
            LexerRule("OPEN_CLOSE", r"</"),
            LexerRule("OPEN", r"<"),
            LexerRule("SELF_CLOSE", r"/>"),
            LexerRule("CLOSE", r">"),
            LexerRule("EQUALS", r"="),
            LexerRule("STRING", r'"[^"]*"'),
            LexerRule("COMPONENT", r"[A-Z][A-Za-z0-9_]*"),
            LexerRule("TAG", r"[a-z][A-Za-z0-9_]*"),
            LexerRule("TEXT", r"[A-Za-z0-9][A-Za-z0-9.,!?-]*"),
            LexerRule("WS", r"\s+", skip=True),
        ]
    )


def input_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_jsx_valid_inputs_parse() -> None:
    lexer = build_jsx_lexer()
    parser = SLRParser(load_yapar(JSX_DIR / "jsx_subset.yapar"))

    for line in input_lines(JSX_DIR / "valid_inputs.txt"):
        result = parser.parse(lexer.tokenize(line))

        assert result.accepted, line


def test_jsx_invalid_inputs_fail_lexically_or_syntactically() -> None:
    lexer = build_jsx_lexer()
    parser = SLRParser(load_yapar(JSX_DIR / "jsx_subset.yapar"))

    for line in input_lines(JSX_DIR / "invalid_inputs.txt"):
        try:
            tokens = lexer.tokenize(line)
        except LexicalError:
            continue

        assert not parser.parse(tokens).accepted, line


def test_jsx_self_closing_tag_tokenizes_and_parses() -> None:
    lexer = build_jsx_lexer()
    parser = SLRParser(load_yapar(JSX_DIR / "jsx_subset.yapar"))

    tokens = lexer.tokenize('<Input name="email" />')
    result = parser.parse(tokens)

    assert [(token.type, token.lexeme) for token in tokens] == [
        ("OPEN", "<"),
        ("COMPONENT", "Input"),
        ("TAG", "name"),
        ("EQUALS", "="),
        ("STRING", '"email"'),
        ("SELF_CLOSE", "/>"),
    ]
    assert result.accepted


def test_jsx_grammar_is_not_ll1_but_is_slr_for_this_subset() -> None:
    grammar = load_yapar(JSX_DIR / "jsx_subset.yapar")

    with pytest.raises(LL1ConflictError):
        LL1Parser(grammar)

    assert SLRParser(grammar).parse(build_jsx_lexer().tokenize("<App></App>")).accepted
