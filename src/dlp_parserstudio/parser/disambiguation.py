"""Educational ambiguity suggestions and safe automatic rewrites."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from dlp_parserstudio.core.grammar import Grammar, NonTerminal, Production, Terminal
from dlp_parserstudio.parser.first_follow import calculate_first_sets, first_of_sequence


@dataclass(frozen=True)
class DisambiguationSuggestion:
    kind: str
    title: str
    problem: str
    explanation: str
    recommended_method: str
    suggested_grammar: str = ""
    confidence: str = "medium"
    can_apply: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_disambiguation(
    grammar: Grammar,
    *,
    conflicts: Iterable[Any] | None = None,
    method: str = "",
    branch_results: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """Analyze known educational ambiguity/conflict patterns."""

    conflict_list = list(conflicts or ())
    suggestions: list[DisambiguationSuggestion] = []
    expression = _detect_expression_ambiguity(grammar)
    if expression is not None:
        suggestions.append(expression)

    suggestions.extend(_detect_direct_common_prefixes(grammar))
    suggestions.extend(_detect_indirect_common_prefixes(grammar))
    suggestions.extend(_suggest_from_conflicts(conflict_list, method, list(branch_results or ())))
    suggestions = _deduplicate_suggestions(suggestions)

    if not suggestions:
        return {
            "has_suggestions": False,
            "summary": "No se detectaron patrones conocidos de ambiguedad o conflicto.",
            "suggestions": [],
        }

    return {
        "has_suggestions": True,
        "summary": f"Se encontraron {len(suggestions)} sugerencia(s) de desambiguacion.",
        "suggestions": [suggestion.to_dict() for suggestion in suggestions],
    }


def auto_resolve_disambiguation(
    grammar: Grammar,
    *,
    conflicts: Iterable[Any] | None = None,
    method: str = "",
    branch_results: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """Apply the best safe rewrite available for known patterns."""

    analysis = analyze_disambiguation(
        grammar,
        conflicts=conflicts,
        method=method,
        branch_results=branch_results,
    )
    suggestions = analysis["suggestions"]
    priorities = {
        "precedence_grammar": 0,
        "left_factoring": 1,
        "left_factoring_indirect": 2,
    }
    candidates = [
        suggestion
        for suggestion in suggestions
        if suggestion.get("can_apply") and suggestion.get("suggested_grammar")
    ]
    candidates.sort(key=lambda item: priorities.get(item["kind"], 99))

    if not candidates:
        return {
            **analysis,
            "resolved": False,
            "resolved_yapar": "",
            "applied_suggestion": None,
            "summary": (
                "No hay una reescritura automatica segura para esta gramatica. "
                "Revise las sugerencias manuales."
            ),
            "limitations": _limitations_text(),
        }

    chosen = candidates[0]
    return {
        **analysis,
        "resolved": True,
        "resolved_yapar": chosen["suggested_grammar"],
        "applied_suggestion": chosen,
        "summary": f"Se aplico automaticamente: {chosen['title']}.",
        "limitations": _limitations_text(),
    }


def _detect_expression_ambiguity(grammar: Grammar) -> DisambiguationSuggestion | None:
    for non_terminal in sorted(grammar.non_terminals, key=lambda symbol: symbol.name):
        productions = grammar.producciones_de(non_terminal)
        operators: list[str] = []
        base_terminals: set[str] = set()

        for production in productions:
            rhs = production.rhs
            if (
                len(rhs) == 3
                and rhs[0] == non_terminal
                and isinstance(rhs[1], Terminal)
                and rhs[2] == non_terminal
            ):
                operators.append(rhs[1].name)
            elif non_terminal not in rhs:
                base_terminals.update(symbol.name for symbol in rhs if isinstance(symbol, Terminal))

        if not operators:
            continue

        upper = {operator.upper() for operator in operators}
        has_plus = bool(upper.intersection({"PLUS", "SUM", "ADD", "MINUS"}))
        has_times = bool(upper.intersection({"TIMES", "STAR", "MULT", "MUL", "DIVIDE", "SLASH"}))
        if not (has_plus and has_times) and len(set(operators)) < 2:
            continue

        return DisambiguationSuggestion(
            kind="precedence_grammar",
            title="Resolver expresiones con precedencia",
            problem=(
                f"{non_terminal.name} usa recursion binaria directa "
                f"con operadores {', '.join(sorted(set(operators)))}."
            ),
            explanation=(
                "La forma E -> E op E no define precedencia ni asociatividad. "
                "El programa puede reemplazarla por niveles expr, term y factor."
            ),
            recommended_method="Aplicar reescritura automatica expr/term/factor.",
            suggested_grammar=_expression_grammar_suggestion(grammar, operators, base_terminals),
            confidence="high",
            can_apply=True,
        )

    return None


def _detect_direct_common_prefixes(grammar: Grammar) -> list[DisambiguationSuggestion]:
    suggestions: list[DisambiguationSuggestion] = []

    for non_terminal in sorted(grammar.non_terminals, key=lambda symbol: symbol.name):
        groups: dict[str, list[Production]] = defaultdict(list)
        for production in grammar.producciones_de(non_terminal):
            if production.rhs:
                groups[production.rhs[0].name].append(production)

        for prefix, productions in sorted(groups.items()):
            if len(productions) < 2:
                continue
            suggested = _left_factored_grammar(grammar, non_terminal, prefix, productions)
            suggestions.append(
                DisambiguationSuggestion(
                    kind="left_factoring",
                    title="Factorizacion izquierda directa",
                    problem=(
                        f"{non_terminal.name} tiene {len(productions)} alternativas "
                        f"que empiezan con {prefix}."
                    ),
                    explanation=(
                        "El parser LL(1) no puede elegir entre alternativas que comparten "
                        "el mismo primer simbolo."
                    ),
                    recommended_method="Factorizar el prefijo comun.",
                    suggested_grammar=suggested,
                    confidence="high",
                    can_apply=bool(suggested),
                )
            )

    return suggestions


def _detect_indirect_common_prefixes(grammar: Grammar) -> list[DisambiguationSuggestion]:
    suggestions: list[DisambiguationSuggestion] = []
    first_sets = calculate_first_sets(grammar)

    for non_terminal in sorted(grammar.non_terminals, key=lambda symbol: symbol.name):
        first_to_productions: dict[str, list[Production]] = defaultdict(list)
        for production in grammar.producciones_de(non_terminal):
            for symbol in first_of_sequence(production.rhs, first_sets):
                if isinstance(symbol, Terminal):
                    first_to_productions[symbol.name].append(production)

        for terminal_name, productions in sorted(first_to_productions.items()):
            unique = _unique_productions(productions)
            if len(unique) < 2 or _has_same_direct_prefix(unique):
                continue
            suggested = _jsx_left_factored_grammar(grammar, non_terminal, terminal_name)
            suggestions.append(
                DisambiguationSuggestion(
                    kind="left_factoring_indirect",
                    title="Factorizacion izquierda indirecta",
                    problem=(
                        f"Varias alternativas de {non_terminal.name} pueden iniciar con "
                        f"FIRST = {terminal_name}."
                    ),
                    explanation=(
                        "Aunque las alternativas empiezan con no terminales distintos, "
                        "sus FIRST se cruzan."
                    ),
                    recommended_method="Factorizar desde el primer terminal compartido.",
                    suggested_grammar=suggested,
                    confidence="medium",
                    can_apply=bool(suggested),
                )
            )

    return suggestions


def _suggest_from_conflicts(
    conflicts: list[Any],
    method: str,
    branches: list[Any],
) -> list[DisambiguationSuggestion]:
    suggestions: list[DisambiguationSuggestion] = []

    for conflict in conflicts:
        kind = _conflict_value(conflict, "kind", "")
        if kind != "shift/reduce":
            continue

        state = _conflict_value(conflict, "state", "-")
        lookahead = _conflict_value(conflict, "lookahead", _conflict_value(conflict, "non_terminal", "-"))
        existing = _action_text(_conflict_value(conflict, "existing", ""))
        incoming = _action_text(_conflict_value(conflict, "incoming", ""))
        joined = f"{existing} {incoming}".lower()

        if "-> epsilon" in joined:
            suggestions.append(
                DisambiguationSuggestion(
                    kind="lr0_epsilon_conflict",
                    title="Conflicto LR(0) con epsilon",
                    problem=f"En ACTION[{state}, {lookahead}] hay shift/reduce con una reduccion epsilon.",
                    explanation=(
                        "LR(0) reduce sin mirar el token siguiente. SLR(1) y LALR(1) "
                        "pueden limitar esa reduccion usando FOLLOW o lookahead."
                    ),
                    recommended_method="Probar SLR(1) o LALR(1).",
                    confidence="high" if "lr(0)" in method.lower() else "medium",
                )
            )
            continue

        branch_text = _branch_summary(branches)
        explanation = (
            f"En ACTION[{state}, {lookahead}] aparecen {existing} y {incoming}. "
            "La gramatica permite mas de un camino."
        )
        if branch_text:
            explanation = f"{explanation} Ramas: {branch_text}."
        suggestions.append(
            DisambiguationSuggestion(
                kind="shift_reduce_conflict",
                title="Conflicto shift/reduce",
                problem=f"ACTION[{state}, {lookahead}] contiene acciones incompatibles.",
                explanation=explanation,
                recommended_method=(
                    "Definir precedencia/asociatividad, reescribir la gramatica o "
                    "usar LALR(1) si el conflicto depende de lookahead."
                ),
                confidence="medium",
            )
        )

    return suggestions


def _expression_grammar_suggestion(
    grammar: Grammar,
    operators: Iterable[str],
    base_terminals: set[str],
) -> str:
    by_upper = {operator.upper(): operator for operator in operators}
    plus = _choose_existing(by_upper, ("PLUS", "SUM", "ADD", "MINUS"), "PLUS")
    times = _choose_existing(by_upper, ("TIMES", "STAR", "MULT", "MUL", "DIVIDE", "SLASH"), "TIMES")

    terminals = {terminal.name for terminal in grammar.terminals}
    terminals.update({plus, times})
    factors = [name for name in ("NUMBER", "ID") if name in terminals or name in base_terminals]
    if not factors:
        factors = sorted(base_terminals) or ["ID"]
        terminals.update(factors)

    factor_alternatives = [*factors]
    if {"LPAREN", "RPAREN"}.issubset(terminals):
        factor_alternatives.append("LPAREN expr RPAREN")

    lines = [
        f"%token {' '.join(sorted(terminals))}",
        "%ignore WS",
        "%start expr",
        "",
        "%%",
        "expr : term exprp ;",
        f"exprp : {plus} term exprp | epsilon ;",
        "term : factor termp ;",
        f"termp : {times} factor termp | epsilon ;",
        f"factor : {' | '.join(factor_alternatives)} ;",
    ]
    return "\n".join(lines)


def _left_factored_grammar(
    grammar: Grammar,
    non_terminal: NonTerminal,
    prefix: str,
    grouped: list[Production],
) -> str:
    tail = _unique_tail_name(grammar, non_terminal.name)
    replacement: dict[str, list[tuple[str, ...]]] = defaultdict(list)
    grouped_set = set(grouped)

    for production in grammar.productions:
        if production.lhs != non_terminal or production not in grouped_set:
            replacement[production.lhs.name].append(tuple(symbol.name for symbol in production.rhs))

    replacement[non_terminal.name].append((prefix, tail))
    for production in grouped:
        replacement[tail].append(tuple(symbol.name for symbol in production.rhs[1:]))

    return _mapping_to_yapar(grammar, replacement)


def _jsx_left_factored_grammar(grammar: Grammar, non_terminal: NonTerminal, terminal_name: str) -> str:
    names = {symbol.name for symbol in grammar.non_terminals}
    if non_terminal.name != "element" or terminal_name != "OPEN":
        return ""
    required = {"document", "element", "close_tag", "element_name", "props", "prop", "children", "child", "text"}
    if not required.issubset(names):
        return ""

    replacement: dict[str, list[tuple[str, ...]]] = defaultdict(list)
    skip = {"element", "normal_element", "self_closing_element", "open_tag"}
    for production in grammar.productions:
        if production.lhs.name not in skip:
            replacement[production.lhs.name].append(tuple(symbol.name for symbol in production.rhs))

    replacement["element"].append(("OPEN", "element_name", "props", "element_tail"))
    replacement["element_tail"].append(("CLOSE", "children", "close_tag"))
    replacement["element_tail"].append(("SELF_CLOSE",))
    return _mapping_to_yapar(grammar, _ordered_mapping(replacement, ("document", "element", "element_tail")))


def _mapping_to_yapar(grammar: Grammar, productions: Mapping[str, list[tuple[str, ...]]]) -> str:
    terminals = " ".join(sorted(terminal.name for terminal in grammar.terminals))
    lines = [f"%token {terminals}", "%ignore WS", f"%start {grammar.start_symbol.name}", "", "%%"]
    for lhs, alternatives in productions.items():
        rendered = [" ".join(rhs) if rhs else "epsilon" for rhs in alternatives]
        lines.append(f"{lhs} : {' | '.join(rendered)} ;")
    return "\n".join(lines)


def _ordered_mapping(
    productions: Mapping[str, list[tuple[str, ...]]],
    preferred: Iterable[str],
) -> dict[str, list[tuple[str, ...]]]:
    ordered: dict[str, list[tuple[str, ...]]] = {}
    for name in preferred:
        if name in productions:
            ordered[name] = productions[name]
    for name in sorted(productions):
        if name not in ordered:
            ordered[name] = productions[name]
    return ordered


def _choose_existing(options: Mapping[str, str], preferred: Iterable[str], fallback: str) -> str:
    for name in preferred:
        if name in options:
            return options[name]
    return fallback


def _unique_tail_name(grammar: Grammar, base: str) -> str:
    existing = {symbol.name for symbol in grammar.non_terminals}
    candidate = f"{base}_tail"
    while candidate in existing:
        candidate = f"{candidate}_tail"
    return candidate


def _unique_productions(productions: Iterable[Production]) -> list[Production]:
    seen: set[Production] = set()
    unique: list[Production] = []
    for production in productions:
        if production not in seen:
            seen.add(production)
            unique.append(production)
    return unique


def _has_same_direct_prefix(productions: Iterable[Production]) -> bool:
    prefixes = {production.rhs[0].name for production in productions if production.rhs}
    return len(prefixes) == 1


def _conflict_value(conflict: Any, key: str, default: Any) -> Any:
    if isinstance(conflict, Mapping):
        return conflict.get(key, default)
    return getattr(conflict, key, default)


def _action_text(action: Any) -> str:
    if isinstance(action, str):
        return action
    kind = getattr(action, "kind", None)
    target = getattr(action, "target", None)
    production = getattr(action, "production", None)
    if kind == "shift":
        return f"shift {target}"
    if kind == "reduce" and production is not None:
        rhs = " ".join(symbol.name for symbol in production.rhs) if production.rhs else "epsilon"
        return f"reduce {production.lhs.name} -> {rhs}"
    return str(action or "")


def _branch_summary(branches: Iterable[Any]) -> str:
    parts: list[str] = []
    for branch in branches:
        if isinstance(branch, Mapping):
            name = branch.get("name", "-")
            result = branch.get("result", "-")
        else:
            name = getattr(branch, "name", "-")
            result = getattr(branch, "result", "-")
        parts.append(f"{name} -> {result}")
    return "; ".join(parts)


def _deduplicate_suggestions(suggestions: Iterable[DisambiguationSuggestion]) -> list[DisambiguationSuggestion]:
    seen: set[tuple[str, str]] = set()
    unique: list[DisambiguationSuggestion] = []
    for suggestion in suggestions:
        key = (suggestion.kind, suggestion.problem)
        if key in seen:
            continue
        seen.add(key)
        unique.append(suggestion)
    return unique


def _limitations_text() -> str:
    return (
        "La ambiguedad general de gramaticas libres de contexto no se puede resolver "
        "de forma completa para todos los casos. Este modo aplica reescrituras seguras "
        "para patrones educativos reconocidos."
    )
