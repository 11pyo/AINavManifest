# -*- coding: utf-8 -*-
"""Validator for AI Friction-Recovery Manifests, version "2.0"
(draft-han-ai-manifest-03 Sections 3.5 and 4).

Two modes over one rule set:

* publisher lint (``validate``): every problem is reported; a demo
  manifest must produce zero errors.
* agent load (``load_for_agent``): manifest-level problems reject the
  whole manifest (baseline behaviour, Section 3.5); a descriptor-level
  problem drops only that descriptor (fail closed, Section 4.1).

Usage:
    python -m afrm.validator FILE_OR_URL [--origin ORIGIN] [--at RFC3339]
"""
import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "ai-friction-manifest.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

MAX_OCTETS = 262144                     # Section 3.5
MAX_SAFE_INT = 2 ** 53 - 1              # I-JSON (RFC 7493 Section 2.2)
REMOVED_MEMBERS = ("publisher", "manifestId", "registry_url")   # Section 4.1
DESCRIPTOR_KINDS = (("knownTraps", "trap", "trapId"),
                    ("fieldHints", "fieldHint", "fieldId"),
                    ("shortcuts", "shortcut", "shortcutId"))

# Lint only: names that suggest a security control (Section 5.4). Agents detect
# these on the live page; a publisher should never point a descriptor at one.
_SECURITY_NAME_RE = re.compile(
    r"captcha|password|passcode|sign ?in|log ?in|otp|one-time|verify you|consent|cookie|"
    r"confirm|are you sure|delete|remove|pay|purchase|checkout|transfer|subscribe|"
    r"확인|취소|삭제|로그인|비밀번호|동의|결제", re.I)

_TOP_VALIDATOR = Draft202012Validator(
    {**SCHEMA, "properties": {**SCHEMA["properties"],
                              "knownTraps": {"type": "array"},
                              "fieldHints": {"type": "array"},
                              "shortcuts": {"type": "array"}}})
_DESC_VALIDATORS = {name: Draft202012Validator({"$ref": f"#/$defs/{name}", "$defs": SCHEMA["$defs"]})
                    for _, name, _ in DESCRIPTOR_KINDS}


class ManifestRejected(Exception):
    """The whole manifest must be ignored (agent falls back to baseline)."""


@dataclass
class Report:
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    invalid_descriptors: list = field(default_factory=list)   # [(member, index, id)]

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}")


# ---------------------------------------------------------------- I-JSON

def _reject_duplicates(pairs):
    obj = {}
    for k, v in pairs:
        if k in obj:
            raise ManifestRejected(f"duplicate member name {k!r} (I-JSON)")
        obj[k] = v
    return obj


def _check_i_json_values(value, path="$"):
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise ManifestRejected(f"{path}: lone surrogate (I-JSON)")
    elif isinstance(value, bool) or value is None:
        pass
    elif isinstance(value, int):
        if abs(value) > MAX_SAFE_INT:
            raise ManifestRejected(f"{path}: integer outside IEEE 754 exact range (I-JSON)")
    elif isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ManifestRejected(f"{path}: non-finite number")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _check_i_json_values(v, f"{path}[{i}]")
    elif isinstance(value, dict):
        for k, v in value.items():
            _check_i_json_values(k, f"{path}.<key>")
            _check_i_json_values(v, f"{path}.{k}")


def parse_i_json(raw: bytes):
    """Parse manifest octets, enforcing the size limit and I-JSON (Section 3.5)."""
    if len(raw) > MAX_OCTETS:
        raise ManifestRejected(f"manifest is {len(raw)} octets, limit {MAX_OCTETS}")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ManifestRejected("byte order mark is not allowed")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ManifestRejected("not UTF-8 (I-JSON)")
    try:
        obj = json.loads(text, object_pairs_hook=_reject_duplicates,
                         parse_constant=lambda c: (_ for _ in ()).throw(ManifestRejected(c)))
    except json.JSONDecodeError as e:
        raise ManifestRejected(f"not JSON: {e}")
    _check_i_json_values(obj)
    if not isinstance(obj, dict):
        raise ManifestRejected("top level is not an object")
    return obj


# ---------------------------------------------------------------- helpers

