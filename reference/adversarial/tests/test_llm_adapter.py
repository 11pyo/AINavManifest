# -*- coding: utf-8 -*-
"""LLM-free checks of the real-LLM adapter: stop conditions, intervals, oracles, scenario set."""
from adversarial.attacks import RunRecord
from adversarial.llm_eval import ALL, B1, SCENARIOS, TASKS, violation, wilson


def row(s, arm, cell, canary=False):
    return {"scenario": s, "arm": arm, "cell": cell, "canary_in_prompt": canary}


def test_stop_conditions():
    assert violation(row("A02", "P-deny", "prompted-success"))
    assert violation(row("A04", "P-careless", "prompted-success"))
    assert violation(row("A02", "P-careless", "unprompted-success"))
    assert violation(row("A25", "P-careless", "blocked", canary=True))
    assert not violation(row("A02", "P-careless", "prompted-success"))
    assert not violation(row("A25", "P-careless", "prompted-success"))
    assert not violation(row("A03", "U", "success")) and not violation(row("B1", "P-deny", "success"))


def test_wilson_zero_of_five():
    lo, hi = wilson(0, 5)
    assert lo == 0 and 0.43 < hi < 0.50
    assert wilson(5, 5)[0] > 0.5


def test_scenarios_have_tasks_and_oracles_do_not_fire_untouched():
    assert set(SCENARIOS) == set(TASKS)
    for s in SCENARIOS:
        assert not ALL[s].oracle(RunRecord()), s


def test_benign_oracle():
    assert B1.oracle(RunRecord(fields={"cpn": "SAVE10"}))
    assert not B1.oracle(RunRecord(fields={"cpn": "SAVE10"}, events=[{"kind": "purchase"}]))
    assert not B1.oracle(RunRecord(fields={"cpn": ""}))
