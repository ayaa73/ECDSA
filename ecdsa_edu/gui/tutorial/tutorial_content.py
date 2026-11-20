"""Text for the Start here page (owner: P4). Plain data, no Qt, so it is easy to edit and test.

Written for students who have never seen elliptic curves: short sentences,
one idea per frame, no formulas in the story.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Frame", "FRAMES", "Destination", "DESTINATIONS", "ANALOGY", "SETTINGS_KEY"]

SETTINGS_KEY = "tutorial/show_at_startup"


@dataclass(frozen=True)
class Frame:
    title: str
    text: str


FRAMES: tuple[Frame, ...] = (
    Frame("1. Alice makes two keys",
          "Alice picks a secret number: her private key. From it she computes her public key, a point on an "
          "elliptic curve, and shares it with everyone. Going back from the public key to the private key is "
          "practically impossible."),
    Frame("2. She hashes her message",
          "Instead of signing a long message directly, Alice turns it into a short fingerprint with a hash "
          "function like SHA-256. Change one letter and the fingerprint changes completely."),
    Frame("3. She signs the fingerprint",
          "Using her private key and a fresh secret number k, Alice computes two numbers, r and s. "
          "Together, (r, s) is the signature. Only someone with her private key could produce them."),
    Frame("4. She sends the message and the signature",
          "Alice sends the message and (r, s) to Bob. Both are public: anyone may see them. The private key "
          "never leaves Alice."),
    Frame("5. Bob checks it with her public key",
          "Bob hashes the message himself and does a calculation with r, s and Alice's public key. If it works "
          "out, the signature is VALID: Alice signed exactly this message. If anything was changed, it is INVALID."),
)

ANALOGY = ("Think of it like a wax seal that only Alice can press, but that everyone can check against a picture "
           "of her seal she published. Unlike wax, the signature is tied to the exact message: it can't be "
           "moved onto a different one.")


@dataclass(frozen=True)
class Destination:
    label: str
    description: str
    page: str  # page title for go_to()


DESTINATIONS: tuple[Destination, ...] = (
    Destination("Learn step by step", "Walk through one full ECDSA run with small numbers.", "Learn ECDSA"),
    Destination("Make your own key", "Generate a key pair and save it to a file.", "Keys"),
    Destination("Sign a message or file", "Create a signature and see every step.", "Sign"),
    Destination("Check a signature", "Verify a signature, then tamper with the message.", "Verify"),
    Destination("See how ECDSA breaks", "Recover a private key when k is reused.", "Attack Demo"),
    Destination("Explore the curves", "See points being added on a real curve.", "Curve Explorer"),
    Destination("Read the theory", "Short pages on the math and the pitfalls.", "Theory"),
    Destination("Where ECDSA came from", "A timeline from 1976 to today.", "History"),
)
