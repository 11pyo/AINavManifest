# -*- coding: utf-8 -*-
"""Section 6.1: detached-JWS publisher signatures. RFC test vectors, tampering, algorithm confusion,
key designation, and the rule that a valid signature relaxes nothing in Section 5."""
import copy
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from afrm import jws, jws_sign
from afrm.agent import DenyAsk, ManifestSession
from afrm.jcs import canonicalize, signing_payload
from afrm.jws import DesignatedKey, JwsError, b64u_decode, b64u_encode, verify_manifest
from afrm.pep import ASK
from test_pep import BUTTON, CELL, GRIDCELL, ORIGIN, PAGE, FakePage, key, make_manifest, trap

FIX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)
WK = ORIGIN + "/.well-known/ai-friction-manifest.json"


def appendix_a():
    return json.loads((FIX / "appendix_a.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def es():
    d, jwk = jws_sign.generate_es256(b"publisher-1")
    return d, DesignatedKey("pub-1", "ES256", jwk)


@pytest.fixture(scope="module")
def ed():
    sk, jwk = jws_sign.generate_ed25519(b"publisher-2")
    return sk, DesignatedKey("pub-2", "Ed25519", jwk)


def signed(manifest, kid, alg, private, **kw):
    return jws_sign.with_signatures(manifest, jws_sign.sign_manifest(manifest, kid, alg, private, **kw))


# ---------------------------------------------------------------- public test vectors

def test_rfc7515_a3_es256_vector():
    x = int.from_bytes(b64u_decode("f83OJ3D2xF1Bg8vub9tLe1gHMzV76e8Tus9uPHvRVEU"), "big")
    y = int.from_bytes(b64u_decode("x_FEzRu9m36HLN_tue659LNpXW6pCyStikYjKIWI5a0"), "big")
    inp = (b"eyJhbGciOiJFUzI1NiJ9.eyJpc3MiOiJqb2UiLA0KICJleHAiOjEzMDA4MTkzODAsDQogImh0dHA6Ly9leGFt"
           b"cGxlLmNvbS9pc19yb290Ijp0cnVlfQ")
    sig = b64u_decode("DtEhU3ljbEg8L38VWAfUAqOyKAM6-Xx-F4GawxaepmXFCgfTjDxw5djxLa8ISlSApmWQxfKTUJqPP3-Kg6NU1Q")
    assert jws.es256_verify(inp, sig, x, y)
    assert not jws.es256_verify(inp + b"!", sig, x, y)            # a verifier that says yes to everything fails here
    assert not jws.es256_verify(inp, sig[:-1] + bytes([sig[-1] ^ 1]), x, y)


def test_rfc8037_a4_ed25519_vector():
    pub = b64u_decode("11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo")
    inp = b"eyJhbGciOiJFZERTQSJ9.RXhhbXBsZSBvZiBFZDI1NTE5IHNpZ25pbmc"
    sig = b64u_decode("hgyY0il_MGCjP0JzlnLWG1PPOt7-09PGcvMg3AIbQR6dWbhijcNR4ki4iylGjg5BhVsPt9g7sVvpAr_MuM0KAg")
    assert jws.ed25519_verify(inp, sig, pub)
    assert not jws.ed25519_verify(inp + b" ", sig, pub)


RFC8032 = [  # (public key, message, signature) - RFC 8032 Section 7.1 tests 1-3
    ("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46b"
     "d25bf5f0595bbe24655141438e7a100b"),
    ("3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c"
     "387b2eaeb4302aeeb00d291612bb0c00"),
    ("fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb9115489080" "25", "af82",
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc659"
     "4a7c15e9716ed28dc027beceea1ec40a"),
]


@pytest.mark.parametrize("pub, msg, sig", RFC8032)
def test_rfc8032_vectors(pub, msg, sig):
    pub, msg, sig = bytes.fromhex(pub), bytes.fromhex(msg), bytes.fromhex(sig)
    assert jws.ed25519_verify(msg, sig, pub)
    assert not jws.ed25519_verify(msg + b"\0", sig, pub)


def test_curve_constants_are_the_standard_ones():
    assert jws._on_curve(jws._G) and jws._ec_mul(jws._N, jws._G) is None
    assert jws._ed_equal(jws._ed_mul(jws._EL, jws._EG), (0, 1, 1, 0))
    # RFC 8032 test 1: the private seed gives the published public key
    sk = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    assert b64u_decode(jws_sign.ed25519_public_jwk(sk)["x"]).hex() == RFC8032[0][0]
    assert jws_sign.ed25519_sign(b"", sk).hex() == RFC8032[0][2]
    # RFC 7515 A.3 key: d gives the published x, y
    d = int.from_bytes(b64u_decode("jpsQnnGQmL-YBIffH1136cspYG6-0iY7X1fCE9-E9LI"), "big")
    x, y = jws._ec_mul(d, jws._G)
    assert b64u_encode(x.to_bytes(32, "big")) == "f83OJ3D2xF1Bg8vub9tLe1gHMzV76e8Tus9uPHvRVEU"
    assert b64u_encode(y.to_bytes(32, "big")) == "x_FEzRu9m36HLN_tue659LNpXW6pCyStikYjKIWI5a0"


def test_cross_check_with_the_cryptography_library():
    ec = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ec")
    ed25519 = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature
    for i in range(3):
        msg = f"message {i}".encode()
        d, jwk = jws_sign.generate_es256(bytes([i]))                       # ours signs, theirs verifies
        pub = ec.EllipticCurvePublicNumbers(int.from_bytes(b64u_decode(jwk["x"]), "big"),
                                            int.from_bytes(b64u_decode(jwk["y"]), "big"), ec.SECP256R1()).public_key()
        sig = jws_sign.es256_sign(msg, d)
        pub.verify(encode_dss_signature(int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big")),
                   msg, ec.ECDSA(hashes.SHA256()))
        priv = ec.derive_private_key(i + 12345, ec.SECP256R1())            # theirs signs, ours verifies
        n = priv.public_key().public_numbers()
        r, s = decode_dss_signature(priv.sign(msg, ec.ECDSA(hashes.SHA256())))
        assert jws.es256_verify(msg, r.to_bytes(32, "big") + s.to_bytes(32, "big"), n.x, n.y)
        sk, pj = jws_sign.generate_ed25519(bytes([i]))
        ed25519.Ed25519PublicKey.from_public_bytes(b64u_decode(pj["x"])).verify(jws_sign.ed25519_sign(msg, sk), msg)
        theirs = ed25519.Ed25519PrivateKey.from_private_bytes(bytes([i + 1]) * 32)
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        raw_pub = theirs.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        assert jws.ed25519_verify(msg, theirs.sign(msg), raw_pub)
        with pytest.raises(InvalidSignature):                              # the oracle itself rejects a flipped message
            theirs.public_key().verify(theirs.sign(msg), msg + b"x")


# ---------------------------------------------------------------- round trip and canonical payload

@pytest.mark.parametrize("which", ["es", "ed"])
def test_round_trip_both_algorithms(which, es, ed):
    priv, dk = es if which == "es" else ed
    m = signed(appendix_a(), dk.kid, dk.alg, priv)
    out = verify_manifest(m, [dk])
    assert out.verified and out.kid == dk.kid


def test_payload_is_jcs_of_manifest_without_signatures(es):
    priv, dk = es
    m = appendix_a()
    tok = jws_sign.sign_manifest(m, dk.kid, "ES256", priv)
    assert tok.count("..") == 1 and tok.split("..")[0] == tok.split(".")[0]          # detached: empty middle part
    # the same manifest after re-serialization with another member order and escapes still verifies
    text = json.dumps(jws_sign.with_signatures(m, tok), ensure_ascii=True, indent=3, sort_keys=True)
    assert verify_manifest(json.loads(text), [dk]).verified
    # signing over the manifest INCLUDING a signatures member is a different payload and must not verify
    wrong = jws_sign.sign_payload(canonicalize(jws_sign.with_signatures(m, "x..y")).encode(), dk.kid, "ES256", priv)
    assert not verify_manifest(jws_sign.with_signatures(m, wrong), [dk]).verified
    # nor does a signer that canonicalizes with plain json.dumps (different whitespace) verify
    other = jws_sign.sign_payload(json.dumps(m).encode(), dk.kid, "ES256", priv)
    assert not verify_manifest(jws_sign.with_signatures(m, other), [dk]).verified


def test_jcs_difference_in_number_and_unicode_is_caught(es):
    priv, dk = es
    m = appendix_a()
    m["scope"] = {"includes": ["/a"], "x": 1.0}                 # 1.0 and 1 are the same JCS number
    tok = jws_sign.sign_manifest(m, dk.kid, "ES256", priv)
    m2 = json.loads(json.dumps(m).replace("1.0", "1"))
    assert verify_manifest(jws_sign.with_signatures(m2, tok), [dk]).verified
    m3 = copy.deepcopy(m2)
    m3["scope"]["x"] = 2
    assert not verify_manifest(jws_sign.with_signatures(m3, tok), [dk]).verified


# ---------------------------------------------------------------- tampering

def test_any_change_to_the_manifest_breaks_the_signature(es):
    priv, dk = es
    m = signed(appendix_a(), dk.kid, "ES256", priv)
    assert verify_manifest(m, [dk]).verified
    t = copy.deepcopy(m)
    t["knownTraps"][0]["recovery"][0]["target"] = "/evil" if "target" in t["knownTraps"][0]["recovery"][0] else None
    for mutate in (lambda x: x.__setitem__("expires", "2099-01-01T00:00:00Z"),
                   lambda x: x["knownTraps"].pop(),
                   lambda x: x.__setitem__("extra", 1),
                   lambda x: x.pop("scope", None)):
        c = copy.deepcopy(m)
        mutate(c)
        assert not verify_manifest(c, [dk]).verified


def test_tampered_signature_or_header_fails(es):
    priv, dk = es
    m = appendix_a()
    tok = jws_sign.sign_manifest(m, dk.kid, "ES256", priv)
    h, _, sig = tok.split(".")
    flipped = sig[:-2] + ("A" if sig[-2] != "A" else "B") + sig[-1]
    assert not verify_manifest(jws_sign.with_signatures(m, h + ".." + flipped), [dk]).verified
    other_hdr = b64u_encode(json.dumps({"alg": "ES256", "kid": "pub-1", "x": 1}, separators=(",", ":")).encode())
    assert not verify_manifest(jws_sign.with_signatures(m, other_hdr + ".." + sig), [dk]).verified   # header is signed


# ---------------------------------------------------------------- algorithm confusion and header abuse

def hdr(**h):
    return b64u_encode(json.dumps(h, separators=(",", ":")).encode())


def test_alg_none_and_empty_signature_rejected(es):
    _, dk = es
    m = appendix_a()
    for tok in (hdr(alg="none", kid="pub-1") + "..", hdr(alg="none", kid="pub-1") + "..AAAA",
                hdr(alg="ES256", kid="pub-1") + "..", hdr(alg="NONE", kid="pub-1") + "..AAAA"):
        assert not verify_manifest(jws_sign.with_signatures(m, tok), [dk]).verified


def test_hs256_with_the_public_key_as_secret_rejected(es):
    _, dk = es
    m = appendix_a()
    h = hdr(alg="HS256", kid="pub-1")
    payload = b64u_encode(signing_payload(m))
    for secret in (b64u_decode(dk.jwk["x"]) + b64u_decode(dk.jwk["y"]), json.dumps(dk.jwk).encode(), b"pub-1"):
        mac = hmac.new(secret, f"{h}.{payload}".encode(), hashlib.sha256).digest()
        out = verify_manifest(jws_sign.with_signatures(m, h + ".." + b64u_encode(mac)), [dk])
        assert not out.verified and any("rejected" in r for r in out.reasons)
    for alg in ("HS384", "HS512", "RS256", "PS256", "ES384", "ES512", "EdDSA", "", "es256", "ed25519"):
        tok = hdr(alg=alg, kid="pub-1") + ".." + b64u_encode(b"\0" * 64)
        assert not verify_manifest(jws_sign.with_signatures(m, tok), [dk]).verified


def test_eddsa_is_rejected_even_with_a_valid_ed25519_signature(ed):
    priv, dk = ed
    m = appendix_a()
    good = jws_sign.sign_manifest(m, dk.kid, "Ed25519", priv)
    assert verify_manifest(jws_sign.with_signatures(m, good), [dk]).verified
    bad = jws_sign.sign_manifest(m, dk.kid, "EdDSA", priv)               # RFC 9864 deprecates the polymorphic name
    assert not verify_manifest(jws_sign.with_signatures(m, bad), [dk]).verified


def test_header_alg_cannot_pick_another_algorithm_for_a_key(es, ed):
    epriv, edk = es
    spriv, sdk = ed
    clash_es = DesignatedKey("same", "ES256", edk.jwk)
    clash_ed = DesignatedKey("same", "Ed25519", sdk.jwk)
    m = appendix_a()
    tok = jws_sign.sign_manifest(m, "same", "Ed25519", spriv)
    assert verify_manifest(jws_sign.with_signatures(m, tok), [clash_es, clash_ed]).verified
    assert not verify_manifest(jws_sign.with_signatures(m, tok), [clash_es]).verified      # only an ES256 key has this kid
    tok = jws_sign.sign_manifest(m, "same", "ES256", epriv)
    assert not verify_manifest(jws_sign.with_signatures(m, tok), [clash_ed]).verified


def test_kid_mismatch_and_forged_kid(es):
    priv, dk = es
    other_priv, other = jws_sign.generate_es256(b"attacker")
    odk = DesignatedKey("pub-1", "ES256", other)                       # attacker signs claiming kid pub-1
    m = appendix_a()
    forged = jws_sign.sign_manifest(m, "pub-1", "ES256", other_priv)
    assert not verify_manifest(jws_sign.with_signatures(m, forged), [dk]).verified
    assert verify_manifest(jws_sign.with_signatures(m, forged), [odk]).verified      # control: the oracle does verify
    for kid in ("PUB-1", "pub-1 ", "pub-2", ""):
        tok = jws_sign.sign_manifest(m, kid, "ES256", priv)
        assert not verify_manifest(jws_sign.with_signatures(m, tok), [dk]).verified
    nokid = hdr(alg="ES256") + ".." + b64u_encode(b"\1" * 64)
    assert not verify_manifest(jws_sign.with_signatures(m, nokid), [dk]).verified


def test_keys_named_by_the_header_or_the_manifest_are_never_used():
    priv, jwk = jws_sign.generate_es256(b"attacker")
    m = appendix_a()
    pinned_priv, pinned_jwk = jws_sign.generate_es256(b"pinned")
    dk = DesignatedKey("k", "ES256", pinned_jwk)
    extras = [{"jwk": jwk}, {"jku": "https://evil.example/jwks"}, {"x5u": "https://evil.example/c"},
              {"x5c": ["AAAA"]}, {"jwk": jwk, "kid": "k"}]
    for extra in extras:
        tok = jws_sign.sign_manifest(m, "k", "ES256", priv, header_extra=extra)     # signed by the attacker's key
        assert not verify_manifest(jws_sign.with_signatures(m, tok), [dk]).verified, extra
    m2 = dict(m, keys=[jwk], publicKey=jwk, jwks={"keys": [jwk]}, signingKey=jwk)   # manifest declares its own key
    tok = jws_sign.sign_manifest(m2, "k", "ES256", priv)
    assert not verify_manifest(jws_sign.with_signatures(m2, tok), [dk]).verified
    assert not verify_manifest(jws_sign.with_signatures(m2, tok), []).verified      # no designated key at all


def test_crit_header_is_rejected(es):
    priv, dk = es
    m = appendix_a()
    for crit in (["exp"], [], "x"):
        tok = jws_sign.sign_manifest(m, dk.kid, "ES256", priv, header_extra={"crit": crit, "exp": 1})
        assert not verify_manifest(jws_sign.with_signatures(m, tok), [dk]).verified


def test_malformed_tokens(es):
    priv, dk = es
    m = appendix_a()
    good = jws_sign.sign_manifest(m, dk.kid, "ES256", priv)
    h, _, s = good.split(".")
    payload = b64u_encode(signing_payload(m))
    bad = [h + "." + payload + "." + s,                  # attached payload, not detached
           h + ".." + s + ".",                           # four parts
           h + "." + s, "", ".", "..", "x", h + ".." + s + "=",           # padding
           h + ".." + s[:-1] + "!", h + ".. " + s, h + "..\n" + s,
           "e30..AAAA",                                  # header {} has no alg/kid
           hdr(alg="ES256", kid="pub-1")[:-1] + "..AAAA",
           b64u_encode(b'{"alg":"ES256","alg":"none","kid":"pub-1"}') + ".." + s,    # duplicate member (I-JSON)
           b64u_encode(b"[1]") + ".." + s, b64u_encode(b"\xff\xfe") + ".." + s,
           b64u_encode(b'{"alg":"ES256","kid":"pub-1"}' + b"\x00") + ".." + s,
           5, None, {"keyId": "x"}, ["x"]]
    for tok in bad:
        out = verify_manifest(jws_sign.with_signatures(m, tok), [dk])
        assert not out.verified, tok


def test_non_canonical_base64url_is_rejected(es):
    priv, dk = es
    m = appendix_a()
    h, _, s = jws_sign.sign_manifest(m, dk.kid, "ES256", priv).split(".")
    last = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    assert len(s) % 4 == 2 and last.index(s[-1]) % 16 == 0          # 64 octets = 86 characters: the last carries 4 unused bits
    twin = s[:-1] + last[last.index(s[-1]) + 1]                      # same octets, different trailing bits
    import base64
    assert base64.urlsafe_b64decode(twin + "==") == base64.urlsafe_b64decode(s + "==")   # a lenient decoder cannot tell them apart
    assert not verify_manifest(jws_sign.with_signatures(m, h + ".." + twin), [dk]).verified
    with pytest.raises(JwsError):
        b64u_decode(twin)


# ---------------------------------------------------------------- signature encoding and key validity

def test_es256_signature_encoding_and_range(es):
    priv, dk = es
    msg = b"abc"
    x, y = dk._material
    sig = jws_sign.es256_sign(msg, priv)
    assert jws.es256_verify(msg, sig, x, y)
    r, s = int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big")
    assert jws.es256_verify(msg, sig[:32] + (jws._N - s).to_bytes(32, "big"), x, y)      # high-s is valid ECDSA (RFC 7518 does not forbid it)
    for bad in (sig[:63], sig + b"\0", b"\0" * 64, sig[:32] + b"\0" * 32, b"\0" * 32 + sig[32:],
                (r + jws._N).to_bytes(33, "big")[1:] + sig[32:], sig[:32] + (s + jws._N).to_bytes(33, "big")[1:],
                b"\xff" * 64, b"", b"0\x44" + sig):                # DER and raw garbage
        assert not jws.es256_verify(msg, bad, x, y)


def test_ed25519_malleability_and_bad_encodings(ed):
    priv, dk = ed
    pub = dk._material[0]
    msg = b"abc"
    sig = jws_sign.ed25519_sign(msg, priv)
    assert jws.ed25519_verify(msg, sig, pub)
    s = int.from_bytes(sig[32:], "little")
    assert not jws.ed25519_verify(msg, sig[:32] + (s + jws._EL).to_bytes(32, "little"), pub)       # S + L
    for bad in (sig[:63], sig + b"\0", b"\0" * 64, b"\xff" * 64, b""):
        assert not jws.ed25519_verify(msg, bad, pub)
    assert not jws.ed25519_verify(msg, sig, pub[:31]) and not jws.ed25519_verify(msg, sig, b"\xff" * 32)


def test_designated_key_validation():
    d, jwk = jws_sign.generate_es256(b"k")
    DesignatedKey("a", "ES256", jwk)
    for args in (("a", "ES256", dict(jwk, crv="P-384")), ("a", "ES256", dict(jwk, kty="OKP")),
                 ("a", "ES256", dict(jwk, y=jwk["x"])),                                  # not on the curve
                 ("a", "ES256", dict(jwk, x=jwk["x"][:-2])), ("a", "ES256", {}), ("a", "ES256", None),
                 ("a", "HS256", jwk), ("a", "none", jwk), ("a", "EdDSA", jwk), ("", "ES256", jwk),
                 ("a", "Ed25519", jwk), ("a", "ES256", {"kty": "oct", "k": "AAAA"})):
        with pytest.raises(JwsError):
            DesignatedKey(*args)
    _, ej = jws_sign.generate_ed25519(b"k")
    DesignatedKey("a", "Ed25519", ej)
    with pytest.raises(JwsError):
        DesignatedKey("a", "Ed25519", dict(ej, crv="Ed448"))
    with pytest.raises(JwsError):
        DesignatedKey("a", "Ed25519", dict(ej, x=b64u_encode(b"\xff" * 32)))


# ---------------------------------------------------------------- limits

def test_many_signatures_cost_is_bounded(es):
    priv, dk = es
    m = appendix_a()
    junk_same_kid = [jws_sign.sign_payload(b"x", dk.kid, "ES256", priv) for _ in range(40)]
    good = jws_sign.sign_manifest(m, dk.kid, "ES256", priv)
    t = time.time()
    out = verify_manifest(dict(m, signatures=junk_same_kid + [good]), [dk])
    assert not out.verified and time.time() - t < 20                  # budget reached before the good one
    assert any("stopped after" in r for r in out.reasons)
    assert verify_manifest(dict(m, signatures=junk_same_kid[:jws.MAX_VERIFY_ATTEMPTS - 1] + [good]), [dk]).verified
    unknown = [hdr(alg="ES256", kid=f"k{i}") + ".." + b64u_encode(b"\1" * 64) for i in range(5000)]
    t = time.time()
    assert verify_manifest(dict(m, signatures=unknown + [good]), [dk]).verified      # undesignated kids cost no arithmetic
    assert time.time() - t < 20


def test_first_bad_then_good_signature_verifies(es, ed):
    (epriv, edk), (spriv, sdk) = es, ed
    m = appendix_a()
    bad = jws_sign.sign_manifest(m, "pub-1", "ES256", jws_sign.generate_es256(b"x")[0])
    good = jws_sign.sign_manifest(m, "pub-2", "Ed25519", spriv)
    out = verify_manifest(jws_sign.with_signatures(m, "junk", bad, good), [edk, sdk])
    assert out.verified and out.kid == "pub-2" and len(out.reasons) == 2


def test_no_signatures_member(es):
    _, dk = es
    for m in (appendix_a(), dict(appendix_a(), signatures=[]), dict(appendix_a(), signatures="x"),
              dict(appendix_a(), signatures={})):
        assert not verify_manifest(m, [dk]).verified


# ---------------------------------------------------------------- session: designation, fail closed, no widening

def fetcher(manifest):
    raw = json.dumps(manifest).encode("utf-8")
    return lambda page_url: (raw, WK)


def disc(manifest, keys=None, ask=None):
    page = FakePage([(CELL, [GRIDCELL])])
    s = ManifestSession(page, ask=ask or DenyAsk(), designated_keys=keys or {})
    return s, s.discover(fetch=fetcher(manifest), now=NOW)


def base():
    return make_manifest(trap("t1", key("Enter", CELL)))


def test_designated_key_requires_a_verifying_signature(es):
    priv, dk = es
    keys = {ORIGIN: [dk]}
    s, ok = disc(signed(base(), dk.kid, "ES256", priv), keys)
    assert ok and s.signed_by == "pub-1" and s.manifest is not None
    s, ok = disc(base(), keys)                                          # unsigned: MUST be ignored
    assert not ok and s.manifest is None and "Section 6.1" in s.rejected_reason and s.signed_by is None
    _, other = jws_sign.generate_es256(b"someone-else")
    s, ok = disc(signed(base(), dk.kid, "ES256", priv), {ORIGIN: [DesignatedKey("pub-1", "ES256", other)]})
    assert not ok and s.manifest is None
    s, ok = disc(signed(base(), dk.kid, "ES256", priv), {"https://other.example": [dk]})   # designation is per origin
    assert ok and s.signed_by is None


def test_no_designated_key_means_signatures_are_ignored(es):
    priv, dk = es
    for m in (base(), signed(base(), dk.kid, "ES256", priv),
              dict(base(), signatures=[hdr(alg="none", kid="x") + "..AAAA"])):
        s, ok = disc(m, {})
        assert ok and s.signed_by is None
        s, ok = disc(m, {ORIGIN: []})
        assert ok


def test_valid_signature_does_not_bypass_validation(es):
    priv, dk = es
    keys = {ORIGIN: [dk]}
    expired = dict(base(), expires="2026-01-01T00:00:00Z")
    s, ok = disc(signed(expired, dk.kid, "ES256", priv), keys)
    assert not ok and s.manifest is None
    wrong_origin = dict(base(), origin="https://evil.example")
    s, ok = disc(signed(wrong_origin, dk.kid, "ES256", priv), keys)
    assert not ok
    bad_version = dict(base(), version="1.0")
    assert not disc(signed(bad_version, dk.kid, "ES256", priv), keys)[1]


def test_payload_covers_descriptors_the_agent_drops(es):
    priv, dk = es
    m = base()
    m["knownTraps"].append({"trapId": "broken", "category": "commit-gesture"})      # invalid descriptor, dropped on load
    s, ok = disc(signed(m, dk.kid, "ES256", priv), {ORIGIN: [dk]})
    assert ok and [t["trapId"] for t in s.manifest["knownTraps"]] == ["t1"]


def test_verified_signature_changes_no_pep_decision(es):
    """Section 6.1: a valid signature MUST NOT relax any Section 5 requirement. Same page, same
    manifest content, signed-and-verified vs unsigned: every PEP outcome and reason is identical."""
    priv, dk = es
    el = {"role": "button", "name": "Save"}
    for steps in ([key("Enter", CELL)], [key("Escape", CELL)], [key("Enter", el)],
                  [{"action": "click", "locator": el}], [{"action": "wait", "timeoutMs": 9000}]):
        outcomes = []
        for signed_ in (False, True):
            m = make_manifest(trap("t1", *steps))
            if signed_:
                m = signed(m, dk.kid, "ES256", priv)
            page = FakePage([(CELL, [GRIDCELL]), (el, [BUTTON])])
            s = ManifestSession(page, ask=DenyAsk(), designated_keys={ORIGIN: [dk]} if signed_ else {})
            assert s.discover(fetch=fetcher(m), now=NOW)
            assert (s.signed_by is not None) == signed_
            res = s.recover(1)
            outcomes.append((res.status, [(r.outcome, r.reason) for r in s.audit.records], page.done))
        assert outcomes[0] == outcomes[1], steps
    # and Enter on a gridcell is still an ask, under a verified signature
    m = signed(make_manifest(trap("t1", key("Enter", CELL))), dk.kid, "ES256", priv)
    s = ManifestSession(FakePage([(CELL, [GRIDCELL])]), ask=DenyAsk(), designated_keys={ORIGIN: [dk]})
    assert s.discover(fetch=fetcher(m), now=NOW) and s.recover(1).status == "abandoned"
    assert s.audit.records[-1].outcome == ASK


def test_the_pep_does_not_import_the_signature_module():
    src = (Path(__file__).parent.parent / "afrm" / "pep.py").read_text(encoding="utf-8")
    assert "jws" not in src and "signed_by" not in src and "designated" not in src


def test_unexpected_error_in_verification_fails_closed(es, monkeypatch):
    priv, dk = es

    def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr("afrm.agent.verify_manifest", boom)
    s, ok = disc(signed(base(), dk.kid, "ES256", priv), {ORIGIN: [dk]})
    assert not ok and s.manifest is None and "signature check failed" in s.rejected_reason
