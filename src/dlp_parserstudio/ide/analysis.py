"""Analysis service used by the web IDE."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from dlp_parserstudio.core.grammar import Grammar, NonTerminal, Production, Symbol, Terminal
from dlp_parserstudio.lexer.yalex import LexerRule, LexicalError, Token, YALexLexer
from dlp_parserstudio.mini_antlr.loader import MiniANTLRLoaderError, loads_mini_antlr
from dlp_parserstudio.parser.first_follow import EOF, FirstFollowCalculator
from dlp_parserstudio.parser.lalr import LALRParser, build_lalr_table
from dlp_parserstudio.parser.ll1 import LL1Parser, build_ll1_table
from dlp_parserstudio.parser.lr0 import LR0Automaton, build_lr0_automaton
from dlp_parserstudio.parser.parallel_conflict import explore_shift_reduce_conflict
from dlp_parserstudio.parser.slr import SLRParser, build_slr_table
from dlp_parserstudio.parser.syntax_tree import SyntaxTree, TreeNode
from dlp_parserstudio.parser.yapar_loader import YaparLoaderError, loads_yapar


@dataclass(frozen=True)
class YALexLoaderError(ValueError):
    """Raised when a .yalex text cannot be parsed by the educational loader."""

    message: str
    line: int
    column: int

    def __str__(self) -> str:
        return f"{self.message} at line {self.line}, column {self.column}."


@dataclass(frozen=True)
class _LRAction:
    kind: str
    target: int | None = None
    production: Production | None = None

    @classmethod
    def shift(cls, target: int) -> _LRAction:
        return cls("shift", target=target)

    @classmethod
    def reduce(cls, production: Production) -> _LRAction:
        return cls("reduce", production=production)

    @classmethod
    def accept(cls) -> _LRAction:
        return cls("accept")

    @classmethod
    def error(cls) -> _LRAction:
        return cls("error")


@dataclass(frozen=True)
class _LRConflict:
    kind: str
    state: int
    lookahead: Terminal
    existing: _LRAction
    incoming: _LRAction


@dataclass(frozen=True)
class _LRParsingTable:
    action: Mapping[tuple[int, Terminal], _LRAction]
    goto: Mapping[tuple[int, NonTerminal], int]
    conflicts: tuple[_LRConflict, ...]
    automaton: LR0Automaton

    def action_for(self, state: int, lookahead: Terminal) -> _LRAction:
        return self.action.get((state, lookahead), _LRAction.error())

    def goto_for(self, state: int, non_terminal: NonTerminal) -> int | None:
        return self.goto.get((state, non_terminal))


@dataclass(frozen=True)
class _InputToken:
    terminal: Terminal
    lexeme: str
    line: int
    column: int


def analyze_source(
    yalex_text: str,
    yapar_text: str,
    input_text: str,
    method: str,
    lexicon_text: str = "",
) -> dict[str, Any]:
    """Run the selected analysis pipeline and return JSON-serializable data."""

    errors: list[dict[str, Any]] = []
    method_key = method.lower()
    result: dict[str, Any] = {
        "method": method,
        "format_detected": None,
        "tokens": [],
        "first": {},
        "follow": {},
        "lr0_automaton": None,
        "lr1_automaton": None,
        "lalr_automaton": None,
        "tables": {},
        "steps": [],
        "accepted": False,
        "conflicts": [],
        "parallel_branches": [],
        "syntax_tree": None,
        "translation": None,
        "errors": errors,
    }

    try:
        grammar_format = _detect_grammar_format(yapar_text)
        result["format_detected"] = grammar_format

        if grammar_format == "antlr":
            spec = loads_mini_antlr(yapar_text)
            lexer = YALexLexer(spec.lexer_rules)
            grammar = spec.grammar
        else:
            rules = loads_yalex(yalex_text)
            lexer = YALexLexer(rules)
            grammar = loads_yapar(yapar_text)

        tokens, lexical_errors = _tokenize_collecting_errors(lexer, input_text)
        errors.extend(lexical_errors)
    except YALexLoaderError as error:
        errors.append(_error("yalex", error.message, error.line, error.column))
        return result
    except YaparLoaderError as error:
        errors.append(_error("yapar", str(error), error.line, error.column))
        return result
    except MiniANTLRLoaderError as error:
        errors.append(_error("antlr", str(error), 1, 1))
        return result
    except Exception as error:
        errors.append(_error("internal", str(error), 1, 1))
        return result

    result["tokens"] = [_token_to_dict(token) for token in tokens]
    result["translation"] = _translation_to_dict(input_text, tokens, lexicon_text)
    result.update(_first_follow_to_dict(grammar))

    try:
        automaton = build_lr0_automaton(grammar)
        result["lr0_automaton"] = _lr0_automaton_to_dict(automaton)
    except Exception as error:
        errors.append(_error("lr0", str(error), 1, 1))

    try:
        if method_key in {"ll1", "ll(1)"}:
            _analyze_ll1(grammar, tokens, result)
        elif method_key in {"lr0", "lr(0)"}:
            _analyze_lr0(grammar, tokens, result)
        elif method_key in {"slr", "slr1", "slr(1)"}:
            _analyze_slr(grammar, tokens, result)
        elif method_key in {"lalr", "lalr1", "lalr(1)"}:
            _analyze_lalr(grammar, tokens, result)
        else:
            errors.append(_error("method", f"Unknown analysis method {method!r}.", 1, 1))
    except Exception as error:
        errors.append(_error("parser", str(error), 1, 1))

    return result


def _detect_grammar_format(text: str) -> str:
    stripped = text.strip()
    first_line = stripped.splitlines()[0] if stripped else ""
    if re.match(r"^grammar\s+[A-Za-z_][A-Za-z0-9_]*\s*;", first_line):
        return "antlr"
    return "yapar"


def loads_yalex(text: str) -> list[LexerRule]:
    """Parse the educational .yalex line format used by examples and the IDE."""

    rules: list[LexerRule] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue

        match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s+(.+?)\s*$", line)
        if match is None:
            raise YALexLoaderError("Expected TOKEN_NAME regex [skip]", line_number, 1)

        token_type = match.group(1)
        pattern = match.group(2).strip()
        skip = False
        skip_match = re.match(r"^(.*?)\s+(?:->\s*)?skip\s*$", pattern)
        if skip_match is not None:
            pattern = skip_match.group(1).strip()
            skip = True

        try:
            rules.append(LexerRule(token_type, pattern, skip=skip))
        except Exception as error:
            column = raw_line.find(pattern) + 1 if pattern in raw_line else 1
            raise YALexLoaderError(str(error), line_number, column) from error

    if not rules:
        raise YALexLoaderError("At least one lexer rule is required", 1, 1)

    return rules


def _tokenize_collecting_errors(
    lexer: YALexLexer,
    text: str,
) -> tuple[list[Token], list[dict[str, Any]]]:
    tokens: list[Token] = []
    errors: list[dict[str, Any]] = []
    position = 0
    line = 1
    column = 1

    while position < len(text):
        match = lexer._best_match(text, position)

        if match is None:
            character = text[position]
            error = LexicalError(character, line, column)
            errors.append(_error("lexer", str(error), line, column, character))
            line, column = _advance_text_position(character, line, column)
            position += 1
            continue

        rule, lexeme = match
        token_line = line
        token_column = column
        line, column = _advance_text_position(lexeme, line, column)
        position += len(lexeme)

        if not rule.skip:
            tokens.append(Token(rule.type, lexeme, token_line, token_column))

    return tokens, errors


def _advance_text_position(lexeme: str, line: int, column: int) -> tuple[int, int]:
    for character in lexeme:
        if character == "\n":
            line += 1
            column = 1
        else:
            column += 1

    return line, column


def _analyze_ll1(grammar: Grammar, tokens: list[Token], result: dict[str, Any]) -> None:
    table = build_ll1_table(grammar)
    parser = LL1Parser(grammar, table=table, raise_on_conflicts=False)
    parse_result = parser.parse(tokens)

    result["accepted"] = parse_result.accepted
    result["steps"] = [_step_to_dict(step) for step in parse_result.steps]
    result["conflicts"] = [_ll1_conflict_to_dict(conflict) for conflict in table.conflicts]
    result["tables"]["ll1"] = _ll1_table_to_dict(table.entries)
    result["syntax_tree"] = _syntax_tree_to_dict(parse_result.syntax_tree)

    if parse_result.error:
        parser_errors = _collect_ll1_syntax_errors(grammar, table, tokens)
        result["errors"].extend(
            parser_errors or [_parse_error_from_tokens(parse_result.error, tokens)]
        )


def _analyze_lr0(grammar: Grammar, tokens: list[Token], result: dict[str, Any]) -> None:
    table = _build_lr0_table(grammar)
    parse_result = _parse_lr_table(table, tokens)

    result["accepted"] = parse_result["accepted"]
    result["steps"] = parse_result["steps"]
    result["errors"].extend(
        _collect_lr_syntax_errors(table, tokens)
        if not parse_result["accepted"]
        else parse_result["errors"]
    )
    result["syntax_tree"] = parse_result["syntax_tree"]
    result["tables"].update(_action_goto_tables_to_dict(table))
    result["tables"]["reductions"] = _reduction_table_to_dict(table, "LR(0): todos los terminales")
    result["conflicts"] = [_lr_conflict_to_dict(conflict) for conflict in table.conflicts]
    result["parallel_branches"] = _parallel_branches_to_dict(grammar, tokens, table)


def _analyze_slr(grammar: Grammar, tokens: list[Token], result: dict[str, Any]) -> None:
    table = build_slr_table(grammar)
    parser = SLRParser(grammar, table=table)
    parse_result = parser.parse(tokens)

    result["accepted"] = parse_result.accepted
    result["steps"] = [_step_to_dict(step) for step in parse_result.steps]
    result["errors"].extend(
        _collect_lr_syntax_errors(table, tokens)
        if not parse_result.accepted
        else _structured_errors_to_dict(parse_result.errors, "parser")
    )
    result["syntax_tree"] = _syntax_tree_to_dict(parse_result.syntax_tree)
    result["tables"].update(_action_goto_tables_to_dict(table))
    result["tables"]["reductions"] = _reduction_table_to_dict(table, "SLR(1): FOLLOW global del LHS")
    result["conflicts"] = [_lr_conflict_to_dict(conflict) for conflict in table.conflicts]
    result["parallel_branches"] = _parallel_branches_to_dict(grammar, tokens, table)


def _analyze_lalr(grammar: Grammar, tokens: list[Token], result: dict[str, Any]) -> None:
    table = build_lalr_table(grammar)
    parser = LALRParser(grammar, table=table)
    parse_result = parser.parse(tokens)

    result["accepted"] = parse_result.accepted
    result["steps"] = [_step_to_dict(step) for step in parse_result.steps]
    result["errors"].extend(
        _collect_lr_syntax_errors(table, tokens)
        if not parse_result.accepted
        else _structured_errors_to_dict(parse_result.errors, "parser")
    )
    result["syntax_tree"] = _syntax_tree_to_dict(parse_result.syntax_tree)
    result["tables"].update(_action_goto_tables_to_dict(table))
    result["tables"]["reductions"] = _reduction_table_to_dict(table, "LALR(1): lookahead LR(1) fusionado")
    if table.automaton is not None:
        result["lr1_automaton"] = _lr1_automaton_to_dict(
            table.automaton.canonical_automaton,
            "LR(1) canonico",
        )
        result["lalr_automaton"] = _lr1_automaton_to_dict(
            table.automaton,
            "LALR(1) fusionado por nucleo",
        )
    result["conflicts"] = [_lr_conflict_to_dict(conflict) for conflict in table.conflicts]
    result["parallel_branches"] = _parallel_branches_to_dict(grammar, tokens, table)


def _build_lr0_table(grammar: Grammar) -> _LRParsingTable:
    automaton = build_lr0_automaton(grammar)
    terminals = set(automaton.grammar.terminals)
    terminals.add(EOF)
    action: dict[tuple[int, Terminal], _LRAction] = {}
    goto_table: dict[tuple[int, NonTerminal], int] = {}
    conflicts: list[_LRConflict] = []
    augmented_start = automaton.grammar.start_symbol

    for (source, symbol), target in automaton.transitions.items():
        if isinstance(symbol, Terminal):
            _set_lr_action(action, conflicts, source, symbol, _LRAction.shift(target))
        elif isinstance(symbol, NonTerminal):
            goto_table[(source, symbol)] = target

    for state_id, state in enumerate(automaton.states):
        for item in state.items:
            if not item.is_complete:
                continue

            if item.production.lhs == augmented_start:
                _set_lr_action(action, conflicts, state_id, EOF, _LRAction.accept())
                continue

            for terminal in terminals:
                _set_lr_action(
                    action,
                    conflicts,
                    state_id,
                    terminal,
                    _LRAction.reduce(item.production),
                )

    return _LRParsingTable(action, goto_table, tuple(conflicts), automaton)


def _parse_lr_table(table: _LRParsingTable, tokens: list[Token]) -> dict[str, Any]:
    input_tokens = _normalize_input(tokens)
    stack: list[int | Symbol] = [0]
    nodes: list[TreeNode] = []
    position = 0
    steps: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    while True:
        state = _top_state(stack)
        current_token = input_tokens[position]
        action = table.action_for(state, current_token.terminal)
        stack_view = tuple(_stack_entry_name(entry) for entry in stack)
        remaining_input = tuple(token.terminal.name for token in input_tokens[position:])

        if action.kind == "shift":
            steps.append(
                {
                    "stack": stack_view,
                    "remaining_input": remaining_input,
                    "action": f"shift {current_token.terminal.name} and go to {action.target}",
                }
            )
            stack.extend([current_token.terminal, action.target])
            nodes.append(
                TreeNode(
                    current_token.terminal.name,
                    current_token.lexeme,
                    current_token.line,
                    current_token.column,
                )
            )
            position += 1
            continue

        if action.kind == "reduce" and action.production is not None:
            production = action.production
            rhs_length = len(production.rhs)
            children = nodes[-rhs_length:] if rhs_length else []
            if rhs_length:
                del stack[-2 * rhs_length :]
                del nodes[-rhs_length:]

            goto_source = _top_state(stack)
            target = table.goto_for(goto_source, production.lhs)
            if target is None:
                message = f"Missing GOTO[{goto_source}, {production.lhs.name}] after reduction"
                errors.append(
                    _error("parser", message, current_token.line, current_token.column, current_token.terminal.name)
                )
                steps.append(
                    {"stack": stack_view, "remaining_input": remaining_input, "action": f"error: {message}"}
                )
                return _parse_table_result(False, steps, errors, None)

            steps.append(
                {
                    "stack": stack_view,
                    "remaining_input": remaining_input,
                    "action": f"reduce {_format_production(production)}",
                }
            )
            stack.extend([production.lhs, target])
            nodes.append(TreeNode(production.lhs.name, children=children))
            continue

        if action.kind == "accept":
            steps.append({"stack": stack_view, "remaining_input": remaining_input, "action": "accept"})
            tree = SyntaxTree(nodes[-1]) if nodes else None
            return _parse_table_result(True, steps, errors, tree)

        message = f"Unexpected token {current_token.terminal.name} in state {state}"
        errors.append(
            _error("parser", message, current_token.line, current_token.column, current_token.terminal.name)
        )
        steps.append({"stack": stack_view, "remaining_input": remaining_input, "action": f"error: {message}"})
        return _parse_table_result(False, steps, errors, None)


def _parse_table_result(
    accepted: bool,
    steps: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    syntax_tree: SyntaxTree | None,
) -> dict[str, Any]:
    return {
        "accepted": accepted,
        "steps": steps,
        "errors": errors,
        "syntax_tree": _syntax_tree_to_dict(syntax_tree),
    }


def _set_lr_action(
    table: dict[tuple[int, Terminal], _LRAction],
    conflicts: list[_LRConflict],
    state: int,
    lookahead: Terminal,
    incoming: _LRAction,
) -> None:
    key = (state, lookahead)
    existing = table.get(key)

    if existing is None:
        table[key] = incoming
        return
    if existing == incoming:
        return

    conflicts.append(_LRConflict(_conflict_kind(existing, incoming), state, lookahead, existing, incoming))


def _conflict_kind(existing: Any, incoming: Any) -> str:
    kinds = {existing.kind, incoming.kind}
    if kinds == {"shift", "reduce"}:
        return "shift/reduce"
    if existing.kind == "reduce" and incoming.kind == "reduce":
        return "reduce/reduce"
    return "/".join(sorted(kinds))


def _first_follow_to_dict(grammar: Grammar) -> dict[str, dict[str, list[str]]]:
    calculator = FirstFollowCalculator(grammar)
    return {
        "first": {
            symbol.name: _symbol_set_to_names(values)
            for symbol, values in sorted(calculator.first_sets.items(), key=lambda item: item[0].name)
            if isinstance(symbol, NonTerminal)
        },
        "follow": {
            symbol.name: _symbol_set_to_names(values)
            for symbol, values in sorted(calculator.follow_sets.items(), key=lambda item: item[0].name)
        },
    }


def _symbol_set_to_names(values: Iterable[Symbol]) -> list[str]:
    return sorted(symbol.name for symbol in values)


def _lr0_automaton_to_dict(automaton: LR0Automaton) -> dict[str, Any]:
    states = []
    for index, state in enumerate(automaton.states):
        states.append(
            {
                "id": index,
                "items": sorted(str(item) for item in state.items),
            }
        )

    transitions = [
        {"from": source, "symbol": symbol.name, "to": target}
        for (source, symbol), target in sorted(
            automaton.transitions.items(),
            key=lambda item: (item[0][0], item[0][1].name, item[1]),
        )
    ]

    return {
        "kind": "LR(0)",
        "states": states,
        "transitions": transitions,
        "dot": automaton.to_dot(),
    }


def _lr1_automaton_to_dict(automaton: Any, kind: str) -> dict[str, Any]:
    states = []
    for index, state in enumerate(automaton.states):
        states.append(
            {
                "id": index,
                "items": sorted(str(item) for item in state.items),
                "core": sorted(
                    f"{production.lhs.name} -> {' '.join(symbol.name for symbol in production.rhs) or 'epsilon'} @ {dot}"
                    for production, dot in state.core
                ),
            }
        )

    transitions = [
        {"from": source, "symbol": symbol.name, "to": target}
        for (source, symbol), target in sorted(
            automaton.transitions.items(),
            key=lambda item: (item[0][0], item[0][1].name, item[1]),
        )
    ]

    return {
        "kind": kind,
        "states": states,
        "transitions": transitions,
        "dot": _lr_items_to_dot(kind, states, transitions),
    }


def _lr_items_to_dot(
    kind: str,
    states: list[dict[str, Any]],
    transitions: list[dict[str, Any]],
) -> str:
    graph_name = re.sub(r"[^A-Za-z0-9_]", "_", kind)
    lines = [
        f"digraph {graph_name} {{",
        "  rankdir=LR;",
        "  node [shape=box];",
    ]

    for state in states:
        label = "\\n".join(_dot_escape(item) for item in state["items"])
        lines.append(f'  I{state["id"]} [label="I{state["id"]}\\n{label}"];')

    for transition in transitions:
        lines.append(
            (
                f'  I{transition["from"]} -> I{transition["to"]} '
                f'[label="{_dot_escape(transition["symbol"])}"];'
            )
        )

    lines.append("}")
    return "\n".join(lines)


def _ll1_table_to_dict(entries: Mapping[tuple[NonTerminal, Terminal], Production]) -> list[dict[str, str]]:
    return [
        {
            "non_terminal": non_terminal.name,
            "lookahead": terminal.name,
            "production": _format_production(production),
        }
        for (non_terminal, terminal), production in sorted(
            entries.items(),
            key=lambda item: (item[0][0].name, item[0][1].name),
        )
    ]


def _action_goto_tables_to_dict(table: Any) -> dict[str, list[dict[str, Any]]]:
    action = [
        {"state": state, "lookahead": terminal.name, "action": _action_to_string(action)}
        for (state, terminal), action in sorted(
            table.action.items(),
            key=lambda item: (item[0][0], item[0][1].name),
        )
    ]
    goto = [
        {"state": state, "non_terminal": non_terminal.name, "target": target}
        for (state, non_terminal), target in sorted(
            table.goto.items(),
            key=lambda item: (item[0][0], item[0][1].name),
        )
    ]
    return {"action": action, "goto": goto}


def _reduction_table_to_dict(table: Any, source: str) -> list[dict[str, Any]]:
    return [
        {
            "state": state,
            "lookahead": terminal.name,
            "production": _format_production(action.production),
            "source": source,
        }
        for (state, terminal), action in sorted(
            table.action.items(),
            key=lambda item: (item[0][0], item[0][1].name),
        )
        if action.kind == "reduce" and action.production is not None
    ]


def _parallel_branches_to_dict(grammar: Grammar, tokens: list[Token], table: Any) -> list[dict[str, Any]]:
    if not any(conflict.kind == "shift/reduce" for conflict in getattr(table, "conflicts", ())):
        return []

    exploration = explore_shift_reduce_conflict(grammar, tokens, table=table)
    return [
        {
            "name": branch.name,
            "chosen_action": branch.chosen_action,
            "stack": list(branch.stack),
            "remaining_input": list(branch.remaining_input),
            "result": branch.result,
            "error": branch.error,
            "steps": [_step_to_dict(step) for step in branch.steps],
        }
        for branch in exploration.branches
    ]


def _ll1_conflict_to_dict(conflict: Any) -> dict[str, str]:
    return {
        "kind": "ll1",
        "non_terminal": conflict.non_terminal.name,
        "lookahead": conflict.lookahead.name,
        "existing": _format_production(conflict.existing),
        "incoming": _format_production(conflict.incoming),
    }


def _lr_conflict_to_dict(conflict: Any) -> dict[str, Any]:
    return {
        "kind": conflict.kind,
        "state": conflict.state,
        "lookahead": conflict.lookahead.name,
        "existing": _action_to_string(conflict.existing),
        "incoming": _action_to_string(conflict.incoming),
    }


def _structured_errors_to_dict(errors: Iterable[Any], source: str) -> list[dict[str, Any]]:
    return [
        _error(source, error.message, error.line, error.column, error.token)
        for error in errors
    ]


def _collect_ll1_syntax_errors(
    grammar: Grammar,
    table: Any,
    tokens: list[Token],
    *,
    max_errors: int = 25,
) -> list[dict[str, Any]]:
    input_tokens = _normalize_input(tokens)
    stack: list[Symbol] = [EOF, grammar.start_symbol]
    position = 0
    errors: list[dict[str, Any]] = []
    max_steps = max(200, len(input_tokens) * 40)

    for _ in range(max_steps):
        if not stack or len(errors) >= max_errors:
            break

        top = stack.pop()
        current = input_tokens[position]

        if top == EOF and current.terminal == EOF:
            break

        if isinstance(top, Terminal):
            if top == current.terminal:
                position += 1
                continue

            errors.append(
                _error(
                    "parser",
                    f"Expected {top.name}, found {current.terminal.name}",
                    current.line,
                    current.column,
                    current.terminal.name,
                )
            )
            if current.terminal != EOF:
                position += 1
                stack.append(top)
            continue

        if isinstance(top, NonTerminal):
            production = table.get(top, current.terminal)
            if production is None:
                errors.append(
                    _error(
                        "parser",
                        f"No LL(1) production for {top.name} with lookahead {current.terminal.name}",
                        current.line,
                        current.column,
                        current.terminal.name,
                    )
                )
                if current.terminal != EOF:
                    position += 1
                continue

            stack.extend(
                reversed(
                    tuple(
                        symbol
                        for symbol in production.rhs
                        if symbol.name.lower() not in {"epsilon", "eps", "ε"}
                    )
                )
            )

    return _dedupe_errors(errors)


def _collect_lr_syntax_errors(
    table: Any,
    tokens: list[Token],
    *,
    max_errors: int = 25,
) -> list[dict[str, Any]]:
    input_tokens = _normalize_input(tokens)
    stack: list[int | Symbol] = [0]
    position = 0
    errors: list[dict[str, Any]] = []
    max_steps = max(200, len(input_tokens) * 50)

    for _ in range(max_steps):
        if len(errors) >= max_errors:
            break

        state = _top_state(stack)
        current = input_tokens[position]
        action = table.action_for(state, current.terminal)

        if action.kind == "shift":
            stack.extend([current.terminal, action.target])
            position += 1
            continue

        if action.kind == "reduce" and action.production is not None:
            production = action.production
            rhs_length = len(production.rhs)
            if rhs_length:
                del stack[-2 * rhs_length :]

            goto_source = _top_state(stack)
            target = table.goto_for(goto_source, production.lhs)
            if target is None:
                errors.append(
                    _error(
                        "parser",
                        f"Missing GOTO[{goto_source}, {production.lhs.name}] after reduction",
                        current.line,
                        current.column,
                        current.terminal.name,
                    )
                )
                if current.terminal == EOF:
                    break
                position += 1
                continue

            stack.extend([production.lhs, target])
            continue

        if action.kind == "accept":
            break

        errors.append(
            _error(
                "parser",
                f"Unexpected token {current.terminal.name} in state {state}",
                current.line,
                current.column,
                current.terminal.name,
            )
        )
        if current.terminal == EOF:
            break
        position += 1

    return _dedupe_errors(errors)


def _dedupe_errors(errors: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []

    for error in errors:
        key = (
            error.get("source"),
            error.get("message"),
            error.get("line"),
            error.get("column"),
            error.get("token"),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(error)

    return result


def _translation_to_dict(
    input_text: str,
    tokens: list[Token],
    lexicon_text: str,
) -> dict[str, Any] | None:
    lexicon = _parse_lexicon(lexicon_text)
    if not lexicon:
        return None

    token_map = []
    for token in tokens:
        original = token.lexeme
        translated = lexicon.get(original.lower(), original)
        token_map.append(
            {
                "original": original,
                "translated": translated,
                "type": token.type,
            }
        )

    return {
        "original": input_text.strip(),
        "translated": " ".join(entry["translated"] for entry in token_map),
        "token_map": token_map,
    }


def _parse_lexicon(text: str) -> dict[str, str]:
    table: dict[str, str] = {}
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return table

    header = [part.strip().lower() for part in lines[0].split("\t")]
    has_header = any(name in header for name in {"original", "lexeme", "lexer_form", "spanish", "translation", "traduccion"})

    if has_header:
        key_index = _first_existing_index(header, ("original", "lexeme", "lexer_form", "qeqchi_form"))
        value_index = _first_existing_index(header, ("translation", "traduccion", "translated", "spanish", "espanol"))
        data_lines = lines[1:]
    else:
        key_index = 0
        value_index = 1
        data_lines = lines

    if key_index is None or value_index is None:
        return table

    for line in data_lines:
        parts = [part.strip() for part in line.split("\t")]
        if len(parts) <= max(key_index, value_index):
            continue
        key = parts[key_index].lower()
        value = parts[value_index]
        if key and value:
            table[key] = value

    return table


def _first_existing_index(values: list[str], names: Iterable[str]) -> int | None:
    for name in names:
        if name in values:
            return values.index(name)
    return None


def _syntax_tree_to_dict(tree: SyntaxTree | None) -> dict[str, Any] | None:
    if tree is None:
        return None
    return {
        "json": tree.to_dict(),
        "dot": tree.to_dot(),
        "text": tree.pretty_print(),
    }


def _normalize_input(tokens: list[Token]) -> list[_InputToken]:
    input_tokens = [
        _InputToken(Terminal(token.type), token.lexeme, token.line, token.column)
        for token in tokens
    ]
    if input_tokens and input_tokens[-1].terminal == EOF:
        return input_tokens

    line, column = _eof_location(input_tokens)
    input_tokens.append(_InputToken(EOF, EOF.name, line, column))
    return input_tokens


def _eof_location(tokens: list[_InputToken]) -> tuple[int, int]:
    if not tokens:
        return 1, 1

    last = tokens[-1]
    line = last.line
    column = last.column
    for character in last.lexeme:
        if character == "\n":
            line += 1
            column = 1
        else:
            column += 1
    return line, column


def _parse_error_from_tokens(message: str, tokens: list[Token]) -> dict[str, Any]:
    line, column = _eof_location(
        [_InputToken(Terminal(token.type), token.lexeme, token.line, token.column) for token in tokens]
    )
    token = "$"

    match = re.search(r"lookahead ([^ ]+)|found ([^ ]+)", message)
    if match is not None:
        token = next(group for group in match.groups() if group is not None)
        for original in tokens:
            if original.type == token:
                line = original.line
                column = original.column
                break

    return _error("parser", message, line, column, token)


def _token_to_dict(token: Token) -> dict[str, Any]:
    return {
        "type": token.type,
        "lexeme": token.lexeme,
        "line": token.line,
        "column": token.column,
    }


def _step_to_dict(step: Any) -> dict[str, Any]:
    return {
        "stack": list(step.stack),
        "remaining_input": list(step.remaining_input),
        "action": step.action,
    }


def _error(source: str, message: str, line: int, column: int, token: str | None = None) -> dict[str, Any]:
    return {
        "source": source,
        "message": message,
        "line": line,
        "column": column,
        "token": token,
    }


def _top_state(stack: list[int | Symbol]) -> int:
    state = stack[-1]
    if not isinstance(state, int):
        raise ValueError("Invalid LR stack: top entry is not a state.")
    return state


def _stack_entry_name(entry: int | Symbol) -> str:
    if isinstance(entry, int):
        return str(entry)
    return entry.name


def _action_to_string(action: Any) -> str:
    if action.kind == "shift":
        return f"shift {action.target}"
    if action.kind == "reduce" and action.production is not None:
        return f"reduce {_format_production(action.production)}"
    return action.kind


def _format_production(production: Production) -> str:
    rhs = " ".join(symbol.name for symbol in production.rhs)
    return f"{production.lhs.name} -> {rhs or 'epsilon'}"


def _dot_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
