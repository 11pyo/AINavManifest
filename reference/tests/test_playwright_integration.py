# -*- coding: utf-8 -*-
"""End-to-end: real HTTP discovery + Chromium + PEP (final -03 rules).

On a live page: Enter and click are "ask"; an HTTP 403 reached during recovery
stops it; confirm() stops; alerts are dismissed and recorded; every redirect of
a manifest-derived navigation is checked; discovery follows no redirect; the
'when' of a field hint resolves within the edited row.
"""
import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

pw = pytest.importorskip("playwright.sync_api")

from afrm.agent import ApproveAsk, DenyAsk, ManifestSession, ModelInterface
from afrm.discovery import fetch_manifest_bytes
from afrm.pep import ALLOW, ASK, DENY
from afrm.playwright_page import PlaywrightPage
from afrm.validator import ManifestRejected

PAGE = """<!doctype html><html><head><title>maint</title>
<link rel="ai-friction-manifest" href="/.well-known/ai-friction-manifest.json"></head><body>
<div role="status" aria-label="Row locked">Row locked</div>
<table role="grid" aria-label="Account categories">
 <tr><th role="columnheader">Material Type</th><th role="columnheader">Account Category Ref</th></tr>
 <tr><td role="gridcell">ROH</td><td role="gridcell" tabindex="0" id="c1">Z051</td></tr>
 <tr><td role="gridcell">HALB</td><td role="gridcell" tabindex="0">Z063</td></tr>
</table>
<button onclick="location.href='/maint/forbidden'">Save</button>
<script>
 const c = document.getElementById('c1');
 c.addEventListener('keydown', e => { if (e.key === 'Enter') {
   window.enterTrusted = e.isTrusted; document.querySelector('[role=status]').remove(); } });
 c.focus();
</script></body></html>"""

ROWS_PAGE = """<!doctype html><html><body>
<table role="grid" aria-label="Material types">
 <tr><th role="columnheader">Material Type</th><th role="columnheader">ARef</th></tr>
 <tr><td role="gridcell">ROH</td><td role="gridcell"><input aria-label="ARef" id="a1"></td></tr>
 <tr><td role="gridcell">HALB</td><td role="gridcell"><input aria-label="ARef" id="a2"></td></tr>
</table></body></html>"""

ALERT_PAGE = """<!doctype html><html><body><p>alert page</p>
<script>setTimeout(() => alert('Session will expire'), 300)</script></body></html>"""
CONFIRM_PAGE = """<!doctype html><html><body><div role="gridcell" tabindex="0" id="c">x</div>
<script>document.getElementById('c').focus(); setTimeout(() => confirm('Delete all rows?'), 300)</script></body></html>"""

SHORTCUT_TARGETS = ["/maint/hop-query", "/maint/hop-out", "/maint/hop-two", "/maint/hop-ok"]
REDIRECTS = {"/maint/hop-query": "/maint/screen?x=1", "/maint/hop-out": "/other/",
             "/maint/hop-two": "/maint/hop-out", "/maint/hop-ok": "/maint/rows"}


