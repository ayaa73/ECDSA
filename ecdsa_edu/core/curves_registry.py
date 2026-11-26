"""Defines the curves that we can select in the application"""
from .curve import Curve
from .field import is_probable_prime

"""Our four curves are: toy-17 small curve for learning and testing
                        toy-97 small curve for demonstration
                        secp256k1 standard curve used in Bitcoin
                        P-256 standard curve used in real-world cryptographic systems."""
CURVES: dict[str, Curve] = {
    "toy-17": Curve("toy-17", 17, 2, 2, (5, 1), 19, 1),
    # Found by searching a, b over F_97, rejecting singular curves,
    # counting all points, and selecting a curve with prime group order.
    # y^2 = x^3 + 5 (mod 97) has 79 points including infinity.
    # Since 79 is prime, every non-infinity point has order 79.
    "toy-97": Curve("toy-97", 97, 0, 5, (1, 43), 79, 1),
    # secp256k1 domain parameters.
    "secp256k1": Curve(
        "secp256k1", 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F,
        0, 7,
        (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
         0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8),
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141, 1),
    # NIST P-256 domain parameters (also specified in SEC 2).
    "P-256": Curve(
        "P-256", 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF,
        0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFC,
        0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B,
        (0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
         0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5),
        0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551, 1),
}


def get_curve(name: str) -> Curve:
    """Return a registered elliptic curve by name.
    name: Name of the curve (e.g., "toy-17", "secp256k1").

    Returns:The Curve object associated with the given name.

    Raises: KeyError: If the curve name is not registered.
    """
    return CURVES[name]


MIN_SUGGEST_P, MAX_SUGGEST_P = 5, 5000  # p is enumerated point by point, so it must stay small


def suggest_small_curves(p: int, limit: int = 5) -> list[Curve]:
    """Good teaching curves over F_p: up to ``limit`` curves y^2 = x^3 + ax + b (mod p).

    Every curve returned is non-singular (4a^3 + 27b^2 != 0 mod p) and has a
    PRIME number of points n >= 5 (the point at infinity included). In a group
    of prime order every point except O generates the whole group, so any
    point can be G and the cofactor is h = 1. G is the point with the smallest x.

    Counting: for each x the curve has as many points as y^2 = x^3 + ax + b has
    square roots (0, 1 or 2). The square roots of every residue are tabulated
    once, so each candidate (a, b) costs one pass over x and no modular
    square roots. Candidates are tried in order a = 0, 1, ...; b = 1, 2, ...
    and the search stops as soon as ``limit`` curves are found.
    """
    if not isinstance(p, int) or isinstance(p, bool) or not MIN_SUGGEST_P <= p < MAX_SUGGEST_P:
        raise ValueError(f"p must be a prime from {MIN_SUGGEST_P} to {MAX_SUGGEST_P - 1}")
    if not is_probable_prime(p):
        raise ValueError(f"{p} is not a prime number")
    if limit < 1:
        return []

    roots: dict[int, int] = {}  # residue -> its smallest square root
    for y in range(p):
        roots.setdefault(y * y % p, y)
    root_count = [0] * p  # how many y have y^2 = r
    for r in roots:
        root_count[r] = 1 if r == 0 else 2
    cubes = [x * x * x % p for x in range(p)]
    xs = range(p)

    found: list[Curve] = []
    for a in range(p):
        for b in range(p):
            if (4 * a ** 3 + 27 * b ** 2) % p == 0:
                continue  # singular: not an elliptic curve
            n = 1 + sum(root_count[(cubes[x] + a * x + b) % p] for x in xs)
            if n < 5 or not is_probable_prime(n):
                continue
            gx = next(x for x in xs if (cubes[x] + a * x + b) % p in roots)
            G = (gx, roots[(cubes[gx] + a * gx + b) % p])
            found.append(Curve(f"suggested-p{p}-a{a}-b{b}", p, a, b, G, n, 1))
            if len(found) >= limit:
                return found
    return found
