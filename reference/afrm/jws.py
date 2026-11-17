# -*- coding: utf-8 -*-
"""Publisher signature verification (draft-han-ai-manifest-03 Section 6.1).  Standard library only.

Each element of ``signatures`` is a JWS [RFC7515] in compact serialization with a detached payload
(Appendix F), over the RFC 8785 canonical form of the manifest with ``signatures`` removed
(``jcs.signing_payload``).  The protected header MUST contain "alg" and "kid".  Supported: "ES256"
(MUST, RFC 7518) and "Ed25519" (MAY, RFC 9864).  Rejected: "none", every symmetric algorithm, and every
algorithm RFC 9864 deprecates ("EdDSA" among them), i.e. anything outside those two.

Trust model (Section 6.1, P1):
  * Keys come ONLY from the agent's own configuration (``DesignatedKey``, grouped per origin).  Nothing in
    the manifest or in a JWS header (jwk, jku, x5u, x5c, kid contents) is ever used to obtain a key.
  * A valid signature establishes who published the manifest bytes.  It grants nothing: this module is not
    imported by the PEP, and its result changes no policy.

Only verification of public data is done here, so the arithmetic is not constant-time.  Signing helpers
for publishers and tests live in ``jws_sign``.
"""
import base64
import hashlib
import re
from dataclasses import dataclass, field

from .jcs import signing_payload
from .validator import ManifestRejected, parse_i_json

ALGORITHMS = ("ES256", "Ed25519")
# Implementation limit, not in the draft: pure-Python verification costs milliseconds, and a 262144-octet
# manifest can carry thousands of signatures.  Only signatures whose kid and alg match a designated key reach
# the arithmetic, and at most this many such checks are made per manifest.
MAX_VERIFY_ATTEMPTS = 8


class JwsError(Exception):
    """A signature (or a configured key) cannot be used.  The message is for logs and the principal only."""


# ---------------------------------------------------------------- base64url (RFC 7515 Section 2, Appendix C)

_B64 = re.compile(r"[A-Za-z0-9_-]*\Z")


def b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64u_decode(s: str) -> bytes:
    """Strict: URL-safe alphabet, no padding, no whitespace, canonical final character (no malleability)."""
    if not isinstance(s, str) or not _B64.match(s) or len(s) % 4 == 1:
        raise JwsError("not base64url without padding")
    raw = base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
    if b64u_encode(raw) != s:
        raise JwsError("non-canonical base64url")
    return raw


# ---------------------------------------------------------------- ECDSA P-256 (FIPS 186-4, RFC 7518 Section 3.4)

_P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
_A = _P - 3
_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
_G = (0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
      0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5)


def _on_curve(pt) -> bool:
    x, y = pt
    return 0 <= x < _P and 0 <= y < _P and (y * y - (x * x * x + _A * x + _B)) % _P == 0


def _ec_add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    (x1, y1), (x2, y2) = p1, p2
    if x1 == x2:
        if (y1 + y2) % _P == 0:
            return None
        lam = (3 * x1 * x1 + _A) * pow(2 * y1, -1, _P) % _P
    else:
        lam = (y2 - y1) * pow(x2 - x1, -1, _P) % _P
    x3 = (lam * lam - x1 - x2) % _P
    return (x3, (lam * (x1 - x3) - y1) % _P)


def _ec_mul(k: int, pt):
    acc = None
    while k:
        if k & 1:
            acc = _ec_add(acc, pt)
        pt = _ec_add(pt, pt)
        k >>= 1
    return acc


def es256_verify(signing_input: bytes, sig: bytes, x: int, y: int) -> bool:
    if len(sig) != 64:                                  # RFC 7518 3.4: R || S, 32 octets each, nothing else
        return False
    r, s = int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big")
    if not (1 <= r < _N and 1 <= s < _N):
        return False
    q = (x, y)
    if not _on_curve(q):
        return False
    e = int.from_bytes(hashlib.sha256(signing_input).digest(), "big")
    w = pow(s, -1, _N)
    pt = _ec_add(_ec_mul(e * w % _N, _G), _ec_mul(r * w % _N, q))
    return pt is not None and pt[0] % _N == r


