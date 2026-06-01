"""Exploratory parallel branching for shift/reduce conflicts."""

from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Iterable

from dlp_parserstudio.core.grammar import Grammar, NonTerminal, Production, Symbol, Terminal
from dlp_parserstudio.parser.first_follow import EOF
from dlp_parserstudio.parser.slr import build_slr_table


@dataclass(frozen=True)
class ConflictBranchStep:
    """One step recorded inside an exploratory conflict branch."""

    stack: tuple[str, ...]
    remaining_input: tuple[str, ...]
    action: str

    @property
    def input_remaining(self) -> tuple[str, ...]:
        return self.remaining_input

    @property
    def input_restante(self) -> tuple[str, ...]:
        return self.remaining_input

    @property
    def accion(self) -> str:
        return self.action


@dataclass(frozen=True)
class ConflictBranch:
    """Result of one conceptual branch through a shift/reduce conflict."""

    name: str
    chosen_action: str
    stack: tuple[str, ...]
    remaining_input: tuple[str, ...]
    result: str
    steps: tuple[ConflictBranchStep, ...]
    error: str | None = None

    @property
    def accion_elegida(self) -> str:
        return self.chosen_action

    @property
    def input_restante(self) -> tuple[str, ...]:
        return self.remaining_input


@dataclass(frozen=True)
class ParallelConflictResult:
    """Exploration output containing every branch that was executed."""

    branches: tuple[ConflictBranch, ...]
    conflict_state: int | None = None
    lookahead: str | None = None
    executor_type: str = "none"
    executor_note: str = "No shift/reduce conflict was explored."

    def __iter__(self):
        return iter(self.branches)

    def __len__(self) -> int:
        return len(self.branches)


@dataclass(frozen=True)
class _InputToken:
    terminal: Terminal
    lexeme: str
    line: int
    column: int


@dataclass(frozen=True)
class _ConflictPoint:
    stack: tuple[int | Symbol, ...]
    position: int
    steps: tuple[ConflictBranchStep, ...]
    conflict: Any


class ParallelConflictExplorer:
    """Runs shift/reduce alternatives without replacing the main parser."""

    def __init__(self, table: Any) -> None:
        self.table = table

    @classmethod
    def from_grammar(cls, grammar: Grammar) -> ParallelConflictExplorer:
        return cls(build_slr_table(grammar))

    def explore(
        self,
        tokens: Iterable[object],
        *,
        max_steps: int = 1000,
        executor: str = "auto",
    ) -> ParallelConflictResult:
        input_tokens = _normalize_input(tokens)
        conflict_point = _run_until_shift_reduce_conflict(
            self.table,
            input_tokens,
            max_steps=max_steps,
        )

        if conflict_point is None:
            return ParallelConflictResult(())

        shift_action, reduce_action = _split_shift_reduce_actions(conflict_point.conflict)
        jobs = [
            ("shift", shift_action),
            ("reduce", reduce_action),
        ]

        branches, executor_type, executor_note = _run_branch_jobs(
            self.table,
            input_tokens,
            conflict_point,
            jobs,
            max_steps,
            executor,
        )

        return ParallelConflictResult(
            branches,
            conflict_state=conflict_point.conflict.state,
            lookahead=conflict_point.conflict.lookahead.name,
            executor_type=executor_type,
            executor_note=executor_note,
        )


def explore_shift_reduce_conflict(
    grammar: Grammar,
    tokens: Iterable[object],
    *,
    table: Any | None = None,
    max_steps: int = 1000,
    executor: str = "auto",
) -> ParallelConflictResult:
    """Explore the first reachable shift/reduce conflict for an input."""

    return ParallelConflictExplorer(table or build_slr_table(grammar)).explore(
        tokens,
        max_steps=max_steps,
        executor=executor,
    )


def explore_shift_reduce_branches(
    grammar: Grammar,
    tokens: Iterable[object],
    *,
    table: Any | None = None,
    max_steps: int = 1000,
    executor: str = "auto",
) -> tuple[ConflictBranch, ...]:
    """Return only the branch list for the first reachable shift/reduce conflict."""

    return explore_shift_reduce_conflict(
        grammar,
        tokens,
        table=table,
        max_steps=max_steps,
        executor=executor,
    ).branches


