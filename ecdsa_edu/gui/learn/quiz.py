"""Quiz content for Learn step 7 (P4). Pure data, no Qt, so it is easy to test and edit."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Choice:
    text: str
    correct: bool
    feedback: str  # shown after the student picks this answer


@dataclass(frozen=True)
class Question:
    prompt: str
    choices: tuple[Choice, ...]

    @property
    def answer_index(self) -> int:
        return next(i for i, c in enumerate(self.choices) if c.correct)


QUIZ: tuple[Question, ...] = (
    Question(
        "Alice signs two different messages with the same nonce k. What can an attacker do?",
        (
            Choice("Nothing: the private key d never appears in a signature.", False,
                   "d does appear: s = k^-1 (e + r*d). With two equations that share k, "
                   "the attacker can eliminate k and solve for d."),
            Choice("Recover k and then Alice's private key d from the two signatures.", True,
                   "Right. r1 = r2 reveals the reuse, k = (e1 - e2) / (s1 - s2) mod n, then "
                   "d = (s1*k - e1) / r mod n. This is how Sony's PS3 key was recovered."),
            Choice("Only forge signatures on those same two messages.", False,
                   "It's much worse: the attacker gets d itself and can sign any message."),
            Choice("Only learn that the two messages were signed by the same person.", False,
                   "The shared r does reveal that, but the real damage is that d can be computed."),
        ),
    ),
    Question(
        "During verification Bob computes X = u1*G + u2*Q. Why does X equal the signer's point R?",
        (
            Choice("Because Bob secretly learns k from the signature.", False,
                   "Bob never learns k. He reaches k*G without knowing k."),
            Choice("Because u1*G + u2*Q = w*(e + r*d)*G, and w*(e + r*d) = k mod n.", True,
                   "Right. Q = d*G lets Bob multiply by d 'inside a point' without knowing d, "
                   "and the signing equation makes w*(e + r*d) equal to k."),
            Choice("Because Bob computes d from Q first.", False,
                   "Computing d from Q = d*G is the elliptic-curve discrete log problem, "
                   "which is infeasible on real curves."),
            Choice("It doesn't: Bob only checks that X is on the curve.", False,
                   "Every sum of curve points is on the curve, so that check would accept anything. "
                   "Bob checks that the x-coordinate of X mod n equals r."),
        ),
    ),
    Question(
        "A verifier skips the check 1 <= r, s <= n-1. What can go wrong?",
        (
            Choice("Nothing, the math rejects bad values anyway.", False,
                   "Not always. With s = 0 there is no s^-1, and Java 15-18 accepted r = s = 0 "
                   "for every message (CVE-2022-21449)."),
            Choice("Verification just becomes a little slower.", False,
                   "Speed isn't the issue. The check is what stops degenerate signatures like "
                   "r = s = 0 from being accepted."),
            Choice("Forged signatures such as r = 0, s = 0 may be accepted for any message.", True,
                   "Right. That exact bug, the 'psychic signatures' flaw in Java (2022), let "
                   "anyone 'sign' anything with r = s = 0."),
            Choice("Valid signatures start failing.", False,
                   "Valid signatures always have 1 <= r, s <= n-1, so the check never rejects "
                   "them. It only blocks invalid ones."),
        ),
    ),
)


def check_answer(question: Question, choice_index: int) -> tuple[bool, str]:
    """(is_correct, feedback) for the given choice. Raises IndexError for a bad index."""
    choice = question.choices[choice_index]
    return choice.correct, choice.feedback
