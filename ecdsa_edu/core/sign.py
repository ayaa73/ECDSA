"""ECDSA signature generation (P3).

This module contains the signing math only.  The GUI supplies a message and a
private key, then displays the TraceStep objects produced here.
"""
from __future__ import annotations

import secrets
from collections.abc import Iterator
from os import PathLike
from typing import TYPE_CHECKING

from ecdsa_edu.core.curve import scalar_mult
from ecdsa_edu.core.field import inv_mod
from ecdsa_edu.core.hashing import hash_file, hash_message
from ecdsa_edu.core.rfc6979 import generate_k_candidates
from ecdsa_edu.core.trace import add_step
from ecdsa_edu.core.types import Signature

if TYPE_CHECKING:
    from ecdsa_edu.core.trace import Trace
    from ecdsa_edu.core.types import PrivateKey

__all__ = ["sign", "sign_file", "normalize_low_s"]


def _validate_private_key(priv: "PrivateKey") -> None:
    """Check the scalar here because the shared dataclass is intentionally simple."""
    d, n = priv.d, priv.curve.n
    if not isinstance(d, int) or isinstance(d, bool) or not 1 <= d < n:
        raise ValueError("the private key d must satisfy 1 <= d < n")


def _random_k_candidates(n: int, trace: "Trace | None") -> Iterator[int]:
    """Yield independent random nonces from the operating system CSPRNG."""
    while True:
        k = secrets.randbelow(n - 1) + 1
        add_step(trace, "Choose a random nonce k", "k is random and 1 <= k < n", k=k)
        yield k


def _sign_digest(
    priv: "PrivateKey",
    e: int,
    hash_name: str,
    k: int | None,
    deterministic: bool,
    trace: "Trace | None",
) -> Signature:
    """Apply the ECDSA equations after hashing has produced integer e."""
    _validate_private_key(priv)
    curve, d, n = priv.curve, priv.d, priv.curve.n

    if k is not None:
        if not isinstance(k, int) or isinstance(k, bool) or not 1 <= k < n:
            raise ValueError("the nonce k must satisfy 1 <= k < n")
        add_step(trace, "Use the supplied nonce k", "manual k with 1 <= k < n", k=k)
        candidates: Iterator[int] = iter((k,))
        manual_k = True
    elif deterministic:
        candidates = generate_k_candidates(d, e, n, hash_name, trace)
        manual_k = False
    else:
        candidates = _random_k_candidates(n, trace)
        manual_k = False

    for nonce in candidates:
        R = scalar_mult(curve, nonce, curve.G)
        # Since G has order n and 1 <= k < n, R should never be infinity.
        # Keeping the check makes failures on an invalid custom curve clearer.
        if R is None:
            if manual_k:
                raise ValueError("the supplied nonce produced the point at infinity")
            continue

        r = R[0] % n
        add_step(
            trace,
            "Compute the point R = kG",
            "R = kG and r = x(R) mod n",
            k=nonce,
            Rx=R[0],
            Ry=R[1],
            r=r,
        )
        if r == 0:
            if manual_k:
                raise ValueError("the supplied nonce produced r = 0")
            add_step(trace, "Reject this nonce", "r = 0, so try another k", k=nonce)
            continue

        k_inverse = inv_mod(nonce, n)
        s = (k_inverse * (e + r * d)) % n
        add_step(
            trace,
            "Compute the second signature value s",
            "s = k^-1 * (e + r*d) mod n",
            e=e,
            r=r,
            k_inverse=k_inverse,
            s=s,
        )
        if s == 0:
            if manual_k:
                raise ValueError("the supplied nonce produced s = 0")
            add_step(trace, "Reject this nonce", "s = 0, so try another k", k=nonce)
            continue

        add_step(trace, "ECDSA signature is ready", "signature = (r, s)", r=r, s=s)
        return Signature(r, s)

    # The one-value iterator for a manual k is the only finite candidate source.
    raise ValueError("the supplied nonce could not produce a valid signature")


def sign(
    priv: "PrivateKey",
    msg: bytes,
    hash_name: str = "sha256",
    k: int | None = None,
    deterministic: bool = True,
    trace: "Trace | None" = None,
) -> Signature:
    """Sign a byte message and return its ``Signature(r, s)``.

    By default RFC 6979 chooses ``k`` deterministically.  A caller may set
    ``deterministic=False`` for a fresh random nonce, or supply ``k`` directly
    for a classroom example and the nonce-reuse demonstration.
    """
    if not isinstance(msg, bytes):
        raise TypeError("msg must be bytes")
    e = hash_message(msg, priv.curve, hash_name, trace)
    return _sign_digest(priv, e, hash_name, k, deterministic, trace)


def sign_file(
    priv: "PrivateKey",
    path: str | PathLike,
    hash_name: str = "sha256",
    deterministic: bool = True,
    trace: "Trace | None" = None,
) -> Signature:
    """Sign a file without reading the complete file into memory."""
    e = hash_file(path, priv.curve, hash_name, trace)
    return _sign_digest(priv, e, hash_name, None, deterministic, trace)


def normalize_low_s(sig: Signature, n: int) -> Signature:
    """Return the equivalent signature whose ``s`` value is at most ``n/2``.

    ECDSA accepts both ``s`` and ``n-s``. This signature malleability lets one
    valid signature have two encodings, so low-s normalization gives encoders
    one predictable representation. Signing does not apply it by default.
    """
    if not isinstance(n, int) or isinstance(n, bool) or n <= 1:
        raise ValueError("n must be an integer greater than 1")
    if not 1 <= sig.r < n or not 1 <= sig.s < n:
        raise ValueError("signature values must satisfy 1 <= r, s < n")
    return Signature(sig.r, min(sig.s, n - sig.s))