def manifest(origin):
    return {
        "version": "2.0", "origin": origin,
        "expires": (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope": ["/maint/"],
        "knownTraps": [
            {"trapId": "row-commit", "category": "commit-gesture",                      # trap 1
             "locator": {"role": "gridcell", "focused": True},
             "condition": {"visible": {"role": "status", "name": "Row locked"}},
             "recovery": [
                 {"action": "key", "key": "Enter", "locator": {"role": "gridcell", "focused": True}},
                 {"action": "wait", "timeoutMs": 2000},
                 {"action": "click", "locator": {"role": "button", "name": "Save"}}]},
            {"trapId": "expiry-alert", "category": "native-alert", "condition": {"dialog": "alert"},  # 2
             "recovery": [{"action": "dismissAlert"}]},
            {"trapId": "focus-cell", "category": "commit-gesture",                      # trap 3
             "locator": {"role": "gridcell", "focused": True},
             "recovery": [{"action": "key", "key": "Tab", "locator": {"role": "gridcell", "focused": True}}]},
        ],
        "fieldHints": [
            {"fieldId": "acctCatRef", "allowedValues": ["Z051", "Z063", "Z072"],
             "locator": {"role": "gridcell", "column": "Account Category Ref"}},
            {"fieldId": "materialType", "locator": {"role": "gridcell", "column": "Material Type"}},
            {"fieldId": "aref-roh", "locator": {"role": "textbox", "name": "ARef"},
             "when": {"materialType": "ROH"}, "allowedValues": ["Z051"]},
        ],
        "shortcuts": [{"shortcutId": f"s{i}", "target": t, "label": t} for i, t in enumerate(SHORTCUT_TARGETS)],
    }


def make_server(redirect_manifest=False):
    hits = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            hits.append(self.path)
            origin = f"http://127.0.0.1:{self.server.server_port}"
            if redirect_manifest and self.path == "/.well-known/ai-friction-manifest.json":
                self.send_response(302)
                self.send_header("Location", "/maint/manifest.json")    # same origin, still refused
                self.end_headers()
                return
            if self.path in REDIRECTS:
                self.send_response(302)
                self.send_header("Location", REDIRECTS[self.path])
                self.end_headers()
                return
            body = json.dumps(manifest(origin))
            routes = {
                "/.well-known/ai-friction-manifest.json": (200, "application/json", body),
                "/maint/manifest.json": (200, "application/json", body),
                "/.well-known/ai-manifest.json": (200, "application/json", '{"version":"1.0"}'),
                "/maint/screen": (200, "text/html", PAGE),
                "/maint/rows": (200, "text/html", ROWS_PAGE),
                "/maint/alert": (200, "text/html", ALERT_PAGE),
                "/maint/confirm": (200, "text/html", CONFIRM_PAGE),
                "/maint/forbidden": (403, "text/html", "<h1>Forbidden</h1>"),
                "/other/": (200, "text/html", "<p>outside scope</p>"),
            }
            code, ctype, text = routes.get(self.path, (404, "text/plain", "nf"))
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(text.encode())

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, hits


@pytest.fixture(scope="module")
def server():
    srv, hits = make_server()
    yield f"http://127.0.0.1:{srv.server_port}", hits
    srv.shutdown()


@pytest.fixture()
def browser_page():
    with pw.sync_playwright() as p:
        try:
            # Local test server: skip proxy auto-detection, which can stall the
            # first request of a fresh Chromium profile on Windows.
            b = p.chromium.launch(args=["--no-proxy-server"])
        except Exception as e:            # browser binaries not installed
            pytest.skip(f"chromium unavailable: {e}")
        page = b.new_page()
        yield page
        b.close()


def wait_for_dialog(s, page, timeout_ms=5000):
    """The test pages open their dialog on a timer; wait until it has opened."""
    for _ in range(timeout_ms // 100):
        if s.page._dialog is not None:
            return
        page.wait_for_timeout(100)
    pytest.fail("dialog did not open")


def open_session(page, url, ask, **kw):
    page.goto(url)
    s = ManifestSession(PlaywrightPage(page), ask=ask, **kw)
    assert s.discover(), s.rejected_reason
    return s


def test_enter_and_click_ask_then_403_stops(server, browser_page):
    base, hits = server
    s = open_session(browser_page, base + "/maint/screen", ApproveAsk())
    assert "/.well-known/ai-manifest.json" not in hits                  # old path ignored
    assert s.active_trap_numbers() == [1, 3]
    assert len(s.page.resolve({"role": "gridcell", "column": "Account Category Ref"})) == 2

    res = s.recover(1)
    assert browser_page.url.endswith("/maint/forbidden")
    outcomes = [(r.action, r.outcome, r.principal, r.executed, r.stop) for r in s.audit.records]
    assert outcomes[0] == ("key:Enter", ASK, "approved", True, False)    # Enter on a gridcell = ask
    assert outcomes[1] == ("wait", ALLOW, None, True, False)             # wait <= 5000 ms
    assert outcomes[2] == ("click", ASK, "approved", True, False)        # click = ask
    assert outcomes[3][1:] == (DENY, None, False, True)                  # 403 after the click
    assert s.audit.records[3].reason == "security-control:http-403"
    assert res.status == "stopped" and s.task_ended
    assert s.recover(3).status == "abandoned"                            # no further manifest actions


def test_declined_click_is_not_performed(server, browser_page):
    base, _ = server
    keys_only = lambda req, d: req.action == "key"                        # approves Enter, declines click
    s = open_session(browser_page, base + "/maint/screen", keys_only)
    res = s.recover(1)
    assert browser_page.evaluate("window.enterTrusted") is True          # trusted input pipeline
    assert res.status == "abandoned" and res.reason == "principal declined"
    assert browser_page.url.endswith("/maint/screen")                    # Save was not clicked
    assert s.audit.records[-1].action == "click" and s.audit.records[-1].principal == "declined"


def test_automated_run_declines_enter(server, browser_page):
    base, _ = server
    s = open_session(browser_page, base + "/maint/screen", DenyAsk())
    assert ModelInterface(s).run_recovery(1) == {"trap": 1, "completed": False, "stopped": False,
                                                 "steps": [{"action": "key", "executed": False}]}
    assert browser_page.evaluate("window.enterTrusted") is None


def test_alert_dismissed_and_recorded(server, browser_page):
    base, _ = server
    s = open_session(browser_page, base + "/maint/alert", DenyAsk())
    wait_for_dialog(s, browser_page)
    assert s.active_trap_numbers() == [2]
    assert s.recover(2).status == "completed"
    assert s.audit.records[-1].alert_text == "Session will expire"


def test_confirm_dialog_stops(server, browser_page):
    base, _ = server
    s = open_session(browser_page, base + "/maint/confirm", ApproveAsk())
    wait_for_dialog(s, browser_page)
    res = s.recover(3)
    assert res.status == "stopped" and "native-confirm" in res.reason
    s.page._dialog.dismiss()          # test cleanup: the principal closes the dialog


class Pick:
    def __init__(self, i):
        self.i = i

    def __call__(self, options, context):
        return self.i


@pytest.mark.parametrize("idx, reached", [(0, None), (1, None), (2, None), (3, "/maint/rows")])
def test_every_redirect_of_a_shortcut_is_checked(server, browser_page, idx, reached):
    """hop-query: same-origin redirect adding a query; hop-out: redirect out of
    scope; hop-two: an allowed hop followed by an out-of-scope one; hop-ok."""
    base, hits = server
    s = open_session(browser_page, base + "/maint/screen", ApproveAsk(), choose=Pick(idx))
    before = len(hits)
    ok = s.offer_shortcuts()
    new_hits = hits[before:]
    if reached is None:
        assert not ok
        assert "/other/" not in new_hits and "/maint/screen?x=1" not in new_hits
        assert s.page.blocked_navigations
    else:
        assert ok and browser_page.url == base + reached


def test_when_uses_the_edited_row(server, browser_page):
    base, _ = server
    s = open_session(browser_page, base + "/maint/rows", DenyAsk())
    model = ModelInterface(s)
    browser_page.focus("#a1")                                             # ROH row
    assert model.propose_value("Z051") == {"applicable": True, "match": True, "principalChose": False}
    assert model.propose_value("0001")["match"] is False
    browser_page.focus("#a2")                                             # HALB row: 'when' unsatisfied
    assert model.propose_value("Z051")["applicable"] is False


def test_discovery_does_not_follow_a_redirect():
    srv, hits = make_server(redirect_manifest=True)
    try:
        base = f"http://127.0.0.1:{srv.server_port}"
        with pytest.raises(ManifestRejected, match="redirect"):
            fetch_manifest_bytes(base + "/maint/screen")
        assert hits == ["/.well-known/ai-friction-manifest.json"]          # target never requested
    finally:
        srv.shutdown()
