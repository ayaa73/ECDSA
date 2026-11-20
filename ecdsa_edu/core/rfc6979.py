"""RFC 6979 deterministic nonce generation for ECDSA (P3).

The nonce ``k`` must never repeat for different messages.  RFC 6979 derives it
from the private key and message hash with HMAC, avoiding dependence on fresh
randomness while still producing a different nonce for a different message.
"""
from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterator
from typing import TYPE_CHECKING

from ecdsa_edu.core.hashing import HASHES
from ecdsa_edu.core.trace import add_step

if TYPE_CHECKING:
    from ecdsa_edu.core.trace import Trace

__all__ = ["generate_k_candidates"]


def _int2octets(value: int, length: int) -> bytes:
    """RFC 6979 int2octets: a fixed-width, big-endian integer encoding."""
    return value.to_bytes(length, "big")


def generate_k_candidates(
    d: int,
    e: int,
    n: int,
    hash_name: str = "sha256",
    trace: "Trace | None" = None,
) -> Iterator[int]:
    """Yield deterministic nonce candidates following RFC 6979 section 3.2.

    ``d`` is the private scalar, ``e`` is the already-truncated message hash,
    and ``n`` is the order of the generator.  A generator is used because the
    very rare ECDSA cases r=0 or s=0 require trying the next candidate.
    """
    if not isinstance(n, int) or isinstance(n, bool) or n <= 1:
        raise ValueError("n must be an integer greater than 1")
    if not isinstance(d, int) or isinstance(d, bool) or not 1 <= d < n:
        raise ValueError("the private key d must satisfy 1 <= d < n")
    if not isinstance(e, int) or isinstance(e, bool) or e < 0:
        raise ValueError("the message hash integer e must be non-negative")
    if not isinstance(hash_name, str) or hash_name.lower() not in HASHES:
        raise ValueError(f"unsupported hash algorithm: {hash_name!r}")

    hash_name = hash_name.lower()
    qlen = n.bit_length()
    rolen = (qlen + 7) // 8
    holen = hashlib.new(hash_name).digest_size

    # hash_message has already done bits2int.  Reducing that value and writing
    # it at rolen bytes is exactly RFC 6979's bits2octets operation.
    key_bytes = _int2octets(d, rolen)
    hash_bytes = _int2octets(e % n, rolen)

    V = b"\x01" * holen
    K = b"\x00" * holen
    K = hmac.new(K, V + b"\x00" + key_bytes + hash_bytes, hash_name).digest()
    V = hmac.new(K, V, hash_name).digest()
    K = hmac.new(K, V + b"\x01" + key_bytes + hash_bytes, hash_name).digest()
    V = hmac.new(K, V, hash_name).digest()

    add_step(
        trace,
        "Initialize RFC 6979",
        "K and V are initialized with HMAC(private key d, message hash e)",
        hash=hash_name,
        order_bits=qlen,
    )

    while True:
        T = b""
        while len(T) < rolen:
            V = hmac.new(K, V, hash_name).digest()
            T += V

        candidate = int.from_bytes(T, "big")
        extra_bits = len(T) * 8 - qlen
        if extra_bits > 0:
            candidate >>= extra_bits

        if 1 <= candidate < n:
            add_step(
                trace,
                "Generate deterministic nonce k",
                "RFC 6979 candidate satisfies 1 <= k < n",
                k=candidate,
            )
            yield candidate

        # If this candidate is unusable (or sign() later finds r or s is zero),
        # RFC 6979 updates the state before producing the next candidate.
        K = hmac.new(K, V + b"\x00", hash_name).digest()
        V = hmac.new(K, V, hash_name).digest()
