"""Tests for RFC 6979 and P3 ECDSA signature generation."""
from __future__ import annotations

import pytest

from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.hashing import hash_message
from ecdsa_edu.core.keys import public_from_private
from ecdsa_edu.core.rfc6979 import generate_k_candidates
from ecdsa_edu.core.sign import normalize_low_s, sign, sign_file
from ecdsa_edu.core.types import PrivateKey, Signature
from ecdsa_edu.core.verify import verify, verify_file


def test_toy17_forced_nonce_is_hand_checkable():
    curve = get_curve("toy-17")
    priv = PrivateKey(7, curve)

    # SHA-256("hello") starts with the five-bit value 5 on this tiny curve.
    # With d=7 and k=10: R=10G=(7,11), r=7, k^-1=2, and s=13.
    sig = sign(priv, b"hello", k=10)
    assert sig == Signature(7, 13)
    assert verify(public_from_private(priv), b"hello", sig)


def test_rfc6979_p256_sha256_sample_vector():
    """RFC 6979 Appendix A.2.5, message = "sample", SHA-256."""
    curve = get_curve("P-256")
    d = int("C9AFA9D845BA75166B5C215767B1D6934E50C3DB36E89B127B8A622B120F6721", 16)
    expected_k = int("A6E3C57DD01ABE90086538398355DD4C3B17AA873382B0F24D6129493D8AAD60", 16)
    e = hash_message(b"sample", curve, "sha256")
    assert next(generate_k_candidates(d, e, curve.n, "sha256")) == expected_k


def test_sign_matches_rfc6979_p256_sha256_sample_vector():
    """The r and s values from the same official RFC 6979 vector."""
    curve = get_curve("P-256")
    d = int("C9AFA9D845BA75166B5C215767B1D6934E50C3DB36E89B127B8A622B120F6721", 16)
    expected = Signature(
        int("EFD48B2AACB6A8FD1140DD9CD45E81D69D2C877B56AAF991C34D0EA84EAF3716", 16),
        int("F7CB1C942D657C41D436C7A1B6E29F65F3E900DBB9AFF4064DC4AB2F843ACDA8", 16),
    )
    assert sign(PrivateKey(d, curve), b"sample", "sha256") == expected


def test_rfc6979_trace_contains_state_and_candidate_without_private_key():
    curve = get_curve("P-256")
    trace = []
    sign(PrivateKey(7, curve), b"trace example", trace=trace)
    values = [step.values for step in trace]
    assert any("K" in item and "V" in item for item in values)
    assert any("k" in item and item.get("accepted") == "yes" for item in values)
    assert all("d" not in item for item in values)


@pytest.mark.parametrize(
    "curve_name, library_curve",
    [
        ("P-256", "SECP256R1"),
        ("secp256k1", "SECP256K1"),
    ],
)
def test_our_signature_verifies_with_cryptography(curve_name, library_curve):
    """Cross-check signatures with a library that is used only inside tests."""
    ec = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ec")
    hashes = pytest.importorskip("cryptography.hazmat.primitives.hashes")
    utils = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.utils")

    curve = get_curve(curve_name)
    priv = PrivateKey(2026, curve)
    pub = public_from_private(priv)
    message = b"independent ECDSA verification"
    sig = sign(priv, message)

    curve_type = getattr(ec, library_curve)
    library_key = ec.EllipticCurvePublicNumbers(*pub.Q, curve_type()).public_key()
    der_signature = utils.encode_dss_signature(sig.r, sig.s)
    # cryptography raises InvalidSignature on failure, so reaching this line's
    # end is the successful result.
    library_key.verify(der_signature, message, ec.ECDSA(hashes.SHA256()))


@pytest.mark.parametrize("curve_name", ["toy-17", "secp256k1", "P-256"])
def test_deterministic_signature_repeats_and_verifies(curve_name):
    curve = get_curve(curve_name)
    priv = PrivateKey(3, curve)
    pub = public_from_private(priv)
    first = sign(priv, b"same key and same message")
    second = sign(priv, b"same key and same message")
    assert first == second
    assert verify(pub, b"same key and same message", first)


def test_different_messages_get_different_deterministic_signatures():
    curve = get_curve("secp256k1")
    priv = PrivateKey(12345, curve)
    assert sign(priv, b"message one") != sign(priv, b"message two")


def test_random_mode_produces_valid_signatures():
    curve = get_curve("secp256k1")
    priv = PrivateKey(12345, curve)
    pub = public_from_private(priv)
    first = sign(priv, b"hello", deterministic=False)
    second = sign(priv, b"hello", deterministic=False)
    assert first != second
    assert verify(pub, b"hello", first)
    assert verify(pub, b"hello", second)


@pytest.mark.parametrize("bad_k", [0, 19, -1, True, 1.5])
def test_rejects_invalid_manual_nonce(bad_k):
    curve = get_curve("toy-17")
    with pytest.raises(ValueError, match="nonce k"):
        sign(PrivateKey(7, curve), b"hello", k=bad_k)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_d", [0, 19, -1, True])
def test_rejects_invalid_private_key(bad_d):
    curve = get_curve("toy-17")
    with pytest.raises(ValueError, match="private key d"):
        sign(PrivateKey(bad_d, curve), b"hello")


def test_sign_file_and_trace(tmp_path):
    curve = get_curve("secp256k1")
    priv = PrivateKey(2026, curve)
    pub = public_from_private(priv)
    path = tmp_path / "report.txt"
    path.write_bytes(b"our ECDSA project report")
    trace = []
    sig = sign_file(priv, path, trace=trace)
    assert verify_file(pub, path, sig)
    assert trace[0].title == "Hash the file"
    assert trace[-1].title == "ECDSA signature is ready"


def test_low_s_normalization_is_explicit():
    assert normalize_low_s(Signature(7, 17), 19) == Signature(7, 2)
    assert normalize_low_s(Signature(7, 2), 19) == Signature(7, 2)
