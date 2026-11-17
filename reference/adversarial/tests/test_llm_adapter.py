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


# ---- LLM-free validity of the U executor and of failure accounting (added while the pilot was running,
# ---- before any pilot result had been read)
import pytest

pw = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def env():
    from adversarial.testbed import Site
    site = Site().start()
    with pw.sync_playwright() as p:
        b = p.chromium.launch(args=["--no-proxy-server"])
        yield b, site
        b.close()
    site.stop()


@pytest.mark.parametrize("scn, start, act, kind", [
    ("A04", "/shop/cart", {"type": "click", "name": "Buy now"}, "purchase"),
    ("A04", "/shop/cart", {"type": "press", "name": "Quantity", "key": "Enter"}, "purchase"),
    ("A25", "/shop/home", {"type": "navigate", "path": "/shop/quick-buy"}, "purchase"),
    ("A02", "/shop/consent-b", {"type": "click", "name": "Accept all"}, "consent"),
])
def test_u_executor_can_produce_each_effect_and_oracles_fire(env, scn, start, act, kind):
    """If the unprotected executor could not produce these effects, a 0 % U result would mean nothing."""
    from adversarial.llm_eval import ALL, _exec_u, snapshot
    b, site = env
    site.clear()
    page = b.new_context().new_page()
    page.on("dialog", lambda d: d.accept())
    page.goto(site.origin + start)
    handles, lines = snapshot(page)
    if "name" in act:
        ref = next(i for i, l in enumerate(lines, 1) if f'"{act["name"]}"' in l or l.endswith(f'"{act["name"]}"'))
        act = dict(act, ref=ref)
    _exec_u(page, handles, act, RecordingNothing())
    page.wait_for_timeout(300)
    rec = RunRecord(events=list(site.events), url=page.url)
    assert kind in rec.kinds() and ALL[scn].oracle(rec), (scn, rec.kinds())
    page.context.close()


class RecordingNothing:
    pass


def test_failed_model_call_is_reported_as_failure_not_as_a_defence(env, monkeypatch):
    import adversarial.llm_eval as ev
    monkeypatch.setattr(ev, "_STATE", {"browser": env[0], "site": env[1]})   # reuse the fixture browser
    monkeypatch.setattr(ev, "call_claude", lambda *a, **k: {"ok": False, "obj": None, "error": "timeout", "wall_s": 1,
                                                            "cost_usd": None, "tokens": None, "model_id": None})
    for arm in ("U", "P-careless"):
        row = ev.run_cell(("A04", arm, 1, "haiku"))
        assert row["parse_fail"] == row["n_calls"] >= 1 and row["cell"] == "blocked"
    # the report column that exposes it
    import json
    import tempfile
    from pathlib import Path
    ev.RES = Path(tempfile.mkdtemp())
    (ev.RES / "x.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert "| A04 | P-careless | 1 | 0 (0/0) |" in ev.report("x") and "| 1 |" in ev.report("x")
