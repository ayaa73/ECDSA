"""The three "boxes" shared by the whole team (owner: P2).

    PrivateKey  holds the secret number d and the curve it belongs to
    PublicKey   holds the public point Q and the curve it belongs to
    Signature   holds the two numbers r and s

@dataclass turns a short class into a ready-made box: you list the fields,
and Python writes the constructor for you, so PrivateKey(7, curve) just works.

frozen=True means the box cannot be changed after it is created. Keys are
passed between pages and background threads, so "nobody can change it by
accident" is a useful guarantee.

About the type "Curve" written in quotes: the Curve class lives in P1's file
core/curve.py. Writing the name in quotes makes it a note for the reader only,
so this file can be loaded even before P1's file is finished.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PrivateKey:
    """The secret number d (1 <= d <= n-1) on a given curve."""

    d: int
    curve: "Curve"

    def __repr__(self) -> str:
        # This text is used whenever a PrivateKey is printed or appears in an
        # error message. We leave the secret number out on purpose, so it can
        # never leak into a log or a traceback.
        return "PrivateKey(d=<hidden>, curve=" + self.curve.name + ")"


@dataclass(frozen=True)
class PublicKey:
    """The public point Q = d * G on a given curve (never the point at infinity)."""

    Q: tuple[int, int]
    curve: "Curve"


@dataclass(frozen=True)
class Signature:
    """An ECDSA signature: the two numbers r and s, both between 1 and n-1."""

    r: int
    s: int
