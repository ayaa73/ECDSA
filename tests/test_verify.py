"""Tests for core/verify.py (P4), Phase 1.

These need P1's curve code, P2's types and P3's hashing. Until those are merged
the whole module is skipped instead of erroring.
"""
from __future__ import annotations

import pytest

pytest.importorskip("ecdsa_edu.core.curve")
pytest.importorskip("ecdsa_edu.core.hashing")
pytest.importorskip("ecdsa_edu.core.types")
pytest.importorskip("ecdsa_edu.core.curves_registry")

from ecdsa_edu.core.curves_registry import get_curve  # noqa: E402
from ecdsa_edu.core.types import PublicKey, Signature  # noqa: E402
from ecdsa_edu.core.verify import (  # noqa: E402
    _verify_digest,
    explain_verify_math,
    verify,
    verify_file,
)


def last_title(trace) -> str:
    return trace[-1].title


# --- Textbook example (Paar & Pelzl, toy-17) --------------------------------
# d = 7, Q = 7G = (0, 6), k = 10, R = 10G = (7, 11), r = 7, h(x) = 26, s = 17
@pytest.fixture
def toy():
    curve = get_curve("toy-17")
    return curve, PublicKey((0, 6), curve)


def test_textbook_example_valid(toy):
    curve, pub = toy
    trace = []
    assert _verify_digest(pub, 26, Signature(7, 17), trace) is True
    assert last_title(trace).startswith("VALID")
    values = {k: v for step in trace for k, v in step.values.items()}
    assert values["w"] == "9" and values["u1"] == "6" and values["u2"] == "6"


def test_textbook_example_wrong_hash(toy):
    curve, pub = toy
    trace = []
    assert _verify_digest(pub, 25, Signature(7, 17), trace) is False
    assert "x1 mod n != r" in last_title(trace)


@pytest.mark.parametrize("r, s, reason", [
    (0, 17, "r out of range"),
    (19, 17, "r out of range"),
    (7, 0, "s out of range"),
    (7, 19, "s out of range"),
    (-1, 5, "r out of range"),
])
def test_out_of_range(toy, r, s, reason):
    _, pub = toy
    trace = []
    assert verify(pub, b"hello", Signature(r, s), trace=trace) is False
    assert reason in last_title(trace)


def test_public_key_not_on_curve(toy):
    curve, _ = toy
    trace = []
    assert verify(PublicKey((1, 1), curve), b"hello", Signature(7, 17), trace=trace) is False
    assert "not on the curve" in last_title(trace)


def test_never_raises_on_garbage(toy):
    curve, pub = toy
    trace = []
    assert verify(pub, b"hello", Signature(7, 17), hash_name="nope", trace=trace) is False
    assert last_title(trace).startswith("INVALID")
    assert verify(pub, b"hello", Signature("x", 3)) is False  # type: ignore[arg-type]


def test_trace_is_optional(toy):
    _, pub = toy
    assert verify(pub, b"hello", Signature(7, 17)) in (True, False)


# --- Interop: signatures made by the `cryptography` library ----------------
ec = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ec")
from cryptography.hazmat.primitives import hashes  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature  # noqa: E402

LIB_CURVES = {"secp256k1": ec.SECP256K1, "P-256": ec.SECP256R1}


def lib_sign(curve_name: str, msg: bytes):
    key = ec.generate_private_key(LIB_CURVES[curve_name]())
    nums = key.public_key().public_numbers()
    r, s = decode_dss_signature(key.sign(msg, ec.ECDSA(hashes.SHA256())))
    curve = get_curve(curve_name)
    return PublicKey((nums.x, nums.y), curve), Signature(r, s)


@pytest.mark.parametrize("curve_name", ["secp256k1", "P-256"])
def test_library_signature_verifies(curve_name):
    pub, sig = lib_sign(curve_name, b"EECE 455 ECDSA Lab")
    trace = []
    assert verify(pub, b"EECE 455 ECDSA Lab", sig, trace=trace) is True
    assert last_title(trace).startswith("VALID")


@pytest.mark.parametrize("curve_name", ["secp256k1", "P-256"])
def test_library_signature_tampered(curve_name):
    pub, sig = lib_sign(curve_name, b"pay Bob 10 dollars")
    n = pub.curve.n
    trace = []
    assert verify(pub, b"pay Bob 99 dollars", sig, trace=trace) is False
    assert "x1 mod n != r" in last_title(trace)
    assert verify(pub, b"pay Bob 10 dollars", Signature(sig.r, (sig.s + 1) % n or 1)) is False
    assert verify(pub, b"pay Bob 10 dollars", Signature((sig.r + 1) % n or 1, sig.s)) is False


def test_wrong_public_key():
    pub1, sig = lib_sign("secp256k1", b"msg")
    pub2, _ = lib_sign("secp256k1", b"msg")
    assert verify(pub1, b"msg", sig) is True
    assert verify(pub2, b"msg", sig) is False


def test_verify_file(tmp_path):
    data = b"file contents " * 5000
    path = tmp_path / "doc.bin"
    path.write_bytes(data)
    pub, sig = lib_sign("secp256k1", data)
    assert verify_file(pub, path, sig) is True
    trace = []
    assert verify_file(pub, tmp_path / "missing.bin", sig, trace=trace) is False
    assert "could not read file" in last_title(trace)


def test_explain_verify_math():
    text = explain_verify_math()
    assert "u1*G + u2*Q" in text and "k*G" in text
