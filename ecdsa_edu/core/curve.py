"""Short-Weierstrass elliptic-curve arithmetic."""
from dataclasses import dataclass
from .field import inv_mod, is_probable_prime, sqrt_mod
from .trace import add_step

Point = tuple[int, int] | None  # None represents infinity O.

"""Creating structure curve with its name, prime modulus, parameters a and b defining the curve,
G generator point, n order of the generator and h cofactor."""
@dataclass(frozen=True) #frozen means the object's fields can't be reassigned after creation
class Curve:
    name: str
    p: int
    a: int
    b: int
    G: tuple[int, int]
    n: int
    h: int


def is_on_curve(curve: Curve, P: Point) -> bool:
    """Check whether a point is valid and satisfies the curve equation."""
    if P is None:
        return True
    if not isinstance(P, tuple) or len(P) != 2 or not all(isinstance(v, int) for v in P):
        return False
    x, y = P
    return (0 <= x < curve.p and 0 <= y < curve.p
            and (y * y - x**3 - curve.a * x - curve.b) % curve.p == 0)


def point_neg(curve: Curve, P: Point) -> Point:
    """Negate a point: -(x, y) = (x, -y mod p), and -O = O"""
    if not is_on_curve(curve, P):
        raise ValueError("point is not on curve")
    return None if P is None else (P[0], (-P[1]) % curve.p)


def point_add(curve: Curve, P: Point, Q: Point, trace=None) -> Point:
    """Add two points, handling identity, inverses and doubling."""
    if not is_on_curve(curve, P) or not is_on_curve(curve, Q):
        raise ValueError("point is not on curve")
    if P is None: #return Q
        add_step(trace, "Identity", "O + Q = Q", Q=Q, result=Q)
        return Q
    if Q is None: #return P
        add_step(trace, "Identity", "P + O = P", P=P, result=P)
        return P
    if P == Q: #Call double_point()
        add_step(trace, "Equal points", "P + P = 2P", P=P)
        return point_double(curve, P, trace)
    x1, y1 = P
    x2, y2 = Q
    if x1 == x2:  # Two points with the same x have opposite y.
        add_step(trace, "Inverse points", "P + (-P) = O", P=P, Q=Q, result="O")
        return None
    numerator = (y2 - y1) % curve.p
    denominator = (x2 - x1) % curve.p
    lam = numerator * inv_mod(denominator, curve.p) % curve.p
    add_step(trace, "Addition slope", "lambda = (y2 - y1) / (x2 - x1) mod p",
             numerator=numerator, denominator=denominator, **{"lambda": lam})
    x3 = (lam * lam - x1 - x2) % curve.p
    add_step(trace, "Addition x-coordinate", "x3 = (lambda^2 - x1 - x2) mod p",
             x1=x1, x2=x2, **{"lambda": lam}, x3=x3)
    y3 = (lam * (x1 - x3) - y1) % curve.p
    add_step(trace, "Addition y-coordinate", "y3 = (lambda*(x1 - x3) - y1) mod p",
             x1=x1, x3=x3, y1=y1, **{"lambda": lam}, y3=y3)
    return x3, y3


def point_double(curve: Curve, P: Point, trace=None) -> Point:
    """Double a point using the tangent slope; 2O=O."""
    if not is_on_curve(curve, P):
        raise ValueError("point is not on curve")
    if P is None:
        add_step(trace, "Infinity", "2O = O", result="O")
        return None
    x1, y1 = P
    if y1 == 0:
        add_step(trace, "Vertical tangent", "2P = O when y = 0", P=P, result="O")
        return None
    numerator = (3 * x1 * x1 + curve.a) % curve.p
    denominator = (2 * y1) % curve.p
    lam = numerator * inv_mod(denominator, curve.p) % curve.p
    add_step(trace, "Doubling slope", "lambda = (3*x1^2 + a) / (2*y1) mod p",
             numerator=numerator, denominator=denominator, **{"lambda": lam})
    x3 = (lam * lam - 2 * x1) % curve.p
    add_step(trace, "Doubling x-coordinate", "x3 = (lambda^2 - 2*x1) mod p",
             x1=x1, **{"lambda": lam}, x3=x3)
    y3 = (lam * (x1 - x3) - y1) % curve.p
    add_step(trace, "Doubling y-coordinate", "y3 = (lambda*(x1 - x3) - y1) mod p",
             x1=x1, x3=x3, y1=y1, **{"lambda": lam}, y3=y3)
    return x3, y3


# Internal Jacobian representation: (X, Y, Z).
# Affine x = X/Z^2 and y = Y/Z^3 modulo p.
# Z = 0 represents the point at infinity.
_JPoint = tuple[int, int, int]


def _jacobian_double(curve: Curve, P: _JPoint) -> _JPoint:
    """Double a Jacobian point without modular inversion."""
    X, Y, Z = P
    p = curve.p

    if Z == 0 or Y == 0:
        return (0, 1, 0)

    yy = Y * Y % p
    yyyy = yy * yy % p
    s = 4 * X * yy % p
    m = (3 * X * X + curve.a * pow(Z, 4, p)) % p

    X3 = (m * m - 2 * s) % p
    Y3 = (m * (s - X3) - 8 * yyyy) % p
    Z3 = 2 * Y * Z % p

    return (X3, Y3, Z3)


