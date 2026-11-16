"""Task 1–3 field tests; no external crypto library required."""
import pytest
from ecdsa_edu.core.field import inv_mod, sqrt_mod, is_probable_prime
from ecdsa_edu.core.trace import add_step
from ecdsa_edu.core.curve import scalar_mult
from ecdsa_edu.core.curves_registry import get_curve


def test_inverses_match_builtin():
    for m in (7, 17, 19, 97, 101):
        for a in range(-2 * m, 2 * m):
            try:
                expected = pow(a, -1, m)
            except ValueError:
                with pytest.raises(ValueError):
                    inv_mod(a, m)
            else:
                assert inv_mod(a, m) == expected


def test_euclidean_trace_contains_iterations():
    trace = []
    assert inv_mod(7, 19, trace) == 11
    assert sum(step.title == "Euclidean division" for step in trace) >= 2
    assert trace[-1].values["inverse"] == "11"


def test_sqrt_mod_bruteforce():
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 41, 97):
        for a in range(p):
            root = sqrt_mod(a, p)
            expected = {y * y % p for y in range(p)}
            assert (root is not None) == (a in expected)
            if root is not None:
                assert root * root % p == a


def test_prime_detection():
    for n in range(2, 500):
        expected = all(n % d for d in range(2, int(n ** 0.5) + 1))
        assert is_probable_prime(n) == expected
    assert not is_probable_prime(341550071728321)


def test_trace_large_int_hex():
    trace = []
    add_step(trace, "Large", "x", x=2**32 + 1, small=42)
    assert trace[0].values["x"] == "4294967297 (0x100000001)"
    assert trace[0].values["small"] == "42"
    add_step(None, "Ignored", "", x=1)


def test_toy17_generator_order():
    curve = get_curve("toy-17")
    assert scalar_mult(curve, 19, curve.G) is None
