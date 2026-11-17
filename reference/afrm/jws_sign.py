# -*- coding: utf-8 -*-
"""Publisher-side signing helper for draft-han-ai-manifest-03 Section 6.1, and the test kit of the suite.

Produces the compact, detached-payload JWS that ``jws.verify_manifest`` accepts.  Standard library only,
no side-channel hardening: use it for tests, demos and offline signing, not on a shared machine with
production keys.  An agent never imports this module.
"""
import hashlib
import hmac
import json

from . import jws
from .jcs import signing_payload


def _int_to_32(n: int) -> bytes:
    return n.to_bytes(32, "big")


# ---------------------------------------------------------------- key generation

def generate_es256(seed: bytes):
    """Deterministic test key from ``seed``. Returns (private_scalar, public_jwk)."""
    d = int.from_bytes(hashlib.sha256(b"es256-test-key:" + seed).digest(), "big") % (jws._N - 1) + 1
    x, y = jws._ec_mul(d, jws._G)
    return d, {"kty": "EC", "crv": "P-256", "x": jws.b64u_encode(_int_to_32(x)), "y": jws.b64u_encode(_int_to_32(y))}


def _ed_encode(pt) -> bytes:
    x, y, z, _ = pt
    zi = pow(z, jws._EP - 2, jws._EP)
    x, y = x * zi % jws._EP, y * zi % jws._EP
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _ed_secret(seed: bytes):
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def generate_ed25519(seed: bytes):
    """Returns (32-octet private seed, public_jwk). ``seed`` is hashed to 32 octets."""
    sk = hashlib.sha256(b"ed25519-test-key:" + seed).digest()
    return sk, ed25519_public_jwk(sk)


def ed25519_public_jwk(sk: bytes) -> dict:
    a, _ = _ed_secret(sk)
    return {"kty": "OKP", "crv": "Ed25519", "x": jws.b64u_encode(_ed_encode(jws._ed_mul(a, jws._EG)))}


# ---------------------------------------------------------------- signing

def es256_sign(signing_input: bytes, d: int) -> bytes:
    e = int.from_bytes(hashlib.sha256(signing_input).digest(), "big")
    ctr = 0
    while True:
        k = int.from_bytes(hmac.new(_int_to_32(d), _int_to_32(e) + bytes([ctr]), hashlib.sha256).digest(), "big") % jws._N
        ctr += 1
        if k == 0:
            continue
        r = jws._ec_mul(k, jws._G)[0] % jws._N
        s = pow(k, -1, jws._N) * (e + r * d) % jws._N
        if r and s:
            return _int_to_32(r) + _int_to_32(s)


def ed25519_sign(message: bytes, sk: bytes) -> bytes:
    a, prefix = _ed_secret(sk)
    pub = _ed_encode(jws._ed_mul(a, jws._EG))
    r = int.from_bytes(hashlib.sha512(prefix + message).digest(), "little") % jws._EL
    big_r = _ed_encode(jws._ed_mul(r, jws._EG))
    k = int.from_bytes(hashlib.sha512(big_r + pub + message).digest(), "little") % jws._EL
    return big_r + ((r + k * a) % jws._EL).to_bytes(32, "little")


def sign_payload(payload: bytes, kid: str, alg: str, private, header_extra: dict = None) -> str:
    """Compact JWS with the payload detached: BASE64URL(header) '..' BASE64URL(signature)."""
    header = {"alg": alg, "kid": kid}
    header.update(header_extra or {})
    h64 = jws.b64u_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    signing_input = (h64 + "." + jws.b64u_encode(payload)).encode("ascii")
    sig = es256_sign(signing_input, private) if alg == "ES256" else ed25519_sign(signing_input, private)
    return h64 + ".." + jws.b64u_encode(sig)


def sign_manifest(manifest: dict, kid: str, alg: str, private, header_extra: dict = None) -> str:
    """Signature over the JCS form of ``manifest`` with its ``signatures`` member removed (Section 6.1)."""
    return sign_payload(signing_payload(manifest), kid, alg, private, header_extra)


def with_signatures(manifest: dict, *tokens: str) -> dict:
    out = dict(manifest)
    out["signatures"] = list(tokens)
    return out
