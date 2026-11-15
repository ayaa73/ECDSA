"""Tests for P1 affine curve arithmetic and textbook toy-17 multiples."""
import random

import pytest

from ecdsa_edu.core.curve import (
    Curve, enumerate_points, is_on_curve, point_add, point_double,
    point_neg, scalar_mult,
)
from ecdsa_edu.core.curves_registry import get_curve

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
    with pytest.raises(ValueError):
        enumerate_points(get_curve("secp256k1"))
