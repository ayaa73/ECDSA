"""Shared value types for keys and signatures (owner: P2).

All three are frozen (immutable) dataclasses: once a key or signature exists it
can be passed between pages and background threads without anyone changing it
by accident. Two objects with the same content compare equal.
"""
from __future__ import annotations

from dataclasses import dataclass, field # using dataclasses because they provide us with constructors, printing and equality check
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # only needed for type hints; keeps this module importable on its own
    from .curve import Curve

__all__ = ["PrivateKey", "PublicKey", "Signature"]

# the classes we're creating below only store values, they don't check

@dataclass(frozen=True)
class PrivateKey:
    """The secret scalar ``d`` with 1 <= d <= n-1, on a given curve."""

    # repr=False keeps the secret out of logs, tracebacks and debug prints.
    d: int = field(repr=False)
    curve: Curve # which curve this key belongs to 


@dataclass(frozen=True)
class PublicKey:
    """public key is a point on the curve q= d*G s.t d is the private key and G is a base point on curve"""

    Q: tuple[int, int] # public key is a tuple because it's a point on the curve; it has x and y coordinates 
    curve: Curve # associated with a given curve
    # Q cannot be O --> checked in keys.py


@dataclass(frozen=True) 
class Signature:
    """An ECDSA signature is the pair (r,s) which both belong to the [1,n-1] interval."""
    r: int
    s: int
