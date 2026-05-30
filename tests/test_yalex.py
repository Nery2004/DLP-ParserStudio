import pytest

from dlp_parserstudio.lexer.yalex import LexicalError, LexerRule, Token, YALexLexer


def build_math_lexer() -> YALexLexer:
    return YALexLexer(
        [
            LexerRule("NUMBER", r"\d+"),
            LexerRule("PLUS", r"\+"),
            LexerRule("WS", r"\s+", skip=True),
        ]
    )


def test_tokenize_basic_math_expression() -> None:
    lexer = build_math_lexer()

    assert lexer.tokenize("12 + 7") == [
        Token("NUMBER", "12", 1, 1),
        Token("PLUS", "+", 1, 4),
        Token("NUMBER", "7", 1, 6),
    ]


def test_skips_whitespace_tokens() -> None:
    lexer = build_math_lexer()

    tokens = lexer.tokenize("  12\t+\n7")

    assert [token.type for token in tokens] == ["NUMBER", "PLUS", "NUMBER"]
    assert tokens[-1] == Token("NUMBER", "7", 2, 1)


def test_lexical_error_reports_invalid_character_location() -> None:
    lexer = build_math_lexer()

    with pytest.raises(LexicalError) as error:
        lexer.tokenize("12 @ 7")

    assert error.value.character == "@"
    assert error.value.line == 1
    assert error.value.column == 4
