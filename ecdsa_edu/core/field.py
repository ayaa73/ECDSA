"""Finite-field arithmetic for the educational ECDSA implementation."""
import secrets
from .trace import add_step


def inv_mod(a: int, m: int, trace=None) -> int:
    """Return a^(-1) mod m using extended Euclid; trace each division."""
    if m <= 1:
        raise ValueError("modulus must exceed 1")
    reduced = a % m
    old_r, r = m, reduced
    old_t, t = 0, 1
    while r:
        q = old_r // r
        next_r = old_r - q * r
        next_t = old_t - q * t
        add_step(trace, "Euclidean division", "old_r = q*r + remainder", old_r=old_r, q=q, r=r, remainder=next_r, coefficient=next_t)
        old_r, r = r, next_r
        old_t, t = t, next_t
    if old_r != 1:
        add_step(trace, "No inverse", "gcd(a,m) != 1", a=a, m=m, gcd=old_r)
        raise ValueError("element is not invertible")
    result = old_t % m
    add_step(trace, "Modular inverse", "a * inverse ≡ 1 (mod m)", a=a, m=m, inverse=result)
    return result


def _is_strong_probable_prime(n: int, a: int, d: int, s: int) -> bool:
    """Test one Miller–Rabin witness."""
    a %= n
    if a == 0:
        return True
    x = pow(a, d, n)
    if x == 1 or x == n - 1:
        return True
    for _ in range(s - 1):
        x = x * x % n
        if x == n - 1:
            return True
    return False


def is_probable_prime(n: int) -> bool:
    """Deterministic Miller–Rabin below 3317044064679887385961981.

    Uses the first 13 prime bases in that range and 40 random bases above.
    Above the bound this is a probabilistic test, not a primality proof.
    """
    if n < 2:
        return False
    bases = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)
    for prime in bases:
        if n % prime == 0:
            return n == prime
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    threshold = 3317044064679887385961981
    witnesses = bases if n < threshold else (secrets.randbelow(n - 3) + 2 for _ in range(40))
    return all(_is_strong_probable_prime(n, a, d, s) for a in witnesses)


def sqrt_mod(a: int, p: int) -> int | None:
    """Find a square root modulo prime p using Tonelli–Shanks, if any."""
    if p == 2:
        return a % 2
    if p < 3 or p % 2 == 0 or not is_probable_prime(p):
        raise ValueError("p must be prime")
    a %= p
    if a == 0:
        return 0
    if pow(a, (p - 1) // 2, p) != 1:
        return None
    if p % 4 == 3:
        return pow(a, (p + 1) // 4, p)
    q, s = p - 1, 0
    while q % 2 == 0:
        q //= 2
        s += 1
    z = 2
    while pow(z, (p - 1) // 2, p) != p - 1:
        z += 1
    m, c = s, pow(z, q, p)
    t, r = pow(a, q, p), pow(a, (q + 1) // 2, p)
    while t != 1:
        i, t2 = 0, t
        while t2 != 1 and i < m:
            t2 = t2 * t2 % p
            i += 1
        if i == m:
            return None
        b = pow(c, 1 << (m - i - 1), p)
        r, t, c, m = r * b % p, t * b * b % p, b * b % p, i
    return r
