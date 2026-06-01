from pathlib import Path

from dlp_parserstudio.ide.analysis import analyze_source


EXAMPLES = Path("examples")


def test_conflict_shift_reduce_example_shows_parallel_branches() -> None:
    result = analyze_source(
        (EXAMPLES / "conflict_shift_reduce.yalex").read_text(encoding="utf-8"),
        (EXAMPLES / "conflict_shift_reduce.yapar").read_text(encoding="utf-8"),
        (EXAMPLES / "conflict_shift_reduce_input.txt").read_text(encoding="utf-8"),
        "LR(0)",
    )

    conflicts = result["conflicts"]
    branches = result["parallel_branches"]

    assert [token["type"] for token in result["tokens"]] == ["ID", "PLUS", "ID", "PLUS", "ID"]
    assert any(conflict["kind"] == "shift/reduce" for conflict in conflicts)
    assert any(conflict["lookahead"] == "PLUS" for conflict in conflicts)
    assert any("shift" in conflict["existing"] or "shift" in conflict["incoming"] for conflict in conflicts)
    assert any("reduce" in conflict["existing"] or "reduce" in conflict["incoming"] for conflict in conflicts)
    assert any("shift/reduce conflict" in entry["action"] for entry in result["tables"]["action"])
    assert {branch["name"] for branch in branches} == {"shift", "reduce"}
    assert all(branch["result"] in {"accepted", "rejected", "error"} for branch in branches)