def origin_of(url: str) -> str:
    """ASCII serialization of a URL's origin (RFC 6454), default ports elided."""
    p = urlsplit(url)
    scheme = p.scheme.lower()
    host = (p.hostname or "").lower()
    if ":" in host:
        host = f"[{host}]"
    port = p.port
    if port is None or (scheme, port) in (("http", 80), ("https", 443)):
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


def is_loopback(url: str) -> bool:
    return (urlsplit(url).hostname or "") in ("localhost", "127.0.0.1", "::1")


def parse_rfc3339(s: str) -> datetime:
    if not isinstance(s, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})", s):
        raise ValueError("not an RFC 3339 date-time with offset")
    return datetime.fromisoformat(s.replace("z", "Z").replace("Z", "+00:00"))


def in_scope(path: str, scope) -> bool:
    return scope is None or any(path.startswith(prefix) for prefix in scope)


def resolve_target(origin: str, target: str, scope):
    """Resolve a navigate/shortcut target (Section 4.4). Returns URL or None if invalid."""
    url = urljoin(origin + "/", target)
    if origin_of(url) != origin:
        return None
    path = urlsplit(url).path or "/"
    if not in_scope(path, scope):
        return None
    return url


def _locators_of(desc):
    """Yield every locator inside a descriptor (for lint)."""
    def walk(loc):
        while isinstance(loc, dict):
            yield loc
            loc = loc.get("within")
    for key in ("locator",):
        yield from walk(desc.get(key))
    cond = desc.get("condition") or {}
    for key in ("visible", "absent"):
        yield from walk(cond.get(key))
    for step in desc.get("recovery") or []:
        yield from walk(step.get("locator") if isinstance(step, dict) else None)
    commit = desc.get("commit")
    if isinstance(commit, dict):
        yield from walk(commit.get("locator"))


# ---------------------------------------------------------------- main check

def validate(manifest, *, retrieved_from: str = None, now: datetime = None) -> Report:
    """Full publisher-side check. ``retrieved_from`` is the URL the manifest was
    (or will be) served from; ``now`` defaults to the current time."""
    rep = Report()
    now = now or datetime.now(timezone.utc)
    if not isinstance(manifest, dict):
        rep.error("$", "top level is not an object")
        return rep

    for err in _TOP_VALIDATOR.iter_errors(manifest):
        rep.error("$" + "".join(f"[{p!r}]" for p in err.absolute_path), err.message)
    if manifest.get("version") != "2.0":
        return rep

    origin = manifest.get("origin")
    if isinstance(origin, str):
        if retrieved_from is not None:
            served = origin_of(retrieved_from)
            if served != origin:
                rep.error("$.origin", f"{origin!r} does not equal the serving origin {served!r}")
            if urlsplit(retrieved_from).path != "/.well-known/ai-friction-manifest.json":
                rep.error("$", "not served at /.well-known/ai-friction-manifest.json (Section 3.1)")
        if urlsplit(origin).scheme != "https":
            if is_loopback(origin):
                rep.warn("$.origin", "HTTP accepted for a loopback demo only; Section 3.1 requires HTTPS")
            else:
                rep.error("$.origin", "manifests MUST be served over HTTPS (Section 3.1)")

    exp = manifest.get("expires")
    try:
        exp_dt = parse_rfc3339(exp)
        if exp_dt <= now:
            rep.error("$.expires", f"expired at {exp} (Section 4.1)")
        elif exp_dt > now + timedelta(days=30, hours=1):
            rep.warn("$.expires", "more than 30 days ahead; publishers SHOULD keep it within 30 days")
    except (ValueError, TypeError) as e:
        rep.error("$.expires", str(e))

    for m in REMOVED_MEMBERS:
        if m in manifest:
            rep.warn(f"$.{m}", "member removed in version 2.0 (Section 4.1); it is ignored")

    scope = manifest.get("scope")
    if not (isinstance(scope, list) and all(isinstance(s, str) for s in scope)):
        scope = None
    field_ids = {h.get("fieldId") for h in manifest.get("fieldHints") or [] if isinstance(h, dict)}

    for member, defname, idkey in DESCRIPTOR_KINDS:
        items = manifest.get(member)
        if not isinstance(items, list):
            continue
        ids = [d.get(idkey) for d in items if isinstance(d, dict) and isinstance(d.get(idkey), str)]
        dupes = {x for x in ids if ids.count(x) > 1}
        for i, desc in enumerate(items):
            where = f"$.{member}[{i}]"
            problems = [e.message for e in _DESC_VALIDATORS[defname].iter_errors(desc)]
            if isinstance(desc, dict):
                did = desc.get(idkey)
                if did in dupes:
                    # Which copy the publisher meant is unknown: ignore all of them.
                    problems.append(f"{idkey} {did!r} is not unique")
                if isinstance(origin, str) and not problems:
                    targets = []
                    if defname == "shortcut":
                        targets.append(desc.get("target"))
                    for step in desc.get("recovery") or []:
                        if step.get("action") == "navigate":
                            targets.append(step.get("target"))
                    for t in targets:
                        if resolve_target(origin, t, scope) is None:
                            problems.append(f"target {t!r} is cross-origin or outside scope")
                if defname == "fieldHint" and isinstance(desc.get("when"), dict):
                    for ref in desc["when"]:
                        if ref == desc.get("fieldId") or ref not in field_ids:
                            problems.append(f"'when' names {ref!r}, which is not another field hint")
                for loc in _locators_of(desc):
                    if set(loc) <= {"css", "within"} and "css" in loc:
                        rep.warn(where, "css-only locator; publishers SHOULD prefer role/name/column")
                    if isinstance(loc.get("name"), str) and _SECURITY_NAME_RE.search(loc["name"]):
                        rep.warn(where, f"locator name {loc['name']!r} looks like a security control "
                                        "or sensitive action (Sections 5.3, 5.4)")
            else:
                did = None
            for p in problems:
                rep.error(where, p)
            if problems:
                rep.invalid_descriptors.append((member, i, did))
    return rep


