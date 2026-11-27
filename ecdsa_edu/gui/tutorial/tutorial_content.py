"""Text for the Start here page (owner: P4). Plain data, no Qt, so it is easy to edit and test.

Written for students who have never seen elliptic curves: short sentences,
one idea per frame, no formulas in the story.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Frame", "FRAMES", "ANALOGY", "SETTINGS_KEY", "WELCOME", "ABOUT", "HOW_TO_USE", "Stop", "SUGGESTED_ORDER"]

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


WELCOME = ("We're glad you're here! This app is a friendly, hands-on place to discover how digital "
           "signatures really work, one small step at a time.")

ABOUT = ("ECDSA (the Elliptic Curve Digital Signature Algorithm) is what lets anyone check that a message "
         "really came from its author and was not changed. It protects websites, software updates and "
         "cryptocurrencies such as Bitcoin. Here you can learn how ECDSA works step by step, generate your own "
         "keys, sign and verify messages and files.")

HOW_TO_USE = "Use the sidebar to explore. Press F1 for help; choose a curve on pages that use it."

@dataclass(frozen=True)
class Stop:
    page: str  # sidebar title of the page
    what: str  # what to do there, in one short line


SUGGESTED_ORDER: tuple[Stop, ...] = (
    Stop("Overview", "See the complete workflow."),
    Stop("Learn ECDSA", "Follow a guided example."),
    Stop("Keys", "Generate a key pair."),
    Stop("Sign", "Sign a message."),
    Stop("Verify", "Check the signature."),
    Stop("Curve Explorer", "Explore point arithmetic."),
    Stop("Attack Demo", "Explore nonce reuse."),
)
