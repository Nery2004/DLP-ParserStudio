from dlp_parserstudio.core.grammar import Grammar, NonTerminal, Production, Terminal


def test_create_grammar() -> None:
    start = NonTerminal("S")
    grammar = Grammar(
        non_terminals={start},
        terminals={Terminal("a")},
        start_symbol=start,
    )

    assert grammar.V == {start}
    assert grammar.T == {Terminal("a")}
    assert grammar.P == []
    assert grammar.S == start


def test_add_productions_and_get_by_non_terminal() -> None:
    grammar = Grammar(
        non_terminals={NonTerminal("S"), NonTerminal("A")},
        terminals={Terminal("a")},
        start_symbol=NonTerminal("S"),
    )

    production = grammar.agregar_produccion("S", ["A", "a"])

    assert production == Production(NonTerminal("S"), (NonTerminal("A"), Terminal("a")))
    assert grammar.producciones_de("S") == [production]
    assert grammar.es_no_terminal("A")
    assert grammar.es_terminal("a")


def test_load_grammar_from_simple_python_structure_and_verify_start_symbol() -> None:
    grammar = Grammar.desde_estructura(
        {
            "start": "S",
            "productions": {
                "S": [["A", "b"]],
                "A": [["a"]],
            },
        }
    )

    assert grammar.start_symbol == NonTerminal("S")
    assert grammar.es_no_terminal("S")
    assert grammar.es_no_terminal("A")
    assert grammar.es_terminal("a")
    assert grammar.es_terminal("b")
    assert len(grammar.productions) == 2


def test_generate_augmented_grammar() -> None:
    grammar = Grammar.desde_estructura(
        {
            "start": "S",
            "productions": {
                "S": [["a"]],
            },
        }
    )

    augmented = grammar.aumentar()

    assert augmented.start_symbol == NonTerminal("S'")
    assert augmented.productions[0] == Production(NonTerminal("S'"), (NonTerminal("S"),))
    assert augmented.producciones_de("S'") == [augmented.productions[0]]
    assert grammar.start_symbol == NonTerminal("S")
