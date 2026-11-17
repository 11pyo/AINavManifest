# -*- coding: utf-8 -*-
"""Oracle validity: every success criterion fires when its effect is produced directly
(no agent involved) and does not fire on an untouched run. A criterion that cannot fire
would make a 0 % attack success rate meaningless.
"""
import json

import pytest

pw = pytest.importorskip("playwright.sync_api")

from adversarial.attacks import (ARMS, ATTACKS, BY_ID, CANARY, SIGNATURE_ATTACKS, RunRecord, collect_state,
                                 model_leaks)
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


ALL = ATTACKS + SIGNATURE_ATTACKS


@pytest.mark.parametrize("attack", ALL, ids=[a.id for a in ALL])
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


def test_signature_attacks_are_what_they_claim_to_be(site):
    """The signature layer of each registered signature attack, checked directly (no browser, no agent):
    the forged ones must NOT verify under the designated key, the valid ones MUST."""
    from afrm.jws import verify_manifest
    must_verify = {"A37", "A38", "A39", "A40"}
    must_fail = {"A30", "A30b", "A31", "A32", "A33", "A34", "A35", "A36"}
    seen = set()
    for a in SIGNATURE_ATTACKS:
        raw = a.build(site)
        m = json.loads(raw.decode("utf-8"))
        assert a.id == "A31b" or CANARY in raw.decode("utf-8") or a.id.startswith("A38c"), a.id
        if not a.designated:
            continue
        out = verify_manifest(m, a.designated(site)[site.origin])
        if a.id in must_verify:
            assert out.verified, (a.id, out.reasons)
        elif a.id in must_fail:
            assert not out.verified, a.id
        seen.add(a.id)
    assert must_verify | must_fail <= seen
    assert not json.loads(BY_ID["A38c"].build(site).decode()).get("signatures")
    assert BY_ID["A38c"].designated is None
