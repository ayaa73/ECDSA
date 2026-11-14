"""Nonce-reuse attack on ECDSA (P4).

If the same nonce k signs two different messages, both signatures share r
and the private key d can be recovered with simple modular algebra.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ecdsa_edu.core.curve import Curve
    from ecdsa_edu.core.trace import Trace
    from ecdsa_edu.core.types import Signature


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
    The recovered d is checked by recomputing Q = d*G.

    Raises ValueError if r1 != r2 ("these signatures did not reuse k")
    or if s1 == s2.
    """
    raise NotImplementedError


def demo_nonce_reuse(curve: "Curve") -> dict[str, Any]:
    """Build everything the Attack tab needs: a fresh key, two messages signed
    with the same forced k, and the true d, Q, k, curve and both signatures.
    """
    raise NotImplementedError
