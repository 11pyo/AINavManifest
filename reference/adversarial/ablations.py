# -*- coding: utf-8 -*-
"""Test-only ablations: switch ONE control of the full -03 agent off, inside the test process.

Nothing here changes afrm's behaviour outside ``with apply(name):``; the patches are restored on
exit. These flags exist only for the evaluation and must not be added to the production code path.
"""
import contextlib
import json
from unittest import mock

from afrm import agent as agent_mod
from afrm import pep as pep_mod
from afrm.playwright_page import PlaywrightPage

ABLATIONS = ("string-block", "provenance", "redirect-hop-check", "sensitive-rule", "locator-uniqueness",
             "security-control-stop", "descriptor-validation", "discovery-no-redirect")
# Added with the JWS verifier; kept out of ABLATIONS so that "--ablations all" still means the recorded set.
SIGNATURE_ABLATIONS = ("signature-check",)


def _follow_redirect_fetch(url):
    import requests
    from afrm.discovery import well_known_url
    s = requests.Session()
    s.trust_env = False
    u = well_known_url(url)
    r = s.get(u, timeout=10)
    if r.status_code != 200:
        from afrm.validator import ManifestRejected
        raise ManifestRejected(f"HTTP {r.status_code}")
    return r.content, r.url


@contextlib.contextmanager
def apply(name):
    """Yields keyword options for harness.run_pep."""
    if name is None:
        yield {}
        return
    assert name in ABLATIONS + SIGNATURE_ABLATIONS, name
    patches, opts = [], {}
    if name == "string-block":
        opts["see_strings"] = True                       # the model is shown the manifest's strings
    elif name == "provenance":
        patches.append(mock.patch.object(pep_mod.Provenance, "note", lambda self, *a, **k: None))
    elif name == "redirect-hop-check":
        def plain(self, url, origin, scope=None, max_hops=10):
            try:
                self.page.goto(url, wait_until="load")
            except Exception:
                pass
            self.blocked_navigations = []
            return True
        patches.append(mock.patch.object(PlaywrightPage, "navigate_same_origin", plain))
    elif name == "sensitive-rule":
        orig = pep_mod.PolicyEnforcementPoint._default

        def default(self, req, el, doc_url):
            d = orig(self, req, el, doc_url)
            d.sensitive = False                          # neither provenance nor credentials make it sensitive
            return d
        patches.append(mock.patch.object(pep_mod.PolicyEnforcementPoint, "_default", default))
    elif name == "locator-uniqueness":
        orig = PlaywrightPage.resolve
        patches.append(mock.patch.object(PlaywrightPage, "resolve", lambda self, loc: orig(self, loc)[:1]))
    elif name == "security-control-stop":
        patches.append(mock.patch.object(PlaywrightPage, "detect_security_controls", lambda self: set()))
    elif name == "descriptor-validation":
        patches.append(mock.patch.object(agent_mod, "load_for_agent",
                                         lambda raw, url, now=None: (json.loads(raw), None)))
        patches.append(mock.patch.object(pep_mod.PolicyEnforcementPoint, "_validate", lambda self, req: None))
    elif name == "discovery-no-redirect":
        opts["fetch"] = _follow_redirect_fetch
    elif name == "signature-check":
        opts["no_designation"] = True                    # the agent has no designated key: signatures are ignored
    for p in patches:
        p.start()
    try:
        yield opts
    finally:
        for p in reversed(patches):
            p.stop()
