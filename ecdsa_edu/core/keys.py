"""Making ECDSA keys (owner: P2).

A key pair on a curve with base point G of order n is:

    private key d : a secret whole number, chosen at random from 1 to n-1
    public key  Q : the curve point Q = d * G  (G added to itself d times)

Going from d to Q is one scalar multiplication, which is fast.
Going back from Q to d is the "discrete logarithm problem", which nobody knows
how to solve quickly. That is what keeps the private key safe.

Every function takes an optional `trace` list. If a list is given, the
function adds human-readable steps to it, so the screen can show the math.

The only math functions used from P1 are scalar_mult and is_on_curve.
"""
import secrets

from .curve import Curve, Point, is_on_curve, scalar_mult
from .trace import add_step
from .types import PrivateKey, PublicKey


def _number_to_text(value: int, curve: Curve) -> str:
    """Write a number for the trace: decimal on toy curves, hexadecimal on real ones."""
    curve_is_small = curve.p.bit_length() <= 32
    if curve_is_small:
        return str(value)  # for example "7"
    else:
        return hex(value)  # for example "0x1f3a..."


def generate_keypair(curve: Curve, trace=None) -> tuple[PrivateKey, PublicKey]:
    """Create a new random key pair on `curve`. Returns (private key, public key)."""
    n = curve.n
    if n < 2:
        raise ValueError("the base point order n must be at least 2")

    # Step 1: pick the private key d at random from 1 to n-1.
    #
    # secrets.randbelow(k) returns a random whole number from 0 to k-1, and
    # every value is equally likely. With k = n-1 we get 0 .. n-2.
    # Adding 1 shifts that to 1 .. n-1, which is exactly the allowed range.
    #
    # We use the `secrets` module (the operating system's secure random
    # generator) and never the `random` module, which can be predicted.
    random_number = secrets.randbelow(n - 1)
    d = random_number + 1

    add_step(
        trace,
        "Choose the private key d",
        "d = random integer, 1 <= d <= n - 1  (from a cryptographic RNG)",
        n=_number_to_text(n, curve),
        d=_number_to_text(d, curve),
    )

    # Step 2: put d in its box and compute the matching public key.
    private_key = PrivateKey(d, curve)
    public_key = public_from_private(private_key, trace)
    return private_key, public_key


def public_from_private(priv: PrivateKey, trace=None) -> PublicKey:
    """Compute the public key Q = d * G that belongs to the private key `priv`.

    Raises ValueError if d is not a whole number from 1 to n-1.
    """
    curve = priv.curve
    d = priv.d

    # Check 1: d must be a whole number.
    # (In Python, True and False also count as integers, so we refuse them by name.)
    if isinstance(d, bool) or not isinstance(d, int):
        raise ValueError("the private key d must be an integer")

    # Check 2: d must be in the range 1 .. n-1.
    if d < 1 or d > curve.n - 1:
        raise ValueError(
            "the private key d must satisfy 1 <= d <= n - 1 (n = " + _number_to_text(curve.n, curve) + ")"
        )

    # Record where we start: the base point G.
    gx = curve.G[0]
    gy = curve.G[1]
    add_step(
        trace,
        "Start from the base point G",
        "Q = d * G  means  G + G + ... + G  (d times), computed with double-and-add",
        d=_number_to_text(d, curve),
        Gx=_number_to_text(gx, curve),
        Gy=_number_to_text(gy, curve),
    )

    # The actual computation is done by P1's scalar_mult (double-and-add).
    # Because we pass `trace`, it adds one step for every doubling and addition.
    Q = scalar_mult(curve, d, curve.G, trace)

    # None means "the point at infinity". With a correct curve and a d in
    # range this cannot happen; the check protects against a wrong value of n.
    if Q is None:
        raise ValueError("d * G is the point at infinity - check the curve's order n")

    add_step(
        trace,
        "Public key Q = d * G",
        "Q = (Qx, Qy) is published; d stays secret",
        Qx=_number_to_text(Q[0], curve),
        Qy=_number_to_text(Q[1], curve),
    )
    return PublicKey(Q, curve)


def validate_public_point(curve: Curve, Q: Point) -> None:
    """Check that Q can be used as a public key on `curve`.

    Returns nothing when Q is fine. Raises ValueError with a clear message when
    it is not. A public key from a file or from another person must always go
    through these four checks before it is used: skipping them would let an
    attacker hand us a point from a different, weaker curve.
    """
    # Check 1: the point at infinity (None) is not a public key.
    if Q is None:
        raise ValueError("the point at infinity is not a valid public key")

    # Check 2: both coordinates must be from 0 to p-1.
    x = Q[0]
    y = Q[1]
    x_in_range = 0 <= x < curve.p
    y_in_range = 0 <= y < curve.p
    if not x_in_range or not y_in_range:
        raise ValueError("public key coordinates must be in the range [0, p - 1]")

    # Check 3: the point must satisfy the curve equation.
    if not is_on_curve(curve, Q):
        raise ValueError("this point is not on the curve")

    # Check 4: n * Q must be the point at infinity. That proves Q is one of
    # the multiples of G. (It is automatic when the cofactor h is 1, but
    # custom curves can have other points, so we always check.)
    n_times_q = scalar_mult(curve, curve.n, Q)
    if n_times_q is not None:
        raise ValueError("this point is not in the subgroup generated by G (n * Q != O)")
