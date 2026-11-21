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


def _bits2int(data: bytes, n: int) -> int:
    """RFC 6979 bits2int: keep the leftmost bit_length(n) bits."""
    value = int.from_bytes(data, "big")
    extra_bits = len(data) * 8 - n.bit_length()
    return value >> extra_bits if extra_bits > 0 else value


def _bits2octets(e: int, n: int, length: int) -> bytes:
    """RFC 6979 bits2octets after hash_message has already done bits2int."""
    # Since e has at most bit_length(n) bits, RFC 6979 needs at most one
    # subtraction here. This is deliberately not the hash truncation step.
    reduced = e - n if e >= n else e
    return _int2octets(reduced, length)


def _trace_state(trace: "Trace | None", title: str, formula: str, K: bytes, V: bytes) -> None:
    """Record the HMAC-DRBG state in hexadecimal for the teaching trace."""
    add_step(trace, title, formula, K=K.hex(), V=V.hex())


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

    # hash_message has already performed bits2int on the message digest.
    key_bytes = _int2octets(d, rolen)
    hash_bytes = _bits2octets(e, n, rolen)

    V = b"\x01" * holen
    K = b"\x00" * holen
    _trace_state(
        trace,
        "Initialize RFC 6979 state",
        "V = 0x01 repeated; K = 0x00 repeated",
        K,
        V,
    )
    K = hmac.new(K, V + b"\x00" + key_bytes + hash_bytes, hash_name).digest()
    V = hmac.new(K, V, hash_name).digest()
    _trace_state(
        trace,
        "Update RFC 6979 state",
        "K = HMAC(K, V || 0x00 || int2octets(d) || bits2octets(e)); V = HMAC(K, V)",
        K,
        V,
    )
    K = hmac.new(K, V + b"\x01" + key_bytes + hash_bytes, hash_name).digest()
    V = hmac.new(K, V, hash_name).digest()
    _trace_state(
        trace,
        "Finish RFC 6979 setup",
        "K = HMAC(K, V || 0x01 || int2octets(d) || bits2octets(e)); V = HMAC(K, V)",
        K,
        V,
    )

    while True:
        T = b""
        while len(T) < rolen:
            V = hmac.new(K, V, hash_name).digest()
            T += V

        candidate = _bits2int(T, n)
        accepted = 1 <= candidate < n
        add_step(
            trace,
            "Check RFC 6979 candidate k",
            "accept k when 1 <= k < n",
            k=candidate,
            accepted="yes" if accepted else "no",
        )

        if accepted:
            yield candidate

        # If this candidate is unusable (or sign() later finds r or s is zero),
        # RFC 6979 updates the state before producing the next candidate.
        K = hmac.new(K, V + b"\x00", hash_name).digest()
        V = hmac.new(K, V, hash_name).digest()
        _trace_state(
            trace,
            "Advance RFC 6979 state",
            "K = HMAC(K, V || 0x00); V = HMAC(K, V)",
            K,
            V,
        )
