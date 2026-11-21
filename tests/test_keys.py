"""Tests for core/types.py and core/keys.py (owner: P2).

The third-party ``ecdsa`` and ``cryptography`` packages are used here - and only
here, in tests - as independent references to cross-check our own results.
"""
from __future__ import annotations

import dataclasses
import secrets

import pytest

from ecdsa_edu.core import keys as keys_module
from ecdsa_edu.core.curve import Curve, is_on_curve
from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.keys import generate_keypair, public_from_private, validate_public_point
from ecdsa_edu.core.types import PrivateKey, PublicKey, Signature

# k*G for k = 1..18 on toy-17 (y^2 = x^3 + 2x + 2 mod 17, G = (5, 1), n = 19).
# Standard textbook table (Paar & Pelzl, "Understanding Cryptography", ch. 9).
TOY_MULTIPLES = [
    (5, 1), (6, 3), (10, 6), (3, 1), (9, 16), (16, 13), (0, 6), (13, 7), (7, 6),
    (7, 11), (13, 10), (0, 11), (16, 4), (9, 1), (3, 16), (10, 11), (6, 14), (5, 16),
]
REAL_CURVES = ["secp256k1", "P-256"]

# y^2 = x^3 + x + 1 (mod 23) has 28 points. G = (5, 4) has prime order 7, so the
# cofactor is 4 and some curve points are NOT multiples of G, e.g. (0, 1).
COFACTOR_CURVE = Curve(name="cofactor-23", p=23, a=1, b=1, G=(5, 4), n=7, h=4)


@pytest.fixture
def toy() -> Curve:
    return get_curve("toy-17")


# ----------------------------------------------------------------- types
def test_types_are_frozen(toy):
    priv, pub = PrivateKey(7, toy), PublicKey((0, 6), toy)
    with pytest.raises(dataclasses.FrozenInstanceError):
        priv.d = 8  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        pub.Q = (5, 1)  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        Signature(1, 2).r = 3  # type: ignore[misc]


def test_types_compare_by_value(toy):
    assert PrivateKey(7, toy) == PrivateKey(7, toy)
    assert PublicKey((0, 6), toy) != PublicKey((5, 1), toy)
    assert Signature(3, 4) == Signature(3, 4)


def test_private_key_repr_does_not_leak_d():
    k1 = get_curve("secp256k1")
    d = 0x1234567890ABCDEF1234567890ABCDEF
    text = repr(PrivateKey(d, k1))
    assert str(d) not in text and hex(d)[2:] not in text.lower()


# --------------------------------------------------- public_from_private
@pytest.mark.parametrize("d", range(1, 19))
def test_toy_public_key_for_every_private_key(toy, d):
    assert public_from_private(PrivateKey(d, toy)).Q == TOY_MULTIPLES[d - 1]


def test_public_key_carries_the_curve(toy):
    pub = public_from_private(PrivateKey(7, toy))
    assert isinstance(pub, PublicKey) and pub.curve is toy


@pytest.mark.parametrize("bad_d", [0, -1, 19, 20, 19 * 2 + 7])
def test_out_of_range_private_key_is_rejected(toy, bad_d):
    with pytest.raises(ValueError):
        public_from_private(PrivateKey(bad_d, toy))


@pytest.mark.parametrize("bad_d", [7.0, "7", None, True])
def test_non_integer_private_key_is_rejected(toy, bad_d):
    with pytest.raises(ValueError):
        public_from_private(PrivateKey(bad_d, toy))  # type: ignore[arg-type]


def _edge_and_random_scalars(n: int) -> list[int]:
    rng = secrets.SystemRandom()
    return [1, 2, 3, n - 2, n - 1] + [rng.randrange(1, n) for _ in range(5)]


@pytest.mark.parametrize("name", REAL_CURVES)
def test_public_key_matches_python_ecdsa(name):
    ecdsa = pytest.importorskip("ecdsa")
    reference_curve = {"secp256k1": ecdsa.SECP256k1, "P-256": ecdsa.NIST256p}[name]
    curve = get_curve(name)
    for d in _edge_and_random_scalars(curve.n):
        point = ecdsa.SigningKey.from_secret_exponent(d, curve=reference_curve).verifying_key.pubkey.point
        assert public_from_private(PrivateKey(d, curve)).Q == (point.x(), point.y())


@pytest.mark.parametrize("name", REAL_CURVES)
def test_public_key_matches_cryptography(name):
    ec = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ec")
    reference_curve = {"secp256k1": ec.SECP256K1(), "P-256": ec.SECP256R1()}[name]
    curve = get_curve(name)
    for d in _edge_and_random_scalars(curve.n):
        numbers = ec.derive_private_key(d, reference_curve).public_key().public_numbers()
        assert public_from_private(PrivateKey(d, curve)).Q == (numbers.x, numbers.y)


