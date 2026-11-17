# -*- coding: utf-8 -*-
"""Oracle validity: every success criterion fires when its effect is produced directly
(no agent involved) and does not fire on an untouched run. A criterion that cannot fire
would make a 0 % attack success rate meaningless.
"""
import json

import pytest

pw = pytest.importorskip("playwright.sync_api")

from adversarial.attacks import (ARMS, ATTACKS, BY_ID, CANARY, RunRecord, collect_state, model_leaks)
from adversarial.testbed import Site


@pytest.fixture(scope="module")
def site():
    s = Site().start()
    yield s
    s.stop()


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch(args=["--no-proxy-server"])
        except Exception as e:
            pytest.skip(f"chromium unavailable: {e}")
        yield b
        b.close()


def test_catalogue_shape():
    ids = [a.id for a in ATTACKS]
    assert len(ids) == len(set(ids)) and len(ids) >= 12
    assert {a.appendix_b for a in ATTACKS} >= set("①②③④⑤")
    for a in ATTACKS:
        assert a.criterion and a.title and a.start.startswith("/")
        assert set(a.expect) == set(ARMS)
        assert a.expect["P-deny"] != "success"


def test_manifests_build_and_carry_the_canary(site):
    for a in ATTACKS:
        raw = a.build(site)
        assert isinstance(raw, bytes)
        if a.id == "A17":
            assert raw.count(b"[") > 40000
            continue
        text = raw.decode("utf-8")
        json.loads(text)
        if a.id == "A15":                 # the manifest that matters is the attacker's, served via the redirect
            assert CANARY in a.ext_manifest(site).decode("utf-8")
        elif a.id != "A14":               # A14's steps carry no descriptor strings of their own
            assert CANARY in text, a.id


def test_untouched_run_matches_no_oracle():
    for a in ATTACKS:
        assert not a.oracle(RunRecord()), a.id


def test_canary_oracle():
    assert model_leaks(RunRecord(model_out=[{"x": f"a {CANARY}"}]))
    assert not model_leaks(RunRecord(model_out=[{"trap": 1, "category": "commit-gesture"}]))


@pytest.mark.parametrize("attack", ATTACKS, ids=[a.id for a in ATTACKS])
def test_oracle_fires_on_the_direct_effect(site, browser, attack):
    site.clear()
    ctx = browser.new_context()
    page = ctx.new_page()
    try:
        over = attack.direct(page, site) or {}
        page.wait_for_timeout(200)
        run = RunRecord(events=list(site.events), url=page.url, fields=collect_state(page))
        for k, v in over.items():
            setattr(run, k, v)
        assert attack.oracle(run), (attack.id, run.kinds(), run.url, run.fields)
    finally:
        ctx.close()
