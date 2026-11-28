"""Plain-Python helpers for P4's pages (Verify, Attack Demo, Start here). No Qt here.

Keeping this logic out of the widgets means it can be unit-tested without a
display, and the widget files stay about layout only. Nothing here does ECDSA
math: it parses user input, formats values and words results for students.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ecdsa_edu.core.types import Signature

if TYPE_CHECKING:
    from ecdsa_edu.core.curve import Curve
    from ecdsa_edu.core.trace import Trace

__all__ = ["parse_signature_text", "tamper_text", "fmt_number", "fmt_point", "Verdict", "verdict_from_trace",
           "AttackResult", "attack_result", "signature_formats_available"]


# ---------------------------------------------------------------- formatting
def fmt_number(value: int, curve: "Curve | None" = None) -> str:
    """Decimal on toy curves (readable), hex on 256-bit curves (shorter)."""
    big = value.bit_length() > 64 if curve is None else curve.p.bit_length() > 32
    return hex(value) if big else str(value)


def fmt_point(P: Any, curve: "Curve | None" = None) -> str:
    if P is None:
        return "O (the point at infinity)"
    return f"({fmt_number(P[0], curve)}, {fmt_number(P[1], curve)})"


# ---------------------------------------------------------------- signature input
def signature_formats_available() -> bool:
    """True once P3's sig_encoding.py (hex r||s and DER) is merged AND implemented.

    The first version on the p3-sign branch only has stubs that raise
    NotImplementedError, so we probe one call instead of just importing.
    """
    try:
        from ecdsa_edu.core.sig_encoding import sig_from_der
        sig_from_der(bytes.fromhex("3006020101020101"))  # DER for r = 1, s = 1
    except NotImplementedError:
        return False
    except ImportError:
        return False
    except Exception:  # noqa: BLE001 - implemented, merely strict about this sample
        return True
    return True


_INT = r"(?:0[xX][0-9a-fA-F_]+|[0-9_]+)"
_PAIR = re.compile(rf"^\s*\(?\s*(?:r\s*=\s*)?({_INT})\s*[,;\s]\s*(?:s\s*=\s*)?({_INT})\s*\)?\s*$")


def parse_signature_text(text: str, curve: "Curve") -> Signature:
    """Read a signature typed or pasted by a student.

    Accepted, in this order:
      * "r, s" as two numbers (decimal or 0x-hex), e.g. "7, 17", "(7, 17)", "r=0x7 s=0x11";
      * hex r||s (fixed width) via P3's sig_from_hex, once sig_encoding.py exists;
      * DER (hex text starting with 30) via P3's sig_from_der, once sig_encoding.py exists.
    Raises ValueError with a message a student can act on. Range checks are left
    to verify(), which explains them in its trace.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Paste a signature first: either 'r, s' or the hex shown in the Sign tab.")
    m = _PAIR.match(text)
    if m:
        r, s = (int(g.replace("_", ""), 0) for g in m.groups())
        return Signature(r, s)

    cleaned = "".join(text.split()).replace(":", "")
    if cleaned[:2].lower() == "0x":
        cleaned = cleaned[2:]
    if not signature_formats_available():
        raise ValueError("Type the signature as two numbers 'r, s' (for example '7, 17'). "
                         "Hex and DER signatures will work once the Sign tab's encodings are added.")
    from ecdsa_edu.core.sig_encoding import sig_from_der, sig_from_hex
    if cleaned[:2] == "30":  # DER always starts with a SEQUENCE tag
        try:
            return sig_from_der(bytes.fromhex(cleaned))
        except ValueError:
            pass  # might still be r||s hex that happens to start with 30
    try:
        return sig_from_hex(cleaned, curve)
    except ValueError as exc:
        raise ValueError(f"This doesn't look like a signature ({exc}). "
                         "Use 'r, s', the r||s hex or the DER hex from the Sign tab.") from None


# ---------------------------------------------------------------- tamper
def tamper_text(text: str) -> tuple[str, str]:
    """Change exactly one character so students can watch the signature break.

    Returns (new_text, description). Letters swap case, digits go up by one,
    anything else becomes '!'; an empty message gets '!' added.
    """
    if not text:
        return "!", "added '!' to the empty message"
    i = len(text) // 2
    c = text[i]
    if c.isalpha() and c.swapcase() != c:
        new = c.swapcase()
    elif c.isdigit() and c in "0123456789":
        new = str((int(c) + 1) % 10)
    else:
        new = "!" if c != "!" else "?"
    shown = {" ": "a space", "\n": "a line break"}
    return (text[:i] + new + text[i + 1:],
            f"changed character {i + 1} from {shown.get(c, repr(c))} to {repr(new)}")


# ---------------------------------------------------------------- verdicts
@dataclass(frozen=True)
class Verdict:
    valid: bool
    headline: str   # "VALID" / "INVALID"
    reason: str     # one plain sentence


_REASONS = {
    "r out of range": "r must be between 1 and n - 1, so this cannot be a real signature.",
    "s out of range": "s must be between 1 and n - 1, so this cannot be a real signature.",
    "public key is the point at infinity": "The public key is the point at infinity, which is never a valid key.",
    "public key is not on the curve": "The public key is not a point on the selected curve. Is the right curve "
                                      "selected?",
    "public key is not in the subgroup": "The public key is not in the group generated by G.",
    "u1*G + u2*Q is the point at infinity": "The check landed on the point at infinity, so the signature is wrong.",
    "x1 mod n != r": "The point Bob computed does not match r: the message, the signature or the key is not the "
                     "one that was signed.",
    "could not read file": "The file could not be read.",
}


def verdict_from_trace(valid: bool, trace: "Trace") -> Verdict:
    """Turn verify()'s result and the last trace step into words for the banner."""
    if valid:
        return Verdict(True, "VALID", "This signature was made with the private key that belongs to this public "
                                      "key, for exactly this message.")
    last = trace[-1].title if trace else ""
    reason = last.removeprefix("INVALID: ").strip()
    for key, text in _REASONS.items():
        if reason.startswith(key):
            return Verdict(False, "INVALID", text)
    return Verdict(False, "INVALID", reason[:1].upper() + reason[1:] + "." if reason else
                   "The signature does not match.")


# ---------------------------------------------------------------- attack
@dataclass(frozen=True)
class AttackResult:
    match: bool
    recovered_d: int
    real_d: int
    recovered_k: int
    real_k: int
    headline: str


def attack_result(demo: dict, recovered: tuple[int, int]) -> AttackResult:
    """Compare what the attack found with the demo's real key and nonce."""
    d, k = recovered
    n = demo["curve"].n
    match = d == demo["d"]
    k_ok = k in (demo["k"], (n - demo["k"]) % n)  # a low-s signer effectively used -k
    headline = ("MATCH: the attacker now has the private key and can sign anything as the victim."
                if match and k_ok else "NO MATCH: the recovered key is different.")
    return AttackResult(match and k_ok, d, demo["d"], k, demo["k"], headline)
