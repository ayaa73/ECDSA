"""Text for the Start here page (owner: P4). Plain data, no Qt, so it is easy to edit and test.

Written for students who have never seen elliptic curves: short sentences,
one idea per frame, no formulas in the story.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Frame", "FRAMES", "STEP_CHIPS", "ANALOGY", "SETTINGS_KEY", "WELCOME", "ABOUT", "HOW_TO_USE", "FACTS",
           "Card", "Track", "TRACKS", "Stop", "SUGGESTED_ORDER"]

SETTINGS_KEY = "tutorial/show_at_startup"


@dataclass(frozen=True)
class Frame:
    title: str
    text: str


FRAMES: tuple[Frame, ...] = (
    Frame("1. Alice makes two keys",
          "A secret number is her private key. Her public key comes from it, and she shares that with everyone."),
    Frame("2. She hashes her message",
          "A hash turns the message into a short fingerprint. Change one letter and it looks completely different."),
    Frame("3. She signs the fingerprint",
          "Her private key and a fresh secret k make two numbers, r and s. Together they are the signature."),
    Frame("4. She sends it to Bob",
          "The message and (r, s) travel in the open. The private key never leaves Alice."),
    Frame("5. Bob checks it",
          "Bob uses Alice's public key. It works out: VALID. Anything was changed: INVALID."),
)

STEP_CHIPS: tuple[str, ...] = ("Keys", "Hash", "Sign", "Send", "Verify")

ANALOGY = "Like a wax seal only Alice can press, but anyone can check it, and it only fits this exact message."

WELCOME = "Learn how digital signatures work by playing with them."

ABOUT = ("ECDSA lets anyone check that a message really came from its author and was not changed. It protects "
         "websites, software updates and cryptocurrencies such as Bitcoin.")

HOW_TO_USE = ("Use the sidebar on the left to move between pages; it is always there. Every page also has a "
              "\"?\" button (F1) at the top with a short help text, and the curve button at the top lets you "
              "switch between tiny teaching curves and real-world curves.")

FACTS: tuple[str, ...] = (
    "Bitcoin and Ethereum use ECDSA to prove that you own your coins.",
    "Reusing the secret number k just once can leak a private key. Game consoles have been hacked this way.",
    "A 256-bit elliptic curve key is about as strong as a 3000-bit RSA key.",
    "Change one letter of a message and its hash changes completely. Try it in the live demo!",
    "Many HTTPS websites prove who they are with ECDSA certificates.",
    "The practice curve in this app uses tiny numbers, so you can check every step by hand.",
)


@dataclass(frozen=True)
class Card:
    page: str    # sidebar title of the page this card opens
    title: str
    blurb: str   # one short line
    badge: str = ""


@dataclass(frozen=True)
class Track:
    name: str
    tagline: str
    cards: tuple[Card, ...]


TRACKS: tuple[Track, ...] = (
    Track("LEARN IT", "Understand the idea first", (
        Card("Learn ECDSA", "Learn ECDSA", "Guided walkthrough, then a quiz", "START"),
        Card("Overview", "Overview", "The whole process on one map"),
        Card("History", "History", "Where ECDSA came from"),
    )),
    Track("TRY IT", "Use the real thing", (
        Card("Keys", "Keys", "Make your own key pair"),
        Card("Sign", "Sign", "Seal a message or file"),
        Card("Verify", "Verify", "Spot a tampered message"),
        Card("Curve Explorer", "Curve Explorer", "Add points on a curve"),
    )),
    Track("PLAY IT", "Games and challenges", (
        Card("Pirate Adventure", "Pirate Adventure", "Sail, sign, find treasure"),
        Card("Verification Game", "Detective Game", "Catch who signed the threat"),
        Card("Attack Demo", "Attack Demo", "Steal a key from one mistake"),
        Card("Key Collision", "Key Collision", "Recover a key yourself"),
    )),
)


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
