# -*- coding: utf-8 -*-
"""Playwright page adapter for ManifestSession.

* Locators are resolved against the live document at the time of use, only in
  frames of the manifest's origin whose path is in scope (Section 4.2). Open
  shadow roots are pierced by Playwright's role engine; cross-origin frames are
  never searched.
* Actions go through Playwright's input pipeline (CDP Input events, trusted),
  never through page script (Section 5.1).
* Security-control detection (Section 5.4) is best effort: HTTP 401/403/429 on
  documents and fetch/XHR, pending confirm/prompt/beforeunload dialogs, CAPTCHA
  frames/widgets, password and one-time-code fields, site-built confirmation
  dialogs, consent banners, and in-page denial text. PEP ask defaults are the
  backstop for what this misses.

Approximations (documented, conservative): a locator with ``name`` but no
``role`` matches by label or exact text; ``column`` compares the header cell's
aria-label or text at the same index (colspan ignored).
"""
from urllib.parse import urlsplit

from playwright.sync_api import Error as PlaywrightError

from .pep import Ancestor, ElementInfo
from .validator import in_scope, origin_of

DENIAL_STATUSES = (401, 403, 429)

_INFO_JS = r"""
el => {
  const first = s => (s || '').trim().split(/\s+/)[0] || null;
  const tag = el.tagName.toLowerCase();
  let role = first(el.getAttribute('role'));
  const type = tag === 'input' ? (el.getAttribute('type') || 'text').toLowerCase() : null;
  if (!role) {
    if (tag === 'a' || tag === 'area') role = el.hasAttribute('href') ? 'link' : null;
    else if (tag === 'input') role = ({checkbox:'checkbox', radio:'radio', button:'button', submit:'button',
        reset:'button', image:'button', range:'slider', number:'spinbutton', search:'searchbox'})[type]
        || (['text','email','tel','url','password'].includes(type) ? 'textbox' : null);
    else role = ({button:'button', textarea:'textbox', option:'option', td:null, th:null,
        select: (el.multiple || el.size > 1) ? 'listbox' : 'combobox'})[tag] || null;
  }
  const ancestors = [];
  for (let p = el.parentElement; p; p = p.parentElement)
    ancestors.push({tag: p.tagName.toLowerCase(), role: first(p.getAttribute('role')),
                    editing_host: p.isContentEditable && !(p.parentElement && p.parentElement.isContentEditable)});
  const form = ('form' in el) ? el.form : null;
  const rendered = el.checkVisibility ? el.checkVisibility() : el.getClientRects().length > 0;
  return {tag, role, input_type: type, has_href: el.hasAttribute('href'),
          form_id: form ? (form.id || form.getAttribute('name') || 'form#' + [...document.forms].indexOf(form)) : null,
          form_has_credentials: form ? !!form.querySelector('input[type=password]') : false,
          editing_host: el.isContentEditable && !(el.parentElement && el.parentElement.isContentEditable),
          ancestors, rendered,
          name: (el.getAttribute('aria-label') || el.innerText || el.value || '').replace(/\s+/g, ' ').trim().slice(0, 120)};
}
"""

_COLUMN_JS = r"""
(el, col) => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const CELL = 'td,th,[role=gridcell],[role=cell],[role=columnheader],[role=rowheader]';
  const TABLE = 'table,[role=grid],[role=table],[role=treegrid]';
  const cell = el.closest(CELL); if (!cell) return false;
  const row = cell.closest('tr,[role=row]'); const table = cell.closest(TABLE);
  if (!row || !table) return false;
  const headers = [...table.querySelectorAll('th,[role=columnheader]')].filter(h => h.closest(TABLE) === table);
  let header = null;
  if (cell.hasAttribute('aria-colindex'))
    header = headers.find(h => h.getAttribute('aria-colindex') === cell.getAttribute('aria-colindex')) || null;
  if (!header && headers.length) {
    const i = [...row.children].filter(c => c.matches(CELL)).indexOf(cell);
    const hrow = headers[0].closest('tr,[role=row]');
    if (hrow) header = [...hrow.children].filter(c => c.matches(CELL))[i] || null;
  }
  return !!header && header !== cell && norm(header.getAttribute('aria-label') || header.innerText) === norm(col);
}
"""