def _jacobian_add_mixed(
    curve: Curve, P: _JPoint, Q: tuple[int, int]
) -> _JPoint:
    """Add an affine point Q to a Jacobian point P."""
    p = curve.p
    X1, Y1, Z1 = P
    x2, y2 = Q

    if Z1 == 0:
        return (x2, y2, 1)

    z2 = Z1 * Z1 % p
    u2 = x2 * z2 % p
    s2 = y2 * z2 * Z1 % p

    h = (u2 - X1) % p
    r = (s2 - Y1) % p

    if h == 0:
        if r == 0:
            return _jacobian_double(curve, P)
        return (0, 1, 0)

    hh = h * h % p
    hhh = h * hh % p
    v = X1 * hh % p

    X3 = (r * r - hhh - 2 * v) % p
    Y3 = (r * (v - X3) - Y1 * hhh) % p
    Z3 = Z1 * h % p

    return (X3, Y3, Z3)


def _jacobian_to_affine(curve: Curve, P: _JPoint) -> Point:
    """Convert Jacobian coordinates back to affine coordinates."""
    X, Y, Z = P

    if Z == 0:
        return None

    z_inv = inv_mod(Z, curve.p)
    z2 = z_inv * z_inv % curve.p
    z3 = z2 * z_inv % curve.p

    return (X * z2 % curve.p, Y * z3 % curve.p)


def _scalar_mult_fast(curve: Curve, k: int, P: Point) -> Point:
    """Left-to-right double-and-add using Jacobian coordinates."""
    if P is None or k == 0:
        return None

    result: _JPoint = (0, 1, 0)

    for bit in bin(k)[2:]:
        result = _jacobian_double(curve, result)

        if bit == "1":
            result = _jacobian_add_mixed(curve, result, P)

    return _jacobian_to_affine(curve, result)


def scalar_mult(curve: Curve, k: int, P: Point, trace=None, trace_detail: str = "bits") -> Point:
    """Left-to-right binary double-and-add instead of adding the point k times."""
    if not isinstance(k, int):
        raise TypeError("k must be an integer")
    if trace_detail not in ("bits", "full"):
        raise ValueError("trace_detail must be 'bits' or 'full'")
    if not is_on_curve(curve, P):
        raise ValueError("point is not on curve")
    if k < 0:
        P = point_neg(curve, P)
        k = -k
    result: Point = None

    if k == 0 or P is None:
        add_step(
            trace,
            "Scalar multiplication",
            "0*P = O or k*O = O",
            k=k,
            result="O"
        )
        return None

    # Fast path: no trace requested.
    # Keep affine operations when recording educational steps.
    if trace is None:
        return _scalar_mult_fast(curve, k, P)

    bits = bin(k)[2:]
    inner_trace = trace if trace_detail == "full" else None
    for index, bit in enumerate(bits):
        result = point_double(curve, result, inner_trace)
        doubled = result
        if bit == "1":
            result = point_add(curve, result, P, inner_trace)
        add_step(trace, "Scalar bit", "R = 2*R; if bit = 1: R = R + P",
                 bit_index=index, bit=bit, doubled=doubled,
                 added=(bit == "1"), result=result)
    return result


def enumerate_points(curve: Curve) -> list[Point]:
    """Find infinity and all points for p < 5000.
    This checks each possible x coordinate and finds its corresponding y coordinates."""
    if curve.p >= 5000:
        raise ValueError("enumeration is limited to p < 5000")
    points: list[Point] = [None]
    for x in range(curve.p):
        rhs = (x**3 + curve.a * x + curve.b) % curve.p
        y = sqrt_mod(rhs, curve.p)
        if y is not None:
            points.append((x, y))
            if y != 0:
                points.append((x, (-y) % curve.p))
    return points


def make_custom_curve(p, a, b, G) -> Curve:
    """Create a small, nonsingular curve with a prime-order generator."""
    if not isinstance(p, int) or isinstance(p, bool):
        raise ValueError("p must be an integer prime number.")

    if p >= 5000:
        raise ValueError("Choose a smaller prime: p must be below 5000.")

    if p < 5 or not is_probable_prime(p):
        raise ValueError("p must be a prime number of at least 5.")

    if (not isinstance(a, int) or isinstance(a, bool)
            or not isinstance(b, int) or isinstance(b, bool)):
        raise ValueError("a and b must be integers.")

    a, b = a % p, b % p

    if (4 * a**3 + 27 * b**2) % p == 0:
        raise ValueError(
            "This curve is singular. Choose different a and b values."
        )

    if (not isinstance(G, tuple) or len(G) != 2
            or any(type(v) is not int for v in G)):
        raise ValueError("G must be a pair of integer coordinates (x, y).")

    temporary = Curve("custom", p, a, b, G, 0, 0)

    if not is_on_curve(temporary, G):
        raise ValueError(
            "Generator G is not on the curve. Check its coordinates."
        )

    total = len(enumerate_points(temporary))

    # Find the smallest positive n such that nG = O.
    R: Point = None
    for order in range(1, total + 1):
        R = point_add(temporary, R, G)

        if R is None:
            if not is_probable_prime(order):
                raise ValueError(
                    f"G has order {order}, which is not prime. "
                    "Choose a generator with prime order."
                )

            if total % order != 0:
                raise ValueError("Invalid generator order.")

            return Curve(
                "custom", p, a, b, G, order, total // order
            )

    raise ValueError("Could not determine the generator order.")
