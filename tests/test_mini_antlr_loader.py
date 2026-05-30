from pathlib import Path

import pytest

from dlp_parserstudio.core.grammar import NonTerminal, Production, Terminal
from dlp_parserstudio.lexer.yalex import YALexLexer
from dlp_parserstudio.mini_antlr import loads_mini_antlr as package_loads_mini_antlr
from dlp_parserstudio.mini_antlr.loader import (
    MiniANTLRLoaderError,
    load_mini_antlr,
    loads_mini_antlr,
)


CALC_SOURCE = r"""
grammar Calc;

expr : term (PLUS term)* ;
term : NUMBER ;
PLUS : '+' ;
NUMBER : [0-9]+ ;
WS : [ \t\r\n]+ -> skip ;
"""


def test_loads_mini_antlr_to_yalex_rules_and_grammar() -> None:
    spec = loads_mini_antlr(CALC_SOURCE)

    assert spec.name == "Calc"
    assert [rule.type for rule in spec.lexer_rules] == ["PLUS", "NUMBER", "WS"]
    assert [rule.skip for rule in spec.lexer_rules] == [False, False, True]
    assert spec.grammar.start_symbol == NonTerminal("expr")
    assert spec.grammar.es_no_terminal("expr")
    assert spec.grammar.es_no_terminal("term")
    assert spec.grammar.es_terminal("PLUS")
    assert spec.grammar.es_terminal("NUMBER")
    assert not spec.grammar.es_terminal("WS")


def test_mini_antlr_lexer_rules_tokenize_input() -> None:
    spec = loads_mini_antlr(CALC_SOURCE)
    lexer = YALexLexer(spec.lexer_rules)

    tokens = lexer.tokenize("12 + 7")

    assert [(token.type, token.lexeme) for token in tokens] == [
        ("NUMBER", "12"),
        ("PLUS", "+"),
        ("NUMBER", "7"),
    ]


def test_mini_antlr_expands_star_group_to_epsilon_production() -> None:
    spec = loads_mini_antlr(CALC_SOURCE)
    repeat_names = [
        symbol.name
        for symbol in spec.grammar.non_terminals
        if symbol.name.startswith("expr__repeat_")
    ]

    assert len(repeat_names) == 1
    repeat = repeat_names[0]
    assert Production(
        NonTerminal("expr"),
        (NonTerminal("term"), NonTerminal(repeat)),
    ) in spec.grammar.producciones_de("expr")
    assert Production(
        NonTerminal(repeat),
        (Terminal("PLUS"), NonTerminal("term"), NonTerminal(repeat)),
    ) in spec.grammar.producciones_de(repeat)
    assert Production(NonTerminal(repeat), ()) in spec.grammar.producciones_de(repeat)


def test_load_mini_antlr_example_file() -> None:
    spec = load_mini_antlr(Path("examples/calc.mini.g4"))

    assert spec.name == "Calc"
    assert spec.grammar.start_symbol == NonTerminal("expr")


def test_mini_antlr_supports_parser_alternatives() -> None:
    spec = package_loads_mini_antlr(
        r"""
        grammar Atom;
        atom : NUMBER | ID ;
        NUMBER : [0-9]+ ;
        ID : [a-z]+ ;
        WS : [ \t\r\n]+ -> skip ;
        """
    )

    assert Production(NonTerminal("atom"), (Terminal("NUMBER"),)) in (
        spec.grammar.producciones_de("atom")
    )
    assert Production(NonTerminal("atom"), (Terminal("ID"),)) in (
        spec.grammar.producciones_de("atom")
    )


def test_mini_antlr_rejects_skip_token_in_parser_rule() -> None:
    with pytest.raises(MiniANTLRLoaderError):
        loads_mini_antlr(
            r"""
            grammar Bad;
            expr : WS ;
            WS : [ \t\r\n]+ -> skip ;
            """
        )
