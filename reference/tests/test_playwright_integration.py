# -*- coding: utf-8 -*-
"""End-to-end: real HTTP discovery + Chromium + PEP.

Shows the two required behaviours on a live page: a manifest-derived click is
"ask", and an HTTP 403 reached during recovery stops it.
"""
import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

pw = pytest.importorskip("playwright.sync_api")

from afrm.agent import ApproveAsk, DenyAsk, ManifestSession
from afrm.pep import ALLOW, ASK, DENY
from afrm.playwright_page import PlaywrightPage

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

ALERT_PAGE = """<!doctype html><html><body><p>alert page</p>
<script>setTimeout(() => alert('Session will expire'), 300)</script></body></html>"""
CONFIRM_PAGE = """<!doctype html><html><body><div role="gridcell" tabindex="0" id="c">x</div>
<script>document.getElementById('c').focus(); setTimeout(() => confirm('Delete all rows?'), 300)</script></body></html>"""


def manifest(origin):
    return {
        "version": "2.0", "origin": origin,
        "expires": (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope": ["/maint/"],
        "knownTraps": [
            {"trapId": "row-commit", "category": "commit-gesture",
             "locator": {"role": "gridcell", "focused": True},
             "condition": {"visible": {"role": "status", "name": "Row locked"}},
             "recovery": [
                 {"action": "key", "key": "Enter", "locator": {"role": "gridcell", "focused": True}},
                 {"action": "wait", "timeoutMs": 2000},
                 {"action": "click", "locator": {"role": "button", "name": "Save"}}]},
            {"trapId": "expiry-alert", "category": "native-alert", "condition": {"dialog": "alert"},
             "recovery": [{"action": "dismissAlert"}]},
            {"trapId": "focus-cell", "category": "commit-gesture",
             "locator": {"role": "gridcell", "focused": True},
             "recovery": [{"action": "key", "key": "Tab", "locator": {"role": "gridcell", "focused": True}}]},
        ],
        "fieldHints": [{"fieldId": "acctCatRef", "allowedValues": ["Z051", "Z063", "Z072"],
                        "locator": {"role": "gridcell", "column": "Account Category Ref"}}],
    }


@pytest.fixture(scope="module")
def server():
    hits = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            hits.append(self.path)
            origin = f"http://127.0.0.1:{self.server.server_port}"
            routes = {
                "/.well-known/ai-friction-manifest.json": (200, "application/json", json.dumps(manifest(origin))),
                "/.well-known/ai-manifest.json": (200, "application/json", '{"version":"1.0"}'),
                "/maint/screen": (200, "text/html", PAGE),
                "/maint/alert": (200, "text/html", ALERT_PAGE),
                "/maint/confirm": (200, "text/html", CONFIRM_PAGE),
                "/maint/forbidden": (403, "text/html", "<h1>Forbidden</h1>"),
            }
            code, ctype, body = routes.get(self.path, (404, "text/plain", "nf"))
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body.encode())

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}", hits
    srv.shutdown()


@pytest.fixture()
def browser_page():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:            # browser binaries not installed
            pytest.skip(f"chromium unavailable: {e}")
        page = b.new_page()
        yield page
        b.close()


def open_session(page, url, ask):
    page.goto(url)
    s = ManifestSession(PlaywrightPage(page), ask=ask)
    assert s.discover(), s.rejected_reason
    return s


def test_click_asks_then_403_stops(server, browser_page):
    base, hits = server
    s = open_session(browser_page, base + "/maint/screen", ApproveAsk())
    assert "/.well-known/ai-manifest.json" not in hits                  # old path never fetched
    assert [t["trapId"] for t in s.applicable_traps()] == ["row-commit", "focus-cell"]
    assert len(s.page.resolve({"role": "gridcell", "column": "Account Category Ref"})) == 2

    res = s.recover("row-commit")
    outcomes = [(r.action, r.outcome, r.principal, r.executed, r.stop) for r in s.audit.records]
    assert outcomes[0] == ("key:Enter", ALLOW, None, True, False)        # Enter on a gridcell
    assert outcomes[1] == ("wait", ALLOW, None, True, False)
    assert outcomes[2] == ("click", ASK, "approved", True, False)        # click = ask
    assert outcomes[3][1:] == (DENY, None, False, True)                  # 403 after the click
    assert s.audit.records[3].reason == "security-control:http-403"
    assert res.status == "stopped" and s.task_ended
    assert s.recover("focus-cell").status == "abandoned"                 # no further manifest actions


def test_declined_click_is_not_performed(server, browser_page):
    base, hits = server
    s = open_session(browser_page, base + "/maint/screen", DenyAsk())
    res = s.recover("row-commit")
    assert browser_page.evaluate("window.enterTrusted") is True          # trusted input pipeline
    assert res.status == "abandoned" and res.reason == "principal declined"
    assert browser_page.url.endswith("/maint/screen")                    # Save was not clicked
    assert s.audit.records[-1].action == "click" and s.audit.records[-1].principal == "declined"


def test_alert_dismissed_and_recorded(server, browser_page):
    base, _ = server
    s = open_session(browser_page, base + "/maint/alert", DenyAsk())
    browser_page.wait_for_timeout(700)
    assert [t["trapId"] for t in s.applicable_traps()] == ["expiry-alert"]
    assert s.recover("expiry-alert").status == "completed"
    assert s.audit.records[-1].alert_text == "Session will expire"


def test_confirm_dialog_stops(server, browser_page):
    base, _ = server
    s = open_session(browser_page, base + "/maint/confirm", ApproveAsk())
    browser_page.wait_for_timeout(700)
    res = s.recover("focus-cell")
    assert res.status == "stopped" and "native-confirm" in res.reason
