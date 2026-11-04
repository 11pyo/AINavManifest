# -*- coding: utf-8 -*-
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from afrm.jcs import canonicalize, manifest_digest
from afrm.validator import ManifestRejected, load_for_agent, parse_i_json, validate

FIX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)
URL = "https://erp.example.com/.well-known/ai-friction-manifest.json"


def appendix_a():
    return json.loads((FIX / "appendix_a.json").read_text(encoding="utf-8"))


def raw(m):
    return json.dumps(m).encode("utf-8")


def test_appendix_a_is_valid():
    rep = validate(appendix_a(), retrieved_from=URL, now=NOW)
    assert rep.ok, rep.errors


def test_jcs_rfc8785_vector():
    # RFC 8785 Section 3.2.2 example
    src = ('{"numbers":[333333333.33333329,1E30,4.50,2e-3,0.000000000000000000000000001],'
           '"string":"\\u20ac$\\u000F\\u000aA\'\\u0042\\u0022\\u005c\\\\\\"\\/",'
           '"literals":[null,true,false]}')
    assert canonicalize(json.loads(src)) == (
        '{"literals":[null,true,false],"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27],'
        '"string":"€$\\u000f\\nA\'B\\"\\\\\\\\\\"/"}')


def test_digest_is_key_order_independent():
    m = appendix_a()
    reordered = dict(reversed(list(m.items())))
    assert manifest_digest(m) == manifest_digest(reordered)


@pytest.mark.parametrize("payload, why", [
    (b'{"version":"2.0","version":"2.0"}', "duplicate"),
    (b"\xef\xbb\xbf{}", "byte order mark"),
    (b'{"n": 9007199254740993}', "IEEE"),
    (b"[]", "not an object"),
])
def test_i_json_rejections(payload, why):
    with pytest.raises(ManifestRejected, match=why):
        parse_i_json(payload)


def test_size_limit():
    m = appendix_a()
    m["pad"] = "x" * 262144
    with pytest.raises(ManifestRejected, match="octets"):
        load_for_agent(raw(m), URL, now=NOW)


def test_version_1_rejected():
    m = appendix_a()
    m["version"] = "1.0"
    with pytest.raises(ManifestRejected, match="version"):
        load_for_agent(raw(m), URL, now=NOW)


def test_origin_mismatch_rejected():
    with pytest.raises(ManifestRejected, match="serving origin"):
        load_for_agent(raw(appendix_a()), "https://evil.example/.well-known/ai-friction-manifest.json", now=NOW)


def test_expired_rejected():
    with pytest.raises(ManifestRejected, match="expired"):
        load_for_agent(raw(appendix_a()), URL, now=datetime(2027, 1, 1, tzinfo=timezone.utc))


def test_http_origin_rejected_unless_loopback():
    m = appendix_a()
    m["origin"] = "http://erp.example.com"
    assert any("HTTPS" in e for e in validate(m, now=NOW).errors)
    m["origin"] = "http://127.0.0.1:6100"
    rep = validate(m, now=NOW)
    assert rep.ok and any("loopback" in w for w in rep.warnings)


@pytest.mark.parametrize("mutate", [
    lambda m: m["knownTraps"][0]["recovery"].append({"action": "fill", "locator": {"role": "textbox"}}),
    lambda m: m["knownTraps"][0]["recovery"][0].update(value="Z051"),
    lambda m: m["knownTraps"][0]["locator"].update(xpath="//td"),
    lambda m: m["knownTraps"][0].update(escapeAction="press Enter"),
    lambda m: m["knownTraps"][0]["recovery"].pop(),           # wait removed: still valid -> control
    lambda m: m["knownTraps"][0].pop("condition"),            # wait without condition
    lambda m: m["knownTraps"][0]["recovery"][0].update(key="F4"),
    lambda m: m["knownTraps"][0].update(category="cross-origin-iframe"),
])
def test_descriptor_fail_closed(mutate):
    m = appendix_a()
    mutate(m)
    usable, rep = load_for_agent(raw(m), URL, now=NOW)
    if rep.ok:     # the control mutation (dropping the wait step) is legal
        assert len(usable["knownTraps"]) == 1
        return
    assert usable["knownTraps"] == []            # the trap is ignored ...
    assert len(usable["fieldHints"]) == 2        # ... the rest of the manifest is kept


@pytest.mark.parametrize("target", ["/maint/x?y=1", "/maint/x#f", "//evil.example/maint/", "/other/", "https://erp.example.com/maint/"])
def test_bad_shortcut_targets(target):
    m = appendix_a()
    m["shortcuts"][0]["target"] = target
    usable, rep = load_for_agent(raw(m), URL, now=NOW)
    assert usable["shortcuts"] == []


def test_allowed_values_pattern_and_when_reference():
    m = appendix_a()
    m["fieldHints"][1]["allowedValues"] = ["Z051 (raw material)"]
    m2 = appendix_a()
    m2["fieldHints"][1]["when"] = {"plant": "1000"}
    for bad in (m, m2):
        usable, _ = load_for_agent(raw(bad), URL, now=NOW)
        assert [h["fieldId"] for h in usable["fieldHints"]] == ["companyCode"]


def test_duplicate_ids_invalidate_both():
    m = appendix_a()
    m["knownTraps"].append(copy.deepcopy(m["knownTraps"][0]))
    usable, rep = load_for_agent(raw(m), URL, now=NOW)
    assert usable["knownTraps"] == [] and any("not unique" in e for e in rep.errors)


def test_removed_members_warn():
    m = appendix_a()
    m["publisher"] = "erp.example.com"
    rep = validate(m, retrieved_from=URL, now=NOW)
    assert rep.ok and any("removed" in w for w in rep.warnings)