def _run_branch_jobs(
    table: Any,
    input_tokens: list[_InputToken],
    conflict_point: _ConflictPoint,
    jobs: list[tuple[str, Any]],
    max_steps: int,
    executor: str,
) -> tuple[tuple[ConflictBranch, ...], str, str]:
    executor = executor.lower()
    if executor not in {"auto", "process", "thread"}:
        raise ValueError("executor must be 'auto', 'process', or 'thread'.")

    if executor in {"auto", "process"}:
        if not _can_try_process_executor():
            branches = _run_jobs_with_executor(
                ThreadPoolExecutor,
                table,
                input_tokens,
                conflict_point,
                jobs,
                max_steps,
            )
            return (
                branches,
                "thread",
                "ProcessPoolExecutor unavailable in this runtime; used ThreadPoolExecutor fallback.",
            )

        try:
            return (
                _run_jobs_with_executor(
                    ProcessPoolExecutor,
                    table,
                    input_tokens,
                    conflict_point,
                    jobs,
                    max_steps,
                ),
                "process",
                "ProcessPoolExecutor used for branch exploration.",
            )
        except Exception as error:
            branches = _run_jobs_with_executor(
                ThreadPoolExecutor,
                table,
                input_tokens,
                conflict_point,
                jobs,
                max_steps,
            )
            return (
                branches,
                "thread",
                f"ProcessPoolExecutor unavailable; used ThreadPoolExecutor fallback ({type(error).__name__}).",
            )

    return (
        _run_jobs_with_executor(
            ThreadPoolExecutor,
            table,
            input_tokens,
            conflict_point,
            jobs,
            max_steps,
        ),
        "thread",
        "ThreadPoolExecutor used as requested.",
    )


def _can_try_process_executor() -> bool:
    main_module = sys.modules.get("__main__")
    main_file = getattr(main_module, "__file__", "")
    return bool(main_file and not str(main_file).startswith("<"))


def _run_jobs_with_executor(
    executor_cls: Any,
    table: Any,
    input_tokens: list[_InputToken],
    conflict_point: _ConflictPoint,
    jobs: list[tuple[str, Any]],
    max_steps: int,
) -> tuple[ConflictBranch, ...]:
    with executor_cls(max_workers=2) as pool:
        futures = [
            pool.submit(
                _run_branch,
                table,
                input_tokens,
                conflict_point,
                name,
                action,
                max_steps,
            )
            for name, action in jobs
        ]
        return tuple(future.result() for future in futures)


def _run_until_shift_reduce_conflict(
    table: Any,
    input_tokens: list[_InputToken],
    *,
    max_steps: int,
) -> _ConflictPoint | None:
    stack: list[int | Symbol] = [0]
    position = 0
    steps: list[ConflictBranchStep] = []

    for _ in range(max_steps):
        state = _top_state(stack)
        current_token = input_tokens[position]
        stack_view = tuple(_stack_entry_name(entry) for entry in stack)
        remaining_input = tuple(token.terminal.name for token in input_tokens[position:])
        conflict = _shift_reduce_conflict_for(table, state, current_token.terminal)

        if conflict is not None:
            steps.append(
                ConflictBranchStep(
                    stack_view,
                    remaining_input,
                    (
                        "shift/reduce conflict at "
                        f"ACTION[{state}, {current_token.terminal.name}]"
                    ),
                )
            )
            return _ConflictPoint(tuple(stack), position, tuple(steps), conflict)

        action = table.action_for(state, current_token.terminal)
        status = _apply_action(table, stack, input_tokens, position, action, steps)
        position = status.position

        if status.done:
            return None

    return None


@dataclass(frozen=True)
class _ActionStatus:
    position: int
    done: bool = False
    result: str | None = None
    error: str | None = None


def _run_branch(
    table: Any,
    input_tokens: list[_InputToken],
    conflict_point: _ConflictPoint,
    name: str,
    chosen_action: Any,
    max_steps: int,
) -> ConflictBranch:
    stack = list(conflict_point.stack)
    position = conflict_point.position
    steps = list(conflict_point.steps)
    steps.append(
        ConflictBranchStep(
            tuple(_stack_entry_name(entry) for entry in stack),
            tuple(token.terminal.name for token in input_tokens[position:]),
            f"choose {name}: {_action_label(chosen_action)}",
        )
    )

    status = _apply_action(table, stack, input_tokens, position, chosen_action, steps)
    position = status.position
    if status.done:
        return _branch_from_status(
            name,
            chosen_action,
            stack,
            input_tokens,
            position,
            steps,
            status,
        )

    for _ in range(max_steps):
        state = _top_state(stack)
        current_token = input_tokens[position]
        action = table.action_for(state, current_token.terminal)
        status = _apply_action(table, stack, input_tokens, position, action, steps)
        position = status.position

        if status.done:
            return _branch_from_status(
                name,
                chosen_action,
                stack,
                input_tokens,
                position,
                steps,
                status,
            )

    status = _ActionStatus(position, True, "error", "Maximum branch step count reached")
    return _branch_from_status(name, chosen_action, stack, input_tokens, position, steps, status)


def _branch_from_status(
    name: str,
    chosen_action: Any,
    stack: list[int | Symbol],
    input_tokens: list[_InputToken],
    position: int,
    steps: list[ConflictBranchStep],
    status: _ActionStatus,
) -> ConflictBranch:
    return ConflictBranch(
        name=name,
        chosen_action=_action_label(chosen_action),
        stack=tuple(_stack_entry_name(entry) for entry in stack),
        remaining_input=tuple(token.terminal.name for token in input_tokens[position:]),
        result=status.result or "error",
        steps=tuple(steps),
        error=status.error,
    )


