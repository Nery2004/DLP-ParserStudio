from pathlib import Path

from dlp_parserstudio.lexer.yalex import LexicalError, LexerRule, YALexLexer
from dlp_parserstudio.parser.slr import SLRParser
from dlp_parserstudio.parser.yapar_loader import load_yapar


def lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build_futlang_lexer() -> YALexLexer:
    return YALexLexer(
        [
            LexerRule("LET", r"let"),
            LexerRule("PRINT", r"print"),
            LexerRule("IF", r"if"),
            LexerRule("WHILE", r"while"),
            LexerRule("NUMBER", r"[0-9]+"),
            LexerRule("ID", r"[a-zA-Z_][a-zA-Z0-9_]*"),
            LexerRule("PLUS", r"\+"),
            LexerRule("MINUS", r"-"),
            LexerRule("TIMES", r"\*"),
            LexerRule("DIVIDE", r"/"),
            LexerRule("ASSIGN", r"="),
            LexerRule("LPAREN", r"\("),
            LexerRule("RPAREN", r"\)"),
            LexerRule("LBRACE", r"\{"),
            LexerRule("RBRACE", r"\}"),
            LexerRule("SEMI", r";"),
            LexerRule("WS", r"\s+", skip=True),
        ]
    )


def build_messiscript_lexer() -> YALexLexer:
    return YALexLexer(
        [
            LexerRule("ARRANCA", r"arranca"),
            LexerRule("GOL", r"gol"),
            LexerRule("PASE", r"pase"),
            LexerRule("MARCA", r"marca"),
            LexerRule("GRITA", r"grita"),
            LexerRule("FIN", r"fin"),
            LexerRule("NUMBER", r"[0-9]+"),
            LexerRule("STRING", r'"[^"]*"'),
            LexerRule("ID", r"[a-zA-Z_][a-zA-Z0-9_]*"),
            LexerRule("SEMI", r";"),
            LexerRule("WS", r"\s+", skip=True),
        ]
    )


def build_cow_lexer() -> YALexLexer:
    return YALexLexer(
        [
            LexerRule("MOO_UPPER", r"MOO"),
            LexerRule("MOO_LEFT", r"mOo"),
            LexerRule("MOO_RIGHT", r"moO"),
            LexerRule("MOO_LOWER", r"moo"),
            LexerRule("WS", r"\s+", skip=True),
        ]
    )


def assert_valid_inputs(directory: str, lexer: YALexLexer, grammar_file: str) -> None:
    base = Path(directory)
    parser = SLRParser(load_yapar(base / grammar_file))

    for source in lines(base / "valid_inputs.txt"):
        assert parser.parse(lexer.tokenize(source)).accepted, source


def assert_invalid_inputs(directory: str, lexer: YALexLexer, grammar_file: str) -> None:
    base = Path(directory)
    parser = SLRParser(load_yapar(base / grammar_file))

    for source in lines(base / "invalid_inputs.txt"):
        try:
            tokens = lexer.tokenize(source)
        except LexicalError:
            continue

        assert not parser.parse(tokens).accepted, source


def test_futlang_valid_and_invalid_inputs() -> None:
    lexer = build_futlang_lexer()

    assert_valid_inputs("examples/creative_language", lexer, "futlang.yapar")
    assert_invalid_inputs("examples/creative_language", lexer, "futlang.yapar")


def test_messiscript_valid_and_invalid_inputs() -> None:
    lexer = build_messiscript_lexer()

    assert_valid_inputs("examples/messiscript", lexer, "messiscript.yapar")
    assert_invalid_inputs("examples/messiscript", lexer, "messiscript.yapar")


def test_messiscript_full_valid_inputs_file_is_accepted() -> None:
    base = Path("examples/messiscript")
    lexer = build_messiscript_lexer()
    parser = SLRParser(load_yapar(base / "messiscript.yapar"))
    source = (base / "valid_inputs.txt").read_text(encoding="utf-8")

    assert parser.parse(lexer.tokenize(source)).accepted


def test_cow_valid_and_invalid_inputs() -> None:
    lexer = build_cow_lexer()

    assert_valid_inputs("examples/cow", lexer, "cow.yapar")
    assert_invalid_inputs("examples/cow", lexer, "cow.yapar")