_DETECT_JS = r"""
() => {
  const vis = e => e.checkVisibility ? e.checkVisibility() : e.getClientRects().length > 0;
  const any = sel => [...document.querySelectorAll(sel)].some(vis);
  const out = [];
  if (any('input[type=password],input[autocomplete="one-time-code"]')) out.push('authentication');
  if (any('.g-recaptcha,.h-captcha,.cf-turnstile,[id*=captcha i],[class*=captcha i]') ||
      [...document.querySelectorAll('iframe')].some(f => /captcha|turnstile|challenges\.cloudflare/i.test(f.src || '')))
    out.push('captcha');
  if (any('[role=alertdialog]')) out.push('confirmation-dialog');
  const ASKS = /^(yes|no|ok|cancel|confirm|continue|proceed|예|아니요|아니오|확인|취소|계속)$/i;
  for (const d of document.querySelectorAll('[role=dialog],dialog[open],[aria-modal=true]')) {
    if (!vis(d)) continue;
    const labels = [...d.querySelectorAll('button,[role=button],input[type=button],input[type=submit]')]
      .filter(vis).map(b => (b.getAttribute('aria-label') || b.innerText || b.value || '').replace(/[^\p{L}\p{N} ]/gu, '').trim());
    if (labels.filter(t => ASKS.test(t)).length >= 1 && labels.length >= 2) { out.push('confirmation-dialog'); break; }
  }
  if (any('[id*=cookie i],[class*=cookie i],[id*=consent i],[class*=consent i]')) out.push('consent');
  const text = (document.body && document.body.innerText || '').slice(0, 4000);
  if (/\b(401 unauthorized|403 forbidden|429 too many requests|access denied|rate limit exceeded)\b/i.test(text))
    out.push('in-page-denial');
  return out;
}
"""

_FIELD_VALUE_JS = r"""
el => {
  if (el.tagName === 'SELECT') { const o = el.selectedOptions[0]; return o ? o.text : ''; }
  if ('value' in el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) return el.value;
  return el.getAttribute('aria-valuetext') || el.getAttribute('aria-valuenow') || el.innerText || '';
}
"""


