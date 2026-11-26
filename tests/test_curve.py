"""Tests for P1 affine curve arithmetic and textbook toy-17 multiples."""
import random

import pytest

from ecdsa_edu.core.curve import (
    Curve, enumerate_points, is_on_curve, point_add, point_double,
    point_neg, scalar_mult, make_custom_curve,
)

from ecdsa_edu.core.field import is_probable_prime
from ecdsa_edu.core.curves_registry import get_curve, suggest_small_curves

TOY = get_curve("toy-17")
# k*G for k = 1..19, with O represented as None.
EXPECTED = [
    (5, 1), (6, 3), (10, 6), (3, 1), (9, 16), (16, 13),
    (0, 6), (13, 7), (7, 6), (7, 11), (13, 10), (0, 11),
    (16, 4), (9, 1), (3, 16), (10, 11), (6, 14), (5, 16), None,
]


def test_generator_order():
    assert scalar_mult(TOY, 19, TOY.G) is None


def test_all_nonzero_multiples_on_curve():
    assert all(is_on_curve(TOY, scalar_mult(TOY, k, TOY.G)) for k in range(1, 19))


def test_enumeration():
    points = enumerate_points(TOY)
    assert len(points) == 19
    assert len(set(points)) == 19
    assert set(points) == set(EXPECTED)


def test_textbook_multiples():
    assert [scalar_mult(TOY, k, TOY.G) for k in range(1, 20)] == EXPECTED


def test_group_law_random():
    rng = random.Random(2026)
    for _ in range(100):
        a, b = rng.randrange(0, 100), rng.randrange(0, 100)
        assert scalar_mult(TOY, a + b, TOY.G) == point_add(
            TOY, scalar_mult(TOY, a, TOY.G), scalar_mult(TOY, b, TOY.G)
        )


def test_special_cases():
    G = TOY.G
    assert point_add(TOY, None, G) == G
    assert point_add(TOY, G, None) == G
    assert point_add(TOY, G, point_neg(TOY, G)) is None
    assert point_add(TOY, G, G) == point_double(TOY, G)
    assert point_double(TOY, None) is None
    # y=0 on a small nonsingular curve, so tangent is vertical.
    other = Curve("y-zero", 5, 1, 0, (0, 0), 2, 2)
    assert point_double(other, (0, 0)) is None


def test_traces():
    steps = []
    point_add(TOY, TOY.G, scalar_mult(TOY, 2, TOY.G), steps)
    assert {"Addition slope", "Addition x-coordinate", "Addition y-coordinate"} <= {s.title for s in steps}
    steps = []
    point_double(TOY, TOY.G, steps)
    assert {"Doubling slope", "Doubling x-coordinate", "Doubling y-coordinate"} <= {s.title for s in steps}
    bits, full = [], []
    assert scalar_mult(TOY, 13, TOY.G, bits) == scalar_mult(TOY, 13, TOY.G, full, "full")
    assert len(bits) == 4
    assert len(full) > len(bits)
    assert all(step.title == "Scalar bit" for step in bits)


def test_enumeration_guard():
    curve = get_curve("secp256k1")

    with pytest.raises(ValueError):
        enumerate_points(curve)

# Standard curves
@pytest.mark.parametrize("name", ["secp256k1", "P-256"])
def test_standard_curve_parameters(name):
    curve = get_curve(name)

    # The curve must be nonsingular.
    assert (4 * curve.a**3 + 27 * curve.b**2) % curve.p != 0

    # Generator must be valid.
    assert is_on_curve(curve, curve.G)

    # Generator order must be prime.
    assert is_probable_prime(curve.n)

    # Multiplying G by its order must give infinity.
    assert scalar_mult(curve, curve.n, curve.G) is None


@pytest.mark.parametrize("name", ["secp256k1", "P-256"])
def test_standard_curves_against_ecdsa_library(name):
    ecdsa = pytest.importorskip("ecdsa")

    curve = get_curve(name)

    reference = {
        "secp256k1": ecdsa.SECP256k1,
        "P-256": ecdsa.NIST256p,
    }[name]

    # Verify the registered domain parameters.
    assert curve.p == reference.curve.p()
    assert curve.a % curve.p == reference.curve.a() % curve.p
    assert curve.b == reference.curve.b()
    assert curve.n == reference.order
    assert curve.G == (
        reference.generator.x(),
        reference.generator.y()
    )

    rng = random.Random(2026)

    for _ in range(5):
        k = rng.randrange(1, curve.n)

        ours = scalar_mult(curve, k, curve.G)
        expected = k * reference.generator

        assert ours == (expected.x(), expected.y())



