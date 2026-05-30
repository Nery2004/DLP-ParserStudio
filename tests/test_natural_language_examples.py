from pathlib import Path

import pytest

from dlp_parserstudio.lexer.yalex import LexicalError, LexerRule, Token, YALexLexer
from dlp_parserstudio.parser.ll1 import LL1Parser
from dlp_parserstudio.parser.yapar_loader import load_yapar


NATURAL_LANGUAGE_DIR = Path("examples/natural_language")


SPANISH_TRANSLATION = {
    "donde": "donde",
    "cuando": "cuando",
    "estudiante": "estudiante",
    "profesor": "profesor",
    "compra": "compra",
    "lee": "lee",
    "libro": "libro",
    "cuaderno": "cuaderno",
}

QEQCHI_TRANSLATION = {
    "b'ar": "donde",
    "b’ar": "donde",
    "laa'in": "yo",
    "laa’in": "yo",
    "a'an": "el",
    "a’an": "el",
    "xnawb'al": "saber",
    "xnawb’al": "saber",
    "yehok": "decir",
    "chalk": "venir",
    "b'ichank": "cantar",
    "b’ichank": "cantar",
    "aatinob'aal": "idioma",
    "aatinob’aal": "idioma",
    "ochoch": "casa",
    "xul": "animal",
}


def build_spanish_lexer() -> YALexLexer:
    return YALexLexer(
        [
            LexerRule("PREGUNTA", r"donde|cuando"),
            LexerRule("SUJETO", r"estudiante|profesor"),
            LexerRule("ACCION", r"compra|lee"),
            LexerRule("OBJETO", r"libro|cuaderno"),
            LexerRule("WS", r"\s+", skip=True),
        ]
    )


def build_qeqchi_lexer() -> YALexLexer:
    return YALexLexer(
        [
            LexerRule("PREGUNTA", r"b['’]?ar"),
            LexerRule("SUJETO", r"laa['’]?in|a['’]?an"),
            LexerRule("ACCION", r"xnawb['’]?al|yehok|chalk|b['’]?ichank"),
            LexerRule("OBJETO", r"aatinob['’]?aal|ochoch|xul"),
            LexerRule("WS", r"\s+", skip=True),
        ]
    )


def parse_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def translate(tokens: list[Token], table: dict[str, str]) -> str:
    return " ".join(table[token.lexeme.lower()] for token in tokens)


def test_spanish_simple_valid_inputs_parse_and_translate() -> None:
    lexer = build_spanish_lexer()
    parser = LL1Parser(load_yapar(NATURAL_LANGUAGE_DIR / "spanish_simple.yapar"))

    for line in parse_lines(NATURAL_LANGUAGE_DIR / "spanish_valid_inputs.txt"):
        tokens = lexer.tokenize(line)
        result = parser.parse(tokens)

        assert result.accepted
        assert translate(tokens, SPANISH_TRANSLATION) == line


def test_spanish_simple_invalid_inputs_are_rejected() -> None:
    lexer = build_spanish_lexer()
    parser = LL1Parser(load_yapar(NATURAL_LANGUAGE_DIR / "spanish_simple.yapar"))

    for line in parse_lines(NATURAL_LANGUAGE_DIR / "spanish_invalid_inputs.txt"):
        result = parser.parse(lexer.tokenize(line))

        assert not result.accepted


def test_qeqchi_valid_inputs_parse_and_translate() -> None:
    lexer = build_qeqchi_lexer()
    parser = LL1Parser(load_yapar(NATURAL_LANGUAGE_DIR / "qeqchi_simplified.yapar"))

    expected = {
        "b'ar laa'in xnawb'al aatinob'aal": "donde yo saber idioma",
        "a'an yehok aatinob'aal": "el decir idioma",
        "laa'in chalk ochoch": "yo venir casa",
    }

    for line in parse_lines(NATURAL_LANGUAGE_DIR / "qeqchi_valid_inputs.txt"):
        tokens = lexer.tokenize(line)
        result = parser.parse(tokens)

        assert result.accepted
        assert translate(tokens, QEQCHI_TRANSLATION) == expected[line]


def test_qeqchi_invalid_inputs_are_rejected_or_fail_lexically() -> None:
    lexer = build_qeqchi_lexer()
    parser = LL1Parser(load_yapar(NATURAL_LANGUAGE_DIR / "qeqchi_simplified.yapar"))

    for line in parse_lines(NATURAL_LANGUAGE_DIR / "qeqchi_invalid_inputs.txt"):
        try:
            tokens = lexer.tokenize(line)
        except LexicalError:
            continue

        assert not parser.parse(tokens).accepted


def test_qeqchi_lexicon_documents_expected_entries() -> None:
    lexicon = (NATURAL_LANGUAGE_DIR / "qeqchi_lexicon.tsv").read_text(encoding="utf-8")

    assert "Q'eqchi' Talking Dictionary" in lexicon
    assert "Laa'in" in lexicon
    assert "Aatinob'aal" in lexicon
