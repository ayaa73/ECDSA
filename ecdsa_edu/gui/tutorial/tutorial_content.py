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
         "keys, sign and verify messages and files, watch a real attack such as nonce reuse recover a private "
         "key, explore elliptic curves visually, and read the history behind it all. Every number is computed "
         "live by the app, so you can see exactly what happens.")

HOW_TO_USE = ("Use the sidebar on the left to move between pages; it is always there. Every page also has a "
              "\"?\" button (F1) at the top with a short help text, and the curve button at the top lets you "
              "switch between tiny teaching curves and real-world curves.")


@dataclass(frozen=True)
class Stop:
    page: str  # sidebar title of the page
    what: str  # what to do there, in one short line


SUGGESTED_ORDER: tuple[Stop, ...] = (
    Stop("Start here", "this page: the big idea in 60 seconds and a 3-click demo."),
    Stop("Overview", "one picture of the whole process, from keys to verification."),
    Stop("Learn ECDSA", "a guided walkthrough of one full run with small numbers, then a quiz."),
    Stop("Keys", "make your own key pair."),
    Stop("Sign", "sign a message or a file with your private key."),
    Stop("Verify", "check a signature, then change one letter and watch it fail."),
    Stop("Curve Explorer", "see how points are added on a curve."),
    Stop("Attack Demo", "in Games & Practice: see how reusing k reveals a private key."),
    Stop("Verification Game", "solve a case: find out which suspect signed a threat."),
    Stop("Pirate Adventure", "sail to the treasure by computing a public key and signing a map."),
    Stop("Key Collision", "recover a private key yourself from two signatures that share k."),
    Stop("History", "anytime: where ECDSA came from."),
)
