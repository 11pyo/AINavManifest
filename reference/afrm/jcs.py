# -*- coding: utf-8 -*-
"""JSON Canonicalization Scheme (RFC 8785) and the manifest digest of
draft-han-ai-manifest-03 Section 5.5 / 6.1.

Input is assumed to be I-JSON (validator.parse_i_json enforces that), so
strings carry no lone surrogates and integers fit IEEE 754 doubles.
"""
import hashlib
import json
import math
from decimal import Decimal


def _es_number(x) -> str:
    """ECMAScript Number.prototype.toString, which RFC 8785 Section 3.2.2.3 mandates."""
    if isinstance(x, bool):
        raise TypeError("bool is not a number")
    if isinstance(x, int):
        x = float(x)
    if math.isnan(x) or math.isinf(x):
        raise ValueError("NaN/Infinity are not JSON numbers")
    if x == 0:
        return "0"
    sign = "-" if x < 0 else ""
    # repr() yields the shortest round-tripping decimal, as ECMAScript requires.
    _, digits, exp = Decimal(repr(abs(x))).normalize().as_tuple()
    s = "".join(map(str, digits))
    k = len(s)
    n = exp + k  # value = 0.s * 10^n
    if k <= n <= 21:
        out = s + "0" * (n - k)
    elif 0 < n <= 21:
        out = s[:n] + "." + s[n:]
    elif -6 < n <= 0:
        out = "0." + "0" * (-n) + s
    else:
        e = n - 1
        mant = s if k == 1 else s[0] + "." + s[1:]
        out = f"{mant}e{'+' if e >= 0 else '-'}{abs(e)}"
    return sign + out


def canonicalize(value) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return _es_number(value)
    if isinstance(value, str):
        # json.dumps(ensure_ascii=False) escapes exactly what ECMAScript JSON.stringify does.
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(canonicalize(v) for v in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value, key=lambda k: k.encode("utf-16-be"))
        return "{" + ",".join(canonicalize(k) + ":" + canonicalize(value[k]) for k in keys) + "}"
    raise TypeError(f"not a JSON value: {type(value).__name__}")


def manifest_digest(manifest: dict) -> str:
    """Lower-case hex SHA-256 of the JCS form of the manifest (audit record, Section 5.5)."""
    return hashlib.sha256(canonicalize(manifest).encode("utf-8")).hexdigest()


def signing_payload(manifest: dict) -> bytes:
    """JCS form with the signatures member removed (detached JWS payload, Section 6.1)."""
    return canonicalize({k: v for k, v in manifest.items() if k != "signatures"}).encode("utf-8")
