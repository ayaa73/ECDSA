"""Tests for core/attacks.py (P4): nonce-reuse key recovery.

Skipped until P1's curve code, P2's types and P3's hashing are merged.
The demo_nonce_reuse tests additionally need P2's keys.py and P3's sign.py.
"""
from __future__ import annotations

import secrets

import pytest

pytest.importorskip("ecdsa_edu.core.curve")
pytest.importorskip("ecdsa_edu.core.hashing")
pytest.importorskip("ecdsa_edu.core.types")
pytest.importorskip("ecdsa_edu.core.curves_registry")

from ecdsa_edu.core.attacks import demo_nonce_reuse, recover_from_nonce_reuse  # noqa: E402
from ecdsa_edu.core.curve import scalar_mult  # noqa: E402
from ecdsa_edu.core.curves_registry import get_curve  # noqa: E402
from ecdsa_edu.core.field import inv_mod  # noqa: E402
from ecdsa_edu.core.hashing import hash_message  # noqa: E402
from ecdsa_edu.core.types import Signature  # noqa: E402

CURVES = ["toy-17", "toy-97", "secp256k1"]


def sign_with_k(curve, d: int, msg: bytes, k: int) -> Signature | None:
    """Test-only signer with a forced nonce, so these tests don't depend on P3's sign()."""
    n = curve.n
    R = scalar_mult(curve, k, curve.G)
    r = R[0] % n
    s = (inv_mod(k, n) * (hash_message(msg, curve) + r * d)) % n
    return None if r == 0 or s == 0 else Signature(r, s)


def reused_pair(curve, low_s_second: bool = False):
    """Random key, one random k, two messages whose hashes differ mod n."""
    n = curve.n
    for _ in range(500):
        d = 1 + secrets.randbelow(n - 1)
        k = 1 + secrets.randbelow(n - 1)
        m1, m2 = b"Pay Bob 10 USD", b"Pay Eve %d USD" % secrets.randbelow(10**6)
        if hash_message(m1, curve) % n == hash_message(m2, curve) % n:
            continue
        s1, s2 = sign_with_k(curve, d, m1, k), sign_with_k(curve, d, m2, k)
        if s1 is None or s2 is None or s1.s == s2.s:
            continue
        if low_s_second:
            s2 = Signature(s2.r, n - s2.s)
        return d, k, m1, s1, m2, s2
    pytest.skip("could not build a pair on this curve")


@pytest.mark.parametrize("name", CURVES)
def test_recovers_true_key(name):
    curve = get_curve(name)
    d, k, m1, s1, m2, s2 = reused_pair(curve)
    trace = []
    assert recover_from_nonce_reuse(curve, m1, s1, m2, s2, trace=trace) == (d, k)
    titles = [st.title for st in trace]
    assert titles[0] == "Spot the reused nonce"
    assert any("Solve for the private key" in t for t in titles)
    assert titles[-1].startswith("Check")


@pytest.mark.parametrize("name", CURVES)
def test_recovers_after_low_s_flip(name):
    curve = get_curve(name)
    d, k, m1, s1, m2, s2 = reused_pair(curve, low_s_second=True)
    trace = []
    rd, rk = recover_from_nonce_reuse(curve, m1, s1, m2, s2, trace=trace)
    assert rd == d and rk in (k, curve.n - k)
    assert any("low-s" in st.title for st in trace)


@pytest.mark.parametrize("name", CURVES)
def test_low_s_flip_makes_s_equal(name):
    """Edge case: after the signer flips s2 to n - s2 it can equal s1 exactly.
    Choosing d = -(e1 + e2) / (2r) forces s1 = -s2, i.e. flipped s2 == s1."""
    curve = get_curve(name)
    n = curve.n
    m1, m2 = b"Pay Bob 10 USD", b"Pay Eve 10 USD"
    e1, e2 = hash_message(m1, curve), hash_message(m2, curve)
    for k in range(2, n):
        r = scalar_mult(curve, k, curve.G)[0] % n
        d = (-(e1 + e2) * inv_mod(2 * r, n)) % n if r else 0
        s1 = sign_with_k(curve, d, m1, k) if d else None
        s2 = sign_with_k(curve, d, m2, k) if d else None
        if s1 and s2 and e1 % n != e2 % n:
            break
    else:
        pytest.skip("no suitable k on this curve")
    flipped = Signature(s2.r, n - s2.s)
    assert flipped.s == s1.s
    rd, rk = recover_from_nonce_reuse(curve, m1, s1, m2, flipped)
    assert rd == d and rk in (k, n - k)


def test_different_r_raises():
    curve = get_curve("secp256k1")
    d = 12345
    a = sign_with_k(curve, d, b"a", 111)
    b = sign_with_k(curve, d, b"b", 222)
    with pytest.raises(ValueError, match="did not reuse k"):
        recover_from_nonce_reuse(curve, b"a", a, b"b", b)


def test_same_signature_raises():
    curve = get_curve("secp256k1")
    sig = sign_with_k(curve, 999, b"same", 4242)
    with pytest.raises(ValueError, match="s1 == s2"):
        recover_from_nonce_reuse(curve, b"same", sig, b"same", sig)


def test_trace_optional():
    curve = get_curve("toy-97")
    d, k, m1, s1, m2, s2 = reused_pair(curve)
    assert recover_from_nonce_reuse(curve, m1, s1, m2, s2) == (d, k)


# --- demo_nonce_reuse needs P2's keys.py and P3's sign.py ------------------
@pytest.mark.parametrize("name", CURVES)
def test_demo_then_attack_matches(name):
    pytest.importorskip("ecdsa_edu.core.keys")
    pytest.importorskip("ecdsa_edu.core.sign")
    curve = get_curve(name)
    demo = demo_nonce_reuse(curve)
    assert demo["sig1"].r == demo["sig2"].r
    assert demo["msg1"] != demo["msg2"]
    d, k = recover_from_nonce_reuse(curve, demo["msg1"], demo["sig1"],
                                    demo["msg2"], demo["sig2"])
    assert d == demo["d"]
    assert k in (demo["k"], curve.n - demo["k"])
    assert scalar_mult(curve, d, curve.G) == demo["Q"]
