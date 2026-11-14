"""ECDSA signature verification (P4).

Implements SEC 1 v2, section 4.1.4. Every function accepts an optional
``trace`` list and appends human-readable TraceStep entries so the GUI can
show each step to students.
"""
from __future__ import annotations

from os import PathLike
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecdsa_edu.core.trace import Trace
    from ecdsa_edu.core.types import PublicKey, Signature


def verify(
    pub: "PublicKey",
    msg: bytes,
    sig: "Signature",
    hash_name: str = "sha256",
    trace: "Trace | None" = None,
) -> bool:
    """Return True iff ``sig`` is a valid ECDSA signature on ``msg`` under ``pub``.

    Steps: check 1 <= r, s <= n-1; check Q is on the curve and not O;
    e = hash(msg); w = s^-1 mod n; u1 = e*w mod n; u2 = r*w mod n;
    (x1, y1) = u1*G + u2*Q; reject if O; valid iff x1 mod n == r.

    Never raises: any failed check returns False and records the reason
    (e.g. "r out of range", "x1 mod n != r") in the trace.
    """
    raise NotImplementedError


def verify_file(
    pub: "PublicKey",
    path: str | PathLike,
    sig: "Signature",
    hash_name: str = "sha256",
    trace: "Trace | None" = None,
) -> bool:
    """Like :func:`verify`, but hashes the file at ``path`` with P3's hash_file."""
    raise NotImplementedError


def explain_verify_math() -> str:
    """Short plain-text proof of why verification works:
    u1*G + u2*Q = (e + r*d) * s^-1 * G = k*G.
    """
    raise NotImplementedError
