from pathlib import Path

from dlp_parserstudio.ide.analysis import analyze_source, loads_yalex
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
        loads_yalex(
            Path("examples/messiscript/messiscript.yalex").read_text(encoding="utf-8")
        )
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
    base = Path("examples/messiscript")
    parser = SLRParser(load_yapar(base / "messiscript.yapar"))

    source = (base / "valid_inputs.txt").read_text(encoding="utf-8")
    assert parser.parse(lexer.tokenize(source)).accepted
    assert_invalid_inputs("examples/messiscript", lexer, "messiscript.yapar")


def test_messiscript_full_valid_inputs_file_is_accepted() -> None:
    base = Path("examples/messiscript")
    lexer = build_messiscript_lexer()
    parser = SLRParser(load_yapar(base / "messiscript.yapar"))
    source = (base / "valid_inputs.txt").read_text(encoding="utf-8")

    assert parser.parse(lexer.tokenize(source)).accepted


def test_messiscript_real_subset_accepts_required_examples_in_all_methods() -> None:
    base = Path("examples/messiscript")
    yalex = (base / "messiscript.yalex").read_text(encoding="utf-8")
    yapar = (base / "messiscript.yapar").read_text(encoding="utf-8")
    examples = [
        "la agarra messi.\nencara messi.\nla mueve messi por la derecha.\njuega messi.\n¡gol!.",
        "la agarra messi.\nva messi pelota grande.\njuega messi.\n¡gol!.",
        "la agarra messi.\nsigue messi.\njuega messi.\nvuelve messi.\n¡gol!.",
    ]

    for source in examples:
        for method in ("LL(1)", "LR(0)", "SLR(1)", "LALR(1)"):
            result = analyze_source(yalex, yapar, source, method)

            assert result["accepted"], f"{method}: {source}"
            assert result["errors"] == []
            assert result["conflicts"] == []


def test_messiscript_old_invented_demo_is_rejected() -> None:
    base = Path("examples/messiscript")
    result = analyze_source(
        (base / "messiscript.yalex").read_text(encoding="utf-8"),
        (base / "messiscript.yapar").read_text(encoding="utf-8"),
        "arranca; gol messi;",
        "SLR(1)",
    )

    assert not result["accepted"]
    assert result["errors"]


def test_cow_valid_and_invalid_inputs() -> None:
    lexer = build_cow_lexer()

    assert_valid_inputs("examples/cow", lexer, "cow.yapar")
    assert_invalid_inputs("examples/cow", lexer, "cow.yapar")