# ---------------------------------------------------------------- Ed25519 (RFC 8032 Section 5.1)

_EP = 2 ** 255 - 19
_ED = -121665 * pow(121666, _EP - 2, _EP) % _EP
_EL = 2 ** 252 + 27742317777372353535851937790883648493
_SQRT_M1 = pow(2, (_EP - 1) // 4, _EP)


def _ed_add(p1, p2):
    a = (p1[1] - p1[0]) * (p2[1] - p2[0]) % _EP
    b = (p1[1] + p1[0]) * (p2[1] + p2[0]) % _EP
    c = 2 * p1[3] * p2[3] * _ED % _EP
    d = 2 * p1[2] * p2[2] % _EP
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _EP, g * h % _EP, f * g % _EP, e * h % _EP)


def _ed_mul(s: int, pt):
    acc = (0, 1, 1, 0)
    while s:
        if s & 1:
            acc = _ed_add(acc, pt)
        pt = _ed_add(pt, pt)
        s >>= 1
    return acc


def _ed_equal(p1, p2) -> bool:
    return (p1[0] * p2[2] - p2[0] * p1[2]) % _EP == 0 and (p1[1] * p2[2] - p2[1] * p1[2]) % _EP == 0


def _recover_x(y: int, sign: int):
    if y >= _EP:
        return None
    x2 = (y * y - 1) * pow(_ED * y * y + 1, _EP - 2, _EP) % _EP
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_EP + 3) // 8, _EP)
    if (x * x - x2) % _EP:
        x = x * _SQRT_M1 % _EP
    if (x * x - x2) % _EP:
        return None
    return x if (x & 1) == sign else _EP - x


def _ed_decode(s: bytes):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign, y = y >> 255, y & ((1 << 255) - 1)
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % _EP)


_GY = 4 * pow(5, _EP - 2, _EP) % _EP
_GX = _recover_x(_GY, 0)
_EG = (_GX, _GY, 1, _GX * _GY % _EP)


def ed25519_verify(message: bytes, sig: bytes, public: bytes) -> bool:
    if len(sig) != 64 or len(public) != 32:
        return False
    a, r = _ed_decode(public), _ed_decode(sig[:32])
    if a is None or r is None:
        return False
    s = int.from_bytes(sig[32:], "little")
    if s >= _EL:                                        # RFC 8032 5.1.7: S must be < L
        return False
    h = int.from_bytes(hashlib.sha512(sig[:32] + public + message).digest(), "little") % _EL
    return _ed_equal(_ed_mul(s, _EG), _ed_add(r, _ed_mul(h, a)))


# ---------------------------------------------------------------- designated keys (agent configuration only)

@dataclass(frozen=True)
class DesignatedKey:
    """A public key the agent's own configuration (or its principal) designates for an origin.

    ``alg`` binds the key to one algorithm, so a header cannot pick another algorithm for it (no alg
    confusion).  ``jwk`` is a public JWK: EC/P-256 for "ES256", OKP/Ed25519 for "Ed25519".  A malformed
    key is a configuration error and raises JwsError at construction.
    """
    kid: str
    alg: str
    jwk: dict
    _material: tuple = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        if self.alg not in ALGORITHMS:
            raise JwsError(f"alg {self.alg!r} is not supported")
        if not isinstance(self.kid, str) or not self.kid:
            raise JwsError("kid must be a non-empty string")
        j = self.jwk
        if not isinstance(j, dict):
            raise JwsError("jwk must be an object")
        if self.alg == "ES256":
            if j.get("kty") != "EC" or j.get("crv") != "P-256":
                raise JwsError('ES256 needs a JWK with kty "EC" and crv "P-256"')
            xb, yb = b64u_decode(j.get("x")), b64u_decode(j.get("y"))
            if len(xb) != 32 or len(yb) != 32:
                raise JwsError("EC P-256 coordinates must be 32 octets")
            pt = (int.from_bytes(xb, "big"), int.from_bytes(yb, "big"))
            if not _on_curve(pt):
                raise JwsError("EC point is not on P-256")
            object.__setattr__(self, "_material", pt)
        else:
            if j.get("kty") != "OKP" or j.get("crv") != "Ed25519":
                raise JwsError('Ed25519 needs a JWK with kty "OKP" and crv "Ed25519"')
            xb = b64u_decode(j.get("x"))
            if len(xb) != 32 or _ed_decode(xb) is None:
                raise JwsError("Ed25519 public key is not a valid point encoding")
            object.__setattr__(self, "_material", (xb,))


