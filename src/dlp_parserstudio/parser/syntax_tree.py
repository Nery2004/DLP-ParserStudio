"""Syntax tree data structures and exporters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dlp_parserstudio.core.grammar import Symbol


@dataclass
class TreeNode:
    """Node in a syntax tree."""

    symbol: str | Symbol
    lexeme: str | None = None
    line: int | None = None
    column: int | None = None
    children: list[TreeNode] = field(default_factory=list)

    def __post_init__(self) -> None:
        if isinstance(self.symbol, Symbol):
            self.symbol = self.symbol.name
        self.children = list(self.children)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "lexeme": self.lexeme,
            "line": self.line,
            "column": self.column,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass
class SyntaxTree:
    """Syntax tree rooted at a grammar symbol."""

    root: TreeNode

    def to_dict(self) -> dict[str, Any]:
        return self.root.to_dict()

    def to_dot(self) -> str:
        lines = [
            "digraph SyntaxTree {",
            "  node [shape=box];",
        ]
        counter = 0

        def visit(node: TreeNode) -> int:
            nonlocal counter
            node_id = counter
            counter += 1

            lines.append(f'  n{node_id} [label="{_dot_escape(_node_label(node))}"];')
            for child in node.children:
                child_id = visit(child)
                lines.append(f"  n{node_id} -> n{child_id};")

            return node_id

        visit(self.root)
        lines.append("}")
        return "\n".join(lines)

    def pretty_print(self) -> str:
        lines: list[str] = []

        def visit(node: TreeNode, prefix: str = "") -> None:
            lines.append(f"{prefix}{_pretty_label(node)}")
            for child in node.children:
                visit(child, f"{prefix}  ")

        visit(self.root)
        return "\n".join(lines)


def _node_label(node: TreeNode) -> str:
    if node.lexeme is None:
        return str(node.symbol)

    location = ""
    if node.line is not None and node.column is not None:
        location = f" ({node.line}:{node.column})"
    return f"{node.symbol}: {node.lexeme}{location}"


def _pretty_label(node: TreeNode) -> str:
    return _node_label(node)


def _dot_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
