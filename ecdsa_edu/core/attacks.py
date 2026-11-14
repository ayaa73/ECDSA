"""Nonce-reuse attack on ECDSA (P4).

If the same nonce k signs two different messages, both signatures share r and
the private key d falls out of two lines of modular algebra:

    s1 = k^-1 (e1 + r d)        s2 = k^-1 (e2 + r d)        (mod n)
    s1 - s2 = k^-1 (e1 - e2)    =>  k = (e1 - e2) / (s1 - s2)
    s1 k = e1 + r d             =>  d = (s1 k - e1) / r

This is how the PlayStation 3 signing key was recovered in 2010. RFC 6979
(deterministic k) prevents it.
"""
from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Any

from ecdsa_edu.core.curve import scalar_mult
from ecdsa_edu.core.field import inv_mod
from ecdsa_edu.core.hashing import hash_message
from ecdsa_edu.core.trace import add_step
from ecdsa_edu.core.types import PublicKey
from ecdsa_edu.core.verify import _verify_digest

if TYPE_CHECKING:
    from ecdsa_edu.core.curve import Curve
    from ecdsa_edu.core.trace import Trace
    from ecdsa_edu.core.types import Signature


def _fmt(v: int) -> str:
    return str(v) if v.bit_length() <= 64 else hex(v)


def _solve(n: int, r: int, s1: int, s2: int, e1: int, e2: int) -> tuple[int, int] | None:
    """k and d from the two signing equations, or None if s1 == s2 (mod n)."""
    if (s1 - s2) % n == 0:
        return None
    k = ((e1 - e2) * inv_mod((s1 - s2) % n, n)) % n
    d = ((s1 * k - e1) * inv_mod(r, n)) % n
    return k, d


def recover_from_nonce_reuse(
    curve: "Curve",
    msg1: bytes,
    sig1: "Signature",
    msg2: bytes,
    sig2: "Signature",
    hash_name: str = "sha256",
    trace: "Trace | None" = None,
) -> tuple[int, int]:
    """Recover (d, k) from two signatures that reused the same nonce k.

    k = (e1 - e2) / (s1 - s2) mod n
    d = (s1*k - e1) / r mod n
    The recovered d is checked by recomputing Q = d*G and verifying both
    signatures under Q.

    Raises ValueError if r1 != r2 ("these signatures did not reuse k")
    or if s1 == s2.
    """
    n = curve.n
    r1, s1, r2, s2 = sig1.r, sig1.s, sig2.r, sig2.s

    if r1 != r2:
        raise ValueError("these signatures did not reuse k (r1 != r2)")
    r = r1
    if not 1 <= r < n:
        raise ValueError("r out of range")
    same_s = s1 % n == s2 % n
    if same_s and msg1 == msg2:
        raise ValueError("s1 == s2: the two signatures are identical, so there is nothing to solve")

    e1 = hash_message(msg1, curve, hash_name)
    e2 = hash_message(msg2, curve, hash_name)
    if same_s and e1 % n == e2 % n:
        raise ValueError("s1 == s2: the two signatures are identical, so there is nothing to solve")

    add_step(trace, "Spot the reused nonce", "r1 = r2  =>  same k, same R = k*G",
             r1=_fmt(r1), r2=_fmt(r2))
    add_step(trace, "Hash both messages", "e1 = H(m1),  e2 = H(m2)", e1=_fmt(e1), e2=_fmt(e2))

    if e1 % n == e2 % n:
        raise ValueError("e1 == e2 (mod n): the messages hash to the same value, "
                         "so the equations are not independent")

    # Normal case first. If the signer normalized one signature to "low s"
    # (s -> n - s, which corresponds to using -k), the plain formula gives a
    # wrong d, so we also try s2 -> n - s2 and keep the candidate whose key
    # actually verifies both signatures.
    candidates = [(s2, False), ((n - s2) % n, True)]
    for s2_used, flipped in candidates:
        solved = _solve(n, r, s1, s2_used, e1, e2)
        if solved is None:
            continue
        k, d = solved
        if d == 0:
            continue
        Q = scalar_mult(curve, d, curve.G)
        pub = PublicKey(Q, curve)
        if not (_verify_digest(pub, e1, sig1) and _verify_digest(pub, e2, sig2)):
            continue

        if flipped:
            add_step(trace, "Undo low-s normalization",
                     "s2 was replaced by n - s2 (same as signing with -k); use s2' = n - s2",
                     s2=_fmt(s2), s2_used=_fmt(s2_used))
        add_step(trace, "Subtract the two signing equations",
                 "s1 - s2 = k^-1 (e1 - e2)  (mod n)",
                 s1=_fmt(s1), s2=_fmt(s2_used), diff=_fmt((s1 - s2_used) % n))
        add_step(trace, "Solve for the nonce k", "k = (e1 - e2) * (s1 - s2)^-1 mod n",
                 e1_minus_e2=_fmt((e1 - e2) % n), k=_fmt(k))
        add_step(trace, "Solve for the private key d", "d = (s1*k - e1) * r^-1 mod n",
                 s1k_minus_e1=_fmt((s1 * k - e1) % n), r_inv=_fmt(inv_mod(r, n)), d=_fmt(d))
        add_step(trace, "Check: recompute Q = d*G and verify both signatures",
                 "Q = d*G;  verify(Q, m1, sig1) and verify(Q, m2, sig2)",
                 Qx=_fmt(Q[0]), Qy=_fmt(Q[1]), result="both signatures verify")
        return d, k

    if same_s:
        raise ValueError("s1 == s2: the equations cannot be solved for k")
    raise ValueError("could not recover a consistent private key: these signatures "
                     "were not made by one key with one reused nonce")


# Two messages that differ in one word, so students see how little it takes.
_DEMO_MESSAGES = (b"Pay Bob 10 USD", b"Pay Eve 10 USD")


def demo_nonce_reuse(curve: "Curve") -> dict[str, Any]:
    """Build everything the Attack tab needs: a fresh key, two messages signed
    with the same forced k, and the true d, Q, k, curve and both signatures.

    Returned keys: curve, d, Q, priv, pub, k, msg1, msg2, sig1, sig2, hash_name.
    """
    from ecdsa_edu.core.keys import generate_keypair  # P2
    from ecdsa_edu.core.sign import sign  # P3

    hash_name = "sha256"
    n = curve.n
    priv, pub = generate_keypair(curve)

    msg1, msg2 = _DEMO_MESSAGES
    e1 = hash_message(msg1, curve, hash_name)
    # On tiny curves (n = 19) the two hashes can collide mod n; tweak the
    # second message until they don't, so the attack has two real equations.
    i = 0
    while hash_message(msg2, curve, hash_name) % n == e1 % n:
        i += 1
        msg2 = _DEMO_MESSAGES[1] + b" #" + str(i).encode()

    for _ in range(200):
        k = 2 + secrets.randbelow(n - 3)  # avoid k = 1 and k = n-1: too trivial for a demo
        try:
            sig1 = sign(priv, msg1, hash_name, k=k, deterministic=False)
            sig2 = sign(priv, msg2, hash_name, k=k, deterministic=False)
        except ValueError:
            continue  # this k gave r = 0 or s = 0 on a toy curve; pick another
        if sig1.r == sig2.r and sig1.s % n != sig2.s % n:
            return {
                "curve": curve, "d": priv.d, "Q": pub.Q, "priv": priv, "pub": pub,
                "k": k, "msg1": msg1, "msg2": msg2, "sig1": sig1, "sig2": sig2,
                "hash_name": hash_name,
            }
    raise RuntimeError("could not build a nonce-reuse demo on this curve")