class PlaywrightPage:
    def __init__(self, page):
        self.page = page
        self.origin = None
        self.scope = None
        self.manifest = None
        self._dialog = None
        self._denials = set()
        page.on("dialog", self._on_dialog)
        page.on("response", self._on_response)

    # -- event capture
    def _on_dialog(self, dialog):
        # Not handled here: an alert waits for a dismissAlert step; anything else
        # is a security control handed to the principal (Section 5.4).
        self._dialog = dialog

    def _on_response(self, resp):
        try:
            rtype = resp.request.resource_type
        except PlaywrightError:
            return
        if resp.status in DENIAL_STATUSES and rtype in ("document", "xhr", "fetch"):
            self._denials.add(resp.status)

    def bind(self, manifest: dict):
        self.manifest = manifest
        self.origin = manifest["origin"]
        self.scope = manifest.get("scope")

    # -- adapter interface
    def url(self) -> str:
        return self.page.url

    def _frames(self):
        out = []
        for f in self.page.frames:
            u = f.url
            if u.startswith(("http://", "https://")) and origin_of(u) == self.origin \
                    and in_scope(urlsplit(u).path or "/", self.scope):
                out.append(f)
        return out

    def _build(self, root, frame, loc):
        if "within" in loc:
            root = self._build(root, frame, loc["within"])
        if "role" in loc:
            kw = {"include_hidden": True}
            if "name" in loc:
                kw.update(name=loc["name"], exact=True)
            l = root.get_by_role(loc["role"], **kw)
        elif "testId" in loc:
            l = root.get_by_test_id(loc["testId"])
        elif "css" in loc:
            l = root.locator(loc["css"])
        elif "name" in loc:
            l = root.get_by_label(loc["name"], exact=True).or_(root.get_by_text(loc["name"], exact=True))
        elif "column" in loc:
            l = root.locator("td,th,[role=gridcell],[role=cell]")
        else:                                   # {"focused": true} alone
            l = root.locator(":focus")
        if "testId" in loc and "role" in loc:
            l = l.and_(root.get_by_test_id(loc["testId"]))
        if "css" in loc and ("role" in loc or "testId" in loc):
            l = l.and_(root.locator(loc["css"]))
        if loc.get("focused") and set(loc) - {"focused", "within"}:
            l = l.and_(frame.locator(":focus"))
        return l

    def _matches(self, loc, limit=500):
        if self._dialog is not None:            # the DOM is blocked while a dialog is open
            return []
        out = []
        for frame in self._frames():
            try:
                l = self._build(frame, frame, loc)
                n = min(l.count(), limit)
                for i in range(n):
                    h = l.nth(i)
                    if "column" in loc and not h.evaluate(_COLUMN_JS, loc["column"]):
                        continue
                    out.append(h)
            except PlaywrightError:
                continue
        return out

    def _info(self, h) -> ElementInfo:
        d = h.evaluate(_INFO_JS)
        d["ancestors"] = tuple(Ancestor(**a) for a in d["ancestors"])
        return ElementInfo(**d)

    def resolve(self, loc):
        return [(self._info(h), h) for h in self._matches(loc)]

    def resolve_focused_field(self, loc):
        """Field-hint locators match a class; return the focused member, if any."""
        return [(self._info(h), h) for h in self._matches(dict(loc, focused=True))]

    def when_holds(self, when, manifest) -> bool:
        for fid, expected in (when or {}).items():
            hint = next((h for h in manifest.get("fieldHints", []) if h["fieldId"] == fid), None)
            if hint is None:
                return False
            m = self._matches(hint["locator"])
            if len(m) != 1:
                return False
            if " ".join(m[0].evaluate(_FIELD_VALUE_JS).split()) != expected:
                return False
        return True

    def detect_security_controls(self) -> set:
        out = {f"http-{s}" for s in self._denials}
        if self._dialog is not None:
            if self._dialog.type != "alert":
                out.add(f"native-{self._dialog.type}")
            return out
        for f in self.page.frames:
            u = f.url
            if u.startswith("http") and origin_of(u) != (self.origin or origin_of(self.page.url)):
                if any(k in u.lower() for k in ("captcha", "turnstile", "challenges.cloudflare")):
                    out.add("captcha")
                continue
            try:
                out.update(f.evaluate(_DETECT_JS))
            except PlaywrightError:
                continue
        return out

    def condition_holds(self, cond) -> bool:
        if not cond:
            return True
        if "dialog" in cond:
            return self._dialog is not None and self._dialog.type == "alert"
        if "visible" in cond:
            return any(h.evaluate("e => e.checkVisibility ? e.checkVisibility() : e.getClientRects().length > 0")
                       for h in self._matches(cond["visible"]))
        if "absent" in cond:
            return not any(h.evaluate("e => e.checkVisibility ? e.checkVisibility() : e.getClientRects().length > 0")
                           for h in self._matches(cond["absent"]))
        return False

    def wait_until_clear(self, cond, timeout_ms) -> bool:
        """'wait': up to timeoutMs for the trap's condition to stop holding."""
        import time
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            if not self.condition_holds(cond):
                return True
            self.page.wait_for_timeout(100)
        return not self.condition_holds(cond)

    def perform(self, action, handle, key=None) -> bool:
        try:
            if action == "click":
                handle.click(timeout=5000)
                self.page.wait_for_load_state("load", timeout=5000)   # let a triggered navigation land
            elif action == "focus":
                handle.focus(timeout=5000)
            elif action == "key":
                handle.press(key, timeout=5000)
            elif action == "scroll":
                box = handle.bounding_box()
                vh = (self.page.viewport_size or {}).get("height", 720)
                if not box:
                    return False
                self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                self.page.mouse.wheel(0, min(vh, box["height"]))
            else:
                return False
            return True
        except PlaywrightError:
            return False

    def type_into(self, handle, value) -> bool:
        try:
            handle.press_sequentially(value, timeout=5000)   # trusted key events
            return True
        except PlaywrightError:
            return False

    def dismiss_alert(self):
        d = self._dialog
        if d is None or d.type != "alert":
            return None
        text = d.message
        d.dismiss()
        self._dialog = None
        return text

    def navigate_same_origin(self, url, origin) -> bool:
        """GET a same-origin URL; stop on a redirect to another origin (Section 4.4)."""
        blocked = []

        def guard(route, request):
            if not (request.is_navigation_request() and request.frame == self.page.main_frame):
                return route.continue_()
            if origin_of(request.url) != origin:
                blocked.append(request.url)
                return route.abort()
            resp = route.fetch(max_redirects=0)
            loc = resp.headers.get("location")
            if 300 <= resp.status < 400 and loc:
                from urllib.parse import urljoin
                if origin_of(urljoin(request.url, loc)) != origin:
                    blocked.append(loc)
                    return route.abort()
            return route.fulfill(response=resp)

        self.page.route("**/*", guard)
        try:
            self.page.goto(url, wait_until="load")
        except PlaywrightError:
            pass
        finally:
            self.page.unroute("**/*", guard)
        return not blocked and origin_of(self.page.url) == origin
