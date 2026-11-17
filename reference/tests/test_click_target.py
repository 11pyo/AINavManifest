# -*- coding: utf-8 -*-
"""-04 Section 5.1: which element would receive a manifest-derived click, and the rule that decides it.

Run in Chromium on set_content pages (no site needed): the check only reads the live document."""
import pytest

pw = pytest.importorskip("playwright.sync_api")

from afrm.playwright_page import PlaywrightPage


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch(args=["--no-proxy-server"])
        except Exception as e:
            pytest.skip(f"chromium unavailable: {e}")
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    pg = browser.new_page(viewport={"width": 800, "height": 600})
    yield pg
    pg.close()


def check(page, html, selector, *, frame=None, timeout_ms=300):
    page.set_content(html)
    adapter = PlaywrightPage(page)
    root = page.frame_locator(frame) if frame else page
    handle = root.locator(selector).element_handle()
    return adapter, handle, adapter._verified(handle, __import__("afrm.playwright_page", fromlist=["_HIT_JS"])._HIT_JS,
                                              timeout_ms)[:2]


def test_the_resolved_element_receives_the_click(page):
    assert check(page, "<button id=b>Go</button>", "#b")[2] == (True, "")


def test_a_descendant_that_is_not_activatable_is_accepted(page):
    assert check(page, "<button id=b><span><b>Go</b></span></button>", "#b")[2][0]


def test_an_activatable_descendant_is_refused(page):
    r = check(page, "<button id=b style='padding:0'><a href='/x' style='display:block;width:80px;height:30px'>x</a></button>", "#b")
    assert r[2][0] is False and "activatable" in r[2][1]


def test_an_invisible_overlay_is_refused(page):
    html = ("<div style='position:relative;display:inline-block'><button id=b>Continue</button>"
            "<a id=ov style='position:absolute;inset:0;opacity:0'></a></div>")
    ok, why = check(page, html, "#b")[2]
    assert not ok and "another element" in why


def test_a_label_of_the_resolved_control_is_accepted(page):
    html = "<input id=c type=checkbox style='position:absolute;left:10px;top:10px'><label for=c style='position:absolute;left:0;top:0;width:60px;height:60px'>x</label>"
    assert check(page, html, "#c")[2][0]


def test_a_label_of_another_control_is_refused(page):
    html = ("<input id=c type=checkbox style='position:absolute;left:10px;top:10px'><input id=d>"
            "<label for=d style='position:absolute;left:0;top:0;width:60px;height:60px'>x</label>")
    assert not check(page, html, "#c")[2][0]


def test_a_nested_shadow_descendant_is_accepted_and_an_activatable_one_refused(page):
    host = ("<div id=h style='display:block;width:120px;height:40px'></div><script>"
            "(()=>{const r=document.getElementById('h').attachShadow({mode:'open'});r.innerHTML=%s})();</script>")
    assert check(page, host % "\"<span style='display:block;height:40px'>plain</span>\"", "#h")[2][0]
    ok, why = check(page, host % "\"<button style='display:block;width:120px;height:40px'>b</button>\"", "#h")[2]
    assert not ok and "activatable" in why


def test_an_element_in_a_shadow_root_is_accepted_when_it_is_the_one_hit(page):
    html = ("<div id=h></div><script>(()=>{const r=document.getElementById('h').attachShadow({mode:'open'});"
            "r.innerHTML=\"<button id=in>inner</button>\"})();</script>")
    page.set_content(html)
    handle = page.locator("#h >> #in").element_handle()
    from afrm import playwright_page as m
    assert PlaywrightPage(page)._verified(handle, m._HIT_JS, 300)[0]


FRAME = "<iframe id=f srcdoc=\"<button id=b>in frame</button>\" style='width:300px;height:100px;border:3px solid;padding:5px'></iframe>"


def test_a_click_inside_a_frame_needs_the_frame_to_lead_to_it(page):
    from afrm import playwright_page as m
    page.set_content(FRAME)
    page.wait_for_function("document.getElementById('f').contentDocument.getElementById('b')")
    handle = page.frame_locator("#f").locator("#b").element_handle()
    a = PlaywrightPage(page)
    assert a._verified(handle, m._HIT_JS, 300)[0]
    page.evaluate("""() => { const o = document.createElement('div');
        o.style.cssText = 'position:fixed;inset:0;opacity:0'; document.body.appendChild(o); }""")
    ok, why = a._verified(handle, m._HIT_JS, 300)[:2]
    assert not ok and "frame" in why


def test_a_transparent_element_is_declined_for_click_and_key(page):
    page.set_content("<button id=b style='opacity:0'>Go</button>")
    a = PlaywrightPage(page)
    h = page.locator("#b").element_handle()
    assert a._verified(h, __import__("afrm.playwright_page", fromlist=["x"])._HIT_JS, 300)[0] is False
    assert a._verified(h, __import__("afrm.playwright_page", fromlist=["x"])._VISIBLE_JS, 300)[0] is False


def test_the_check_is_repeated_and_passes_when_the_cover_goes_away(page):
    html = ("<button id=b>Go</button><div id=ov style='position:fixed;inset:0;background:#fff'></div>"
            "<script>setTimeout(()=>document.getElementById('ov').remove(), 700)</script>")
    page.set_content(html)
    a = PlaywrightPage(page)
    ok, _ = a.verify_click_target(page.locator("#b").element_handle())
    assert ok


def test_a_permanent_cover_is_declined_after_the_window(page):
    import time
    page.set_content("<button id=b>Go</button><div style='position:fixed;inset:0;background:#fff'></div>")
    a = PlaywrightPage(page)
    t0 = time.monotonic()
    ok, why = a.verify_click_target(page.locator("#b").element_handle())
    assert not ok and 4.5 <= time.monotonic() - t0 < 9           # repeated for up to 5000 ms, then refused


def test_the_click_is_sent_at_the_checked_point(page):
    page.set_content("<button id=b onclick=\"window.n=(window.n||0)+1;window.t=event.isTrusted\" "
                     "style='margin:40px;padding:10px 30px;border:4px solid'>Go</button>")
    a = PlaywrightPage(page)
    h = page.locator("#b").element_handle()
    assert a.verify_click_target(h)[0] and a.perform("click", h)
    assert page.evaluate("[window.n, window.t]") == [1, True]
