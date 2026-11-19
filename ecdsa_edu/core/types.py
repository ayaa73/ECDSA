"""Shared value types for keys and signatures (owner: P2).

All three are frozen (immutable) dataclasses: once a key or signature exists it
can be passed between pages and background threads without anyone changing it
by accident. Two objects with the same content compare equal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # only needed for type hints; keeps this module importable on its own
    from .curve import Curve

__all__ = ["PrivateKey", "PublicKey", "Signature"]


@dataclass(frozen=True)
class PrivateKey:
    """The secret scalar ``d`` with 1 <= d <= n-1, on a given curve."""

    # repr=False keeps the secret out of logs, tracebacks and debug prints.
    d: int = field(repr=False)
    curve: Curve


@dataclass(frozen=True)
class PublicKey:
    """The public point ``Q = d * G`` (never the point at infinity)."""

    Q: tuple[int, int]
    curve: Curve


@dataclass(frozen=True)
class Signature:
    """An ECDSA signature: the pair ``(r, s)``, both in [1, n-1]."""

    r: int
    s: int