def _apply_action(
    table: Any,
    stack: list[int | Symbol],
    input_tokens: list[_InputToken],
    position: int,
    action: Any,
    steps: list[ConflictBranchStep],
) -> _ActionStatus:
    state = _top_state(stack)
    current_token = input_tokens[position]
    stack_view = tuple(_stack_entry_name(entry) for entry in stack)
    remaining_input = tuple(token.terminal.name for token in input_tokens[position:])

    if action.kind == "shift":
        if action.target is None:
            error = "Shift action does not have a target state"
            steps.append(ConflictBranchStep(stack_view, remaining_input, f"error: {error}"))
            return _ActionStatus(position, True, "error", error)

        steps.append(
            ConflictBranchStep(
                stack_view,
                remaining_input,
                f"shift {current_token.terminal.name} and go to {action.target}",
            )
        )
        stack.extend([current_token.terminal, action.target])
        return _ActionStatus(position + 1)

    if action.kind == "reduce":
        production = action.production
        if production is None:
            error = "Reduce action does not have a production"
            steps.append(ConflictBranchStep(stack_view, remaining_input, f"error: {error}"))
            return _ActionStatus(position, True, "error", error)

        rhs_length = len(production.rhs)
        if rhs_length:
            del stack[-2 * rhs_length :]

        goto_source = _top_state(stack)
        target = table.goto_for(goto_source, production.lhs)
        if target is None:
            error = f"Missing GOTO[{goto_source}, {production.lhs.name}] after reduction"
            steps.append(ConflictBranchStep(stack_view, remaining_input, f"error: {error}"))
            return _ActionStatus(position, True, "error", error)

        steps.append(
            ConflictBranchStep(
                stack_view,
                remaining_input,
                f"reduce {_format_production(production)}",
            )
        )
        stack.extend([production.lhs, target])
        return _ActionStatus(position)

    if action.kind == "accept":
        steps.append(ConflictBranchStep(stack_view, remaining_input, "accept"))
        return _ActionStatus(position, True, "accepted")

    error = f"Unexpected token {current_token.terminal.name} in state {state}"
    steps.append(ConflictBranchStep(stack_view, remaining_input, f"error: {error}"))
    return _ActionStatus(position, True, "rejected", error)


def _shift_reduce_conflict_for(table: Any, state: int, lookahead: Terminal) -> Any | None:
    for conflict in getattr(table, "conflicts", ()):
        if (
            conflict.kind == "shift/reduce"
            and conflict.state == state
            and conflict.lookahead == lookahead
        ):
            return conflict
    return None


def _split_shift_reduce_actions(conflict: Any) -> tuple[Any, Any]:
    actions = (conflict.existing, conflict.incoming)
    shift_action = next(action for action in actions if action.kind == "shift")
    reduce_action = next(action for action in actions if action.kind == "reduce")
    return shift_action, reduce_action


def _normalize_input(tokens: Iterable[object]) -> list[_InputToken]:
    input_tokens = [_as_input_token(token) for token in tokens]
    if input_tokens and input_tokens[-1].terminal == EOF:
        return input_tokens

    line, column = _eof_location(input_tokens)
    input_tokens.append(_InputToken(EOF, EOF.name, line, column))
    return input_tokens


def _as_input_token(token: object) -> _InputToken:
    if isinstance(token, Terminal):
        terminal = EOF if token.name == EOF.name else token
        return _InputToken(terminal, terminal.name, 1, 1)

    if isinstance(token, str):
        terminal = EOF if token == EOF.name else Terminal(token)
        return _InputToken(terminal, token, 1, 1)

    token_type = getattr(token, "type", None)
    if isinstance(token_type, str):
        lexeme = getattr(token, "lexeme", token_type)
        line = getattr(token, "line", 1)
        column = getattr(token, "column", 1)
        terminal = EOF if token_type == EOF.name else Terminal(token_type)
        return _InputToken(terminal, str(lexeme), int(line), int(column))

    raise TypeError(
        "Conflict exploration input must contain token-like objects, Terminal, or str values."
    )


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


def _top_state(stack: list[int | Symbol]) -> int:
    state = stack[-1]
    if not isinstance(state, int):
        raise ValueError("Invalid conflict exploration stack: top entry is not a state.")
    return state


def _stack_entry_name(entry: int | Symbol) -> str:
    if isinstance(entry, int):
        return str(entry)
    return entry.name


def _action_label(action: Any) -> str:
    if action.kind == "shift":
        return f"shift {action.target}"
    if action.kind == "reduce" and action.production is not None:
        return f"reduce {_format_production(action.production)}"
    return action.kind


def _format_production(production: Production) -> str:
    rhs = " ".join(symbol.name for symbol in production.rhs)
    return f"{production.lhs.name} -> {rhs or 'epsilon'}"
