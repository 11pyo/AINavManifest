# -*- coding: utf-8 -*-
"""Manifest retrieval (draft-han-ai-manifest-03 Sections 3.1, 3.2, 3.5).

* Only /.well-known/ai-friction-manifest.json on the page's own origin.
  The old /.well-known/ai-manifest.json is ignored entirely (Section 3.1).
* No credentials (fresh session, no cookies/auth), and no redirect of any kind.
* HTTPS required; plain HTTP is accepted only for loopback demo origins.
* Size limit enforced while streaming; failure means "no manifest".
* A link rel="ai-friction-manifest" is only a hint and is honoured only if it
  resolves to the same well-known URI (Section 3.2), so it never changes
  what is fetched.
"""
from urllib.parse import urljoin

import requests

from .validator import MAX_OCTETS, ManifestRejected, is_loopback, origin_of

WELL_KNOWN_PATH = "/.well-known/ai-friction-manifest.json"
LINK_REL = "ai-friction-manifest"


def well_known_url(page_url: str) -> str:
    return origin_of(page_url) + WELL_KNOWN_PATH


def link_hint_is_valid(document_url: str, href: str) -> bool:
    """Section 3.2: ignore a link target other than the same-origin well-known URI."""
    return urljoin(document_url, href) == well_known_url(document_url)


def fetch_manifest_bytes(page_url: str, timeout: float = 10.0):
    """Return (raw_bytes, url_retrieved_from). Raises ManifestRejected on any failure."""
    url = well_known_url(page_url)
    if not url.startswith("https://") and not is_loopback(url):
        raise ManifestRejected("manifest must be retrieved over HTTPS (Section 3.1)")
    with requests.Session() as s:              # fresh session = no credentials
        s.trust_env = False                    # no .netrc / proxy auth
        try:
            r = s.get(url, timeout=timeout, allow_redirects=False, stream=True,
                      headers={"Accept": "application/json"})
        except requests.RequestException as e:
            raise ManifestRejected(f"retrieval failed: {e.__class__.__name__}")
        if 300 <= r.status_code < 400:
            r.close()
            # Section 3.1: no redirect is followed, same-origin or not, so an open
            # redirect cannot make another resource be read as the manifest.
            raise ManifestRejected(f"redirect (HTTP {r.status_code}) = no manifest (Section 3.1)")
        with r:
            if r.status_code != 200:
                raise ManifestRejected(f"HTTP {r.status_code}")
            ctype = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if ctype != "application/json":
                raise ManifestRejected(f"media type {ctype!r} is not application/json")
            buf = bytearray()
            for chunk in r.iter_content(8192):
                buf += chunk
                if len(buf) > MAX_OCTETS:
                    raise ManifestRejected(f"larger than {MAX_OCTETS} octets")
    # Origin/path checks are made against the well-known URI that was requested.
    return bytes(buf), well_known_url(page_url)
