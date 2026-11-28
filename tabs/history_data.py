"""Milestones for the History page (owner: P4). Plain data, no Qt, so it is easy to check and test.

Every milestone has a source. Facts and years were checked against these
sources (standards bodies, original papers, the researchers' own talks or
write-ups) in November 2026. If you add a milestone, add its source too.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Milestone", "MILESTONES", "CATEGORIES", "filter_milestones"]


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    color: str  # always shown together with the label, never color alone


CATEGORIES: dict[str, Category] = {
    "math": Category("math", "Math idea", "#9FB3F2"),
    "standard": Category("standard", "Standard", "#A7B26A"),
    "real-world": Category("real-world", "Real-world use", "#F4D35E"),
    "attack": Category("attack", "Attack or bug", "#F5A8D0"),
}


@dataclass(frozen=True)
class Milestone:
    year: int
    title: str
    category: str          # a key of CATEGORIES
    story: str             # 2-3 plain sentences
    why_it_matters: str    # the link to ECDSA / to this app
    source_title: str
    source_url: str
    page: str | None = None  # page in the app that shows this idea (named under the story)


MILESTONES: tuple[Milestone, ...] = (
    Milestone(
        1976, "Public-key cryptography is invented", "math",
        "Whitfield Diffie and Martin Hellman publish \"New Directions in Cryptography\". They describe how two "
        "people can agree on a secret over a public channel, and propose digital signatures that anyone can check.",
        "Every digital signature scheme, ECDSA included, builds on the idea of a private key you keep and a public "
        "key you share.",
        "Diffie & Hellman, New Directions in Cryptography (IEEE Trans. Inf. Theory, 1976)",
        "https://ee.stanford.edu/~hellman/publications/24.pdf", "Keys"),
    Milestone(
        1985, "Elliptic curves enter cryptography", "math",
        "Neal Koblitz and Victor Miller, working independently, propose using the group of points on an elliptic "
        "curve over a finite field for discrete-logarithm cryptography.",
        "Elliptic curves give the same security as older public-key systems with much smaller keys, which is why "
        "ECDSA keys and signatures are so short.",
        "Koblitz, Koblitz & Menezes, Elliptic curve cryptography: the serpentine course of a paradigm shift",
        "https://cacr.uwaterloo.ca/techreports/2008/cacr2008-19.pdf", "Curve Explorer"),
    Milestone(
        1992, "Vanstone proposes ECDSA", "standard",
        "When NIST asks for public comments on its first Digital Signature Standard (DSA), Scott Vanstone "
        "proposes an elliptic-curve version of the same algorithm: ECDSA.",
        "This is the algorithm our whole app teaches: sign with (r, s), verify with u1·G + u2·Q.",
        "Johnson, Menezes & Vanstone, The Elliptic Curve Digital Signature Algorithm (ECDSA)",
        "https://www.cs.miami.edu/~burt/learning/Csc609.142/ecdsa-cert.pdf", "Learn ECDSA"),
    Milestone(
        1999, "ECDSA becomes an official standard", "standard",
        "ECDSA is accepted as an ANSI standard (X9.62) in 1999, and as IEEE and NIST standards in 2000.",
        "Once standardized, banks, governments and browsers could rely on ECDSA, which is why it is used "
        "everywhere today.",
        "Johnson, Menezes & Vanstone, IJIS 1, 36–63 (2001)",
        "https://doi.org/10.1007/s102070100002", None),
    Milestone(
        2000, "SEC 1 and SEC 2 define the curves we use", "standard",
        "The Standards for Efficient Cryptography Group publishes SEC 1 (how ECDSA works) and SEC 2 (recommended "
        "curves), including secp256k1 and the 256-bit curve later known as P-256.",
        "Our verify() follows SEC 1 section 4.1.4 step by step, and two of the app's curves come from SEC 2.",
        "SECG, SEC 2: Recommended Elliptic Curve Domain Parameters, version 1.0 (2000)",
        "https://secg.org/SEC2-Ver-1.0.pdf", "Verify"),
    Milestone(
        2009, "Bitcoin signs every transaction with ECDSA", "real-world",
        "Bitcoin launches and uses ECDSA on the curve secp256k1 to prove that only the owner of a private key can "
        "spend its coins.",
        "secp256k1 is one of the curves in this app: the keys you generate on it have the same form as Bitcoin keys.",
        "Bitcoin Wiki, Secp256k1",
        "https://en.bitcoin.it/wiki/Secp256k1", "Keys"),
    Milestone(
        2010, "PlayStation 3 key recovered from reused k", "attack",
        "At the 27th Chaos Communication Congress, the fail0verflow team shows that Sony signed PS3 software with "
        "the same nonce k every time. From two signatures they computed Sony's private signing key.",
        "This is exactly the attack in our Attack Demo page: same k, same r, private key recovered.",
        "fail0verflow, Console Hacking 2010: PS3 Epic Fail (27C3 slides)",
        "https://fahrplan.events.ccc.de/congress/2010/Fahrplan/attachments/1780_27c3_console_hacking_2010.pdf",
        "Attack Demo"),
    Milestone(
        2013, "Weak randomness puts Android Bitcoin wallets at risk", "attack",
        "Bitcoin.org warns that a weakness in Android's secure random-number generator makes the Bitcoin wallets "
        "created on Android vulnerable to theft, and asks users to move their coins to new keys.",
        "ECDSA needs a fresh, unpredictable k for every signature. If weak randomness ever repeats k, the "
        "private key can be computed, as in the Attack Demo.",
        "Bitcoin.org, Android Security Vulnerability (11 August 2013)",
        "https://bitcoin.org/en/alert/2013-08-11-android", "Attack Demo"),
    Milestone(
        2013, "RFC 6979: deterministic nonces", "standard",
        "Thomas Pornin publishes RFC 6979, which derives k from the private key and the message hash. The same "
        "message always gets the same k, and different messages get unrelated ones, with no random generator.",
        "Our Sign page uses RFC 6979 by default, which rules out the PS3 and Android mistakes.",
        "RFC 6979, Deterministic Usage of DSA and ECDSA (August 2013)",
        "https://www.rfc-editor.org/rfc/rfc6979", "Sign"),
    Milestone(
        2022, "\"Psychic signatures\" in Java", "attack",
        "Neil Madden finds that Java 15 to 18 accepted the signature r = 0, s = 0 for any message and any key, "
        "because the check 1 <= r, s <= n-1 was missing (CVE-2022-21449).",
        "This is why our verify() checks the range of r and s first, and the Verify page explains the rejection.",
        "Neil Madden, CVE-2022-21449: Psychic Signatures in Java",
        "https://neilmadden.blog/2022/04/19/psychic-signatures-in-java/", "Verify"),
    Milestone(
        2023, "FIPS 186-5: today's signature standard", "standard",
        "NIST publishes FIPS 186-5 on 3 February 2023. It keeps ECDSA and RSA, adds EdDSA, and keeps the old DSA "
        "only for verifying existing signatures.",
        "ECDSA is still a current, approved standard, and the one our app follows.",
        "NIST, FIPS 186-5 Digital Signature Standard",
        "https://csrc.nist.gov/pubs/fips/186-5/final", "Learn ECDSA"),
    Milestone(
        2024, "A signature standard for the quantum era", "standard",
        "NIST publishes FIPS 204 (ML-DSA) on 13 August 2024, a lattice-based signature scheme designed to stay "
        "secure against large quantum computers.",
        "A large enough quantum computer running Shor's algorithm could recover ECDSA private keys, so new systems "
        "are starting to plan the move to post-quantum signatures.",
        "NIST, FIPS 204 Module-Lattice-Based Digital Signature Standard",
        "https://csrc.nist.gov/pubs/fips/204/final", None),
)


def filter_milestones(categories: set[str] | frozenset[str]) -> list[Milestone]:
    """Milestones whose category is in `categories`, oldest first."""
    return [m for m in MILESTONES if m.category in categories]