# ---------------------------------------------------------------- verification

@dataclass
class SignatureOutcome:
    verified: bool = False
    kid: str = None                     # kid of the designated key that verified, for the audit record only
    reasons: list = field(default_factory=list)    # why each signature was not accepted (logs/principal only)


def _verify_one(token, payload: bytes, keys, budget):
    """Returns the DesignatedKey whose signature this is, or raises JwsError."""
    if not isinstance(token, str):
        raise JwsError("signature is not a string")
    parts = token.split(".")
    if len(parts) != 3 or parts[1] != "":
        raise JwsError("not a compact JWS with a detached payload")
    header_b64, sig = parts[0], b64u_decode(parts[2])
    try:
        header = parse_i_json(b64u_decode(header_b64))
    except ManifestRejected as e:
        raise JwsError(f"protected header: {e}")
    alg, kid = header.get("alg"), header.get("kid")
    if not isinstance(alg, str) or not isinstance(kid, str):
        raise JwsError('protected header must contain "alg" and "kid"')
    if "crit" in header:                                 # RFC 7515 4.1.11: no extension is understood
        raise JwsError('"crit" names extensions this verifier does not understand')
    if alg not in ALGORITHMS:                            # none, HS*, EdDSA (deprecated, RFC 9864), anything else
        raise JwsError(f"alg {alg!r} is rejected")
    cands = [k for k in keys if k.kid == kid and k.alg == alg]
    if not cands:
        raise JwsError("no designated key for this kid and alg")
    signing_input = (header_b64 + "." + b64u_encode(payload)).encode("ascii")
    for key in cands:
        if budget[0] <= 0:
            raise JwsError(f"stopped after {MAX_VERIFY_ATTEMPTS} signature checks")
        budget[0] -= 1                                   # only checks that reach the arithmetic are counted
        if alg == "ES256":
            ok = es256_verify(signing_input, sig, *key._material)
        else:
            ok = ed25519_verify(signing_input, sig, key._material[0])
        if ok:
            return key
    raise JwsError("signature does not verify")


def verify_manifest(manifest: dict, keys) -> SignatureOutcome:
    """True outcome iff at least one element of ``signatures`` verifies under a designated key.

    ``manifest`` is the parsed manifest exactly as published (descriptors the agent later drops still
    belong to the signed payload).  ``keys`` are the DesignatedKey objects for the manifest's origin.
    """
    out = SignatureOutcome()
    sigs = manifest.get("signatures") if isinstance(manifest, dict) else None
    if not isinstance(sigs, list) or not sigs:
        out.reasons.append("no signatures")
        return out
    keys = list(keys)
    try:
        payload = signing_payload(manifest)
    except (TypeError, ValueError, RecursionError) as e:
        out.reasons.append(f"cannot canonicalize: {type(e).__name__}")
        return out
    budget = [MAX_VERIFY_ATTEMPTS]
    for i, token in enumerate(sigs):
        try:
            key = _verify_one(token, payload, keys, budget)
        except (JwsError, ValueError, TypeError, OverflowError, RecursionError) as e:
            out.reasons.append(f"signatures[{i}]: {e}")
            continue
        out.verified, out.kid = True, key.kid
        return out
    return out
