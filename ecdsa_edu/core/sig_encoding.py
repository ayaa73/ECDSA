"""Convert ECDSA signatures to formats used by the GUI and saved files.

The Sign and Verify tabs use fixed-width hexadecimal for readable classroom
examples and DER for compatibility with standard cryptography tools. The
implementations belong to P3.3; these stubs publish the agreed interfaces now.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecdsa_edu.core.curve import Curve
    from ecdsa_edu.core.types import Signature

__all__ = ["sig_to_hex", "sig_from_hex", "sig_to_der", "sig_from_der"]


def sig_to_hex(sig: "Signature", curve: "Curve") -> str:
    """Encode ``r`` and ``s`` as fixed-width hexadecimal for ``curve``."""
    raise NotImplementedError("signature hexadecimal encoding is implemented in P3.3")


def sig_from_hex(s: str, curve: "Curve") -> "Signature":
    """Decode a fixed-width ``r || s`` hexadecimal string for ``curve``."""
    raise NotImplementedError("signature hexadecimal decoding is implemented in P3.3")


def sig_to_der(sig: "Signature") -> bytes:
    """Encode an ECDSA signature as a strict ASN.1 DER sequence."""
    raise NotImplementedError("DER signature encoding is implemented in P3.3")


def sig_from_der(b: bytes) -> "Signature":
    """Decode a strict ASN.1 DER ECDSA signature."""
    raise NotImplementedError("DER signature decoding is implemented in P3.3")
