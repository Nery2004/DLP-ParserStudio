import json

from dlp_parserstudio.core.grammar import Grammar
from dlp_parserstudio.lexer.yalex import Token
from dlp_parserstudio.parser.ll1 import LL1Parser
from dlp_parserstudio.parser.slr import SLRParser
from dlp_parserstudio.parser.syntax_tree import SyntaxTree, TreeNode


def build_ll1_expression_grammar() -> Grammar:
    return Grammar.desde_estructura(
        {
            "start": "E",
            "productions": {
                "E": [["T", "Ep"]],
                "Ep": [["PLUS", "T", "Ep"], []],
                "T": [["ID"]],
            },
        }
    )


def build_slr_expression_grammar() -> Grammar:
    return Grammar.desde_estructura(
        {
            "start": "E",
            "productions": {
                "E": [["E", "PLUS", "ID"], ["ID"]],
            },
        }
    )


def expression_tokens() -> list[Token]:
    return [
        Token("ID", "id", 1, 1),
        Token("PLUS", "+", 1, 4),
        Token("ID", "id", 1, 6),
    ]


def terminal_leaves(node: TreeNode) -> list[TreeNode]:
    leaves: list[TreeNode] = []

    def visit(current: TreeNode) -> None:
        if current.lexeme is not None:
            leaves.append(current)
        for child in current.children:
            visit(child)

    visit(node)
    return leaves


def test_ll1_syntax_tree_for_id_plus_id() -> None:
    result = LL1Parser(build_ll1_expression_grammar()).parse(expression_tokens())

    assert result.accepted
    assert result.syntax_tree is not None
    assert result.tree is result.syntax_tree
    assert result.syntax_tree.root.symbol == "E"

    leaves = terminal_leaves(result.syntax_tree.root)

    assert [(leaf.symbol, leaf.lexeme) for leaf in leaves] == [
        ("ID", "id"),
        ("PLUS", "+"),
        ("ID", "id"),
    ]
    assert [(leaf.line, leaf.column) for leaf in leaves] == [(1, 1), (1, 4), (1, 6)]


def test_slr_syntax_tree_for_id_plus_id() -> None:
    result = SLRParser(build_slr_expression_grammar()).parse(expression_tokens())

    assert result.accepted
    assert result.syntax_tree is not None
    assert result.tree is result.syntax_tree
    assert result.syntax_tree.root.symbol == "E"

    leaves = terminal_leaves(result.syntax_tree.root)

    assert [(leaf.symbol, leaf.lexeme) for leaf in leaves] == [
        ("ID", "id"),
        ("PLUS", "+"),
        ("ID", "id"),
    ]


def test_syntax_tree_exports_dict_json_dot_and_pretty_print() -> None:
    tree = SyntaxTree(
        TreeNode(
            "E",
            children=[
                TreeNode("ID", "id", 1, 1),
                TreeNode("PLUS", "+", 1, 4),
                TreeNode("ID", "id", 1, 6),
            ],
        )
    )

    data = tree.to_dict()
    dot = tree.to_dot()
    pretty = tree.pretty_print()

    assert data["symbol"] == "E"
    assert data["children"][0]["lexeme"] == "id"
    assert json.loads(json.dumps(data)) == data
    assert "digraph SyntaxTree" in dot
    assert "ID: id" in dot
    assert pretty.splitlines()[0] == "E"