# toy-97


def test_toy97_prime_group():
    curve = get_curve("toy-97")

    assert curve.p == 97
    assert is_probable_prime(curve.n)
    assert curve.n == 79
    assert curve.h == 1

    assert (4 * curve.a**3 + 27 * curve.b**2) % 97 != 0
    assert is_on_curve(curve, curve.G)

    points = enumerate_points(curve)

    assert len(points) == 79
    assert len(set(points)) == 79
    assert scalar_mult(curve, curve.n, curve.G) is None



# Custom curves


def test_custom_curve_valid():
    curve = make_custom_curve(17, 2, 2, (5, 1))

    assert curve.n == 19
    assert curve.h == 1
    assert scalar_mult(curve, curve.n, curve.G) is None


def test_custom_curve_toy97():
    curve = make_custom_curve(97, 0, 5, (1, 43))

    assert curve.n == 79
    assert curve.h == 1


def test_custom_curve_invalid_prime():
    with pytest.raises(ValueError, match="prime"):
        make_custom_curve(15, 2, 2, (5, 1))


def test_custom_curve_too_large():
    with pytest.raises(ValueError, match="below 5000"):
        make_custom_curve(5003, 2, 2, (5, 1))


def test_custom_curve_singular():
    with pytest.raises(ValueError, match="singular"):
        make_custom_curve(17, 0, 0, (0, 0))


def test_custom_curve_invalid_generator():
    with pytest.raises(ValueError, match="not on the curve"):
        make_custom_curve(17, 2, 2, (1, 1))


def test_custom_curve_composite_order():
    # Curve: y^2 = x^3 + 1 (mod 5)
    # G = (2, 2) has order 6, which is not prime.
    with pytest.raises(ValueError, match="not prime"):
        make_custom_curve(5, 0, 1, (2, 2))


# Jacobian optimization

@pytest.mark.parametrize(
    "name", ["toy-17", "toy-97", "secp256k1", "P-256"]
)
def test_jacobian_matches_affine(name):
    curve = get_curve(name)
    rng = random.Random(1234)

    for _ in range(5):
        k = rng.randrange(1, curve.n)

        # No trace: Jacobian implementation.
        fast = scalar_mult(curve, k, curve.G)

        # Trace provided: affine implementation.
        trace = []
        affine = scalar_mult(curve, k, curve.G, trace)

        assert fast == affine
        assert len(trace) > 0


def test_negative_scalar():
    curve = get_curve("toy-17")

    assert scalar_mult(curve, -3, curve.G) == point_neg(
        curve, scalar_mult(curve, 3, curve.G)
    )


# ---------------------------------------------------------------- suggest_small_curves


@pytest.mark.parametrize("p", [5, 7, 17, 97, 251, 1009, 4999])
def test_suggested_curves_are_good_teaching_curves(p):
    curves = suggest_small_curves(p)
    assert 1 <= len(curves) <= 5
    assert len({(c.a, c.b) for c in curves}) == len(curves)  # all different
    for c in curves:
        assert c.p == p and 0 <= c.a < p and 0 <= c.b < p
        assert (4 * c.a ** 3 + 27 * c.b ** 2) % p != 0          # non-singular
        assert is_on_curve(c, c.G)                               # G is on the curve
        assert scalar_mult(c, c.n, c.G) is None                  # n * G = O
        assert c.n >= 5 and is_probable_prime(c.n) and c.h == 1          # prime order, cofactor 1
        assert len(enumerate_points(c)) == c.n                   # the count is right


def test_suggestions_agree_with_make_custom_curve():
    for c in suggest_small_curves(97, limit=3):
        made = make_custom_curve(c.p, c.a, c.b, c.G)
        assert (made.n, made.h) == (c.n, c.h)


def test_suggest_limit_and_bad_p():
    assert len(suggest_small_curves(4999, limit=2)) == 2
    assert suggest_small_curves(97, limit=0) == []
    for bad in (4, 9, 5000, 4998, -7):
        with pytest.raises(ValueError):
            suggest_small_curves(bad)


def test_suggest_is_fast_for_the_largest_p():
    import time
    start = time.perf_counter()
    suggest_small_curves(4999)
    assert time.perf_counter() - start < 3  # well under a second on a laptop; generous for slow CI
