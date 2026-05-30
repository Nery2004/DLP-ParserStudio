from pathlib import Path

import pytest

from dlp_parserstudio.core.grammar import NonTerminal, Production, Terminal
from dlp_parserstudio.parser.yapar_loader import YaparLoaderError, load_yapar, loads_yapar


SAMPLE_YAPAR = """%token ID NUMBER PLUS TIMES LPAREN RPAREN
%ignore WS
%start expr

%%
expr : term exprp ;
exprp : PLUS term exprp | epsilon ;
term : NUMBER | ID | LPAREN expr RPAREN ;
"""


def test_loads_yapar_to_grammar() -> None:
    grammar = loads_yapar(SAMPLE_YAPAR)

    assert grammar.start_symbol == NonTerminal("expr")
    assert grammar.es_no_terminal("expr")
    assert grammar.es_no_terminal("exprp")
    assert grammar.es_no_terminal("term")
    assert grammar.es_terminal("ID")
    assert grammar.es_terminal("NUMBER")
    assert not grammar.es_terminal("WS")
    assert len(grammar.productions) == 6


def test_loads_yapar_supports_epsilon_productions() -> None:
    grammar = loads_yapar(SAMPLE_YAPAR)

    assert Production(NonTerminal("exprp"), ()) in grammar.producciones_de("exprp")


def test_load_yapar_from_example_file() -> None:
    grammar = load_yapar(Path("examples/basic_expr.yapar"))

    assert grammar.start_symbol == NonTerminal("expr")
    assert Production(
        NonTerminal("term"),
        (Terminal("LPAREN"), NonTerminal("expr"), Terminal("RPAREN")),
    ) in grammar.producciones_de("term")


def test_missing_separator_reports_location() -> None:
    with pytest.raises(YaparLoaderError) as error:
        loads_yapar("%token ID\n%start expr\nexpr : ID ;")

    assert error.value.line == 3
    assert error.value.column == 12


def test_missing_start_symbol_reports_location() -> None:
    with pytest.raises(YaparLoaderError) as error:
        loads_yapar("%token ID\n%%\nexpr : ID ;")

    assert error.value.line == 2
    assert error.value.column == 1


def test_undeclared_terminal_reports_location() -> None:
    with pytest.raises(YaparLoaderError) as error:
        loads_yapar("%token ID\n%start expr\n%%\nexpr : NUMBER ;")

    assert error.value.line == 4
    assert error.value.column == 8


def test_malformed_production_reports_location() -> None:
    with pytest.raises(YaparLoaderError) as error:
        loads_yapar("%token ID\n%start expr\n%%\nexpr ID ;")

    assert error.value.line == 4
    assert error.value.column == 6