def load_for_agent(raw: bytes, retrieved_from: str, now: datetime = None):
    """Agent-side load: returns (usable_manifest, report) where invalid
    descriptors are removed, or raises ManifestRejected (Section 3.5)."""
    manifest = parse_i_json(raw)
    if manifest.get("version") != "2.0":
        raise ManifestRejected(f"version {manifest.get('version')!r} is not \"2.0\"")
    rep = validate(manifest, retrieved_from=retrieved_from, now=now)
    fatal = [e for e in rep.errors if not e.startswith(("$.knownTraps[", "$.fieldHints[", "$.shortcuts["))]
    if fatal:
        raise ManifestRejected("; ".join(fatal))
    drop = {(m, i) for m, i, _ in rep.invalid_descriptors}
    usable = dict(manifest)
    for member, _, _ in DESCRIPTOR_KINDS:
        if isinstance(manifest.get(member), list):
            usable[member] = [d for i, d in enumerate(manifest[member]) if (member, i) not in drop]
    return usable, rep


# ---------------------------------------------------------------- CLI

def _read_source(src: str):
    if src.startswith(("http://", "https://")):
        from .discovery import fetch_manifest_bytes
        raw, url = fetch_manifest_bytes(src)
        return raw, url
    return Path(src).read_bytes(), None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Validate an AI Friction-Recovery Manifest (version 2.0).")
    ap.add_argument("source", nargs="+", help="manifest file, or a page/origin URL to discover from")
    ap.add_argument("--origin", help="origin the file is served from (files only)")
    ap.add_argument("--at", help="evaluate expiry at this RFC 3339 time instead of now")
    args = ap.parse_args(argv)
    now = parse_rfc3339(args.at) if args.at else None
    failed = 0
    for src in args.source:
        try:
            raw, url = _read_source(src)
            if url is None and args.origin:
                url = args.origin.rstrip("/") + "/.well-known/ai-friction-manifest.json"
            manifest = parse_i_json(raw)
            rep = validate(manifest, retrieved_from=url, now=now)
        except ManifestRejected as e:
            print(f"FAIL {src}\n  error: {e}")
            failed += 1
            continue
        except OSError as e:
            print(f"FAIL {src}\n  error: {e}")
            failed += 1
            continue
        print(f"{'PASS' if rep.ok else 'FAIL'} {src}" + (f"  (served at {url})" if url else ""))
        for e in rep.errors:
            print(f"  error: {e}")
        for w in rep.warnings:
            print(f"  warning: {w}")
        failed += 0 if rep.ok else 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