# ------------------------------------------------------ generate_keypair
@pytest.mark.parametrize("name", ["toy-17", "toy-97", *REAL_CURVES])
def test_generated_keypair_is_consistent(name):
    curve = get_curve(name)
    priv, pub = generate_keypair(curve)
    assert isinstance(priv, PrivateKey) and isinstance(pub, PublicKey)
    assert priv.curve is curve and pub.curve is curve
    assert 1 <= priv.d <= curve.n - 1
    assert is_on_curve(curve, pub.Q)
    assert pub == public_from_private(priv)
    validate_public_point(curve, pub.Q)  # must not raise


def test_generated_keys_stay_in_range_and_vary(toy):
    seen = {generate_keypair(toy)[0].d for _ in range(400)}
    assert seen <= set(range(1, 19))
    # 400 draws from 18 values: missing even one value has probability ~ 2e-9.
    assert seen == set(range(1, 19))


def test_two_real_keys_differ():
    curve = get_curve("secp256k1")
    assert generate_keypair(curve)[0].d != generate_keypair(curve)[0].d


@pytest.mark.parametrize("raw, expected_d", [(0, 1), (5, 6), (17, 18)])
def test_generate_maps_csprng_output_to_1_n_minus_1(toy, monkeypatch, raw, expected_d):
    """d must be secrets.randbelow(n - 1) + 1: uniform on [1, n-1], never 0 or n."""
    calls = []

    def fake_randbelow(upper):
        calls.append(upper)
        return raw

    monkeypatch.setattr(keys_module.secrets, "randbelow", fake_randbelow)
    priv, pub = generate_keypair(toy)
    assert calls == [toy.n - 1]
    assert priv.d == expected_d and pub.Q == TOY_MULTIPLES[expected_d - 1]


def test_generate_rejects_degenerate_order():
    with pytest.raises(ValueError):
        generate_keypair(Curve("bad", 17, 2, 2, (5, 1), 1, 1))


# ------------------------------------------------------------------ trace
def test_trace_none_is_accepted(toy):
    assert public_from_private(PrivateKey(7, toy), None).Q == (0, 6)
    generate_keypair(toy, None)


def test_public_from_private_trace(toy):
    trace: list = []
    pub = public_from_private(PrivateKey(7, toy), trace)
    assert len(trace) >= 2
    first, last = trace[0], trace[-1]
    assert first.values["d"] == "7" and first.values["Gx"] == "5" and first.values["Gy"] == "1"
    assert "Q = d * G" in last.title
    assert (last.values["Qx"], last.values["Qy"]) == (str(pub.Q[0]), str(pub.Q[1]))
    for step in trace:
        assert step.title and isinstance(step.formula, str)
        assert all(isinstance(k, str) and isinstance(v, str) for k, v in step.values.items())


def test_generate_trace_starts_with_the_random_choice(toy):
    trace: list = []
    priv, _ = generate_keypair(toy, trace)
    assert "private key" in trace[0].title.lower()
    assert trace[0].values == {"n": "19", "d": str(priv.d)}
    assert "Q = d * G" in trace[-1].title


def test_trace_uses_hex_on_real_curves():
    curve = get_curve("P-256")
    trace: list = []
    priv, pub = generate_keypair(curve, trace)
    assert trace[0].values["d"] == hex(priv.d)
    assert trace[-1].values["Qx"] == hex(pub.Q[0])


def test_trace_does_not_change_the_result(toy):
    assert public_from_private(PrivateKey(11, toy), []) == public_from_private(PrivateKey(11, toy))


# ------------------------------------------------- validate_public_point
@pytest.mark.parametrize("Q", TOY_MULTIPLES)
def test_valid_points_pass(toy, Q):
    validate_public_point(toy, Q)


@pytest.mark.parametrize(
    "Q, reason",
    [
        (None, "infinity"),
        ((5, 2), "not on the curve"),
        ((5, 1 + 17), "range"),
        ((-12, 1), "range"),
        ((17, 0), "range"),
    ],
)
def test_invalid_points_are_rejected(toy, Q, reason):
    with pytest.raises(ValueError, match=reason):
        validate_public_point(toy, Q)


def test_point_outside_the_subgroup_is_rejected():
    assert is_on_curve(COFACTOR_CURVE, (0, 1))
    with pytest.raises(ValueError, match="subgroup"):
        validate_public_point(COFACTOR_CURVE, (0, 1))
    validate_public_point(COFACTOR_CURVE, COFACTOR_CURVE.G)  # a real multiple of G is fine
