"""Convert ECDSA signatures to formats used by the GUI and saved files.

The hexadecimal form is convenient for copying values in the classroom. DER
is the standard binary form understood by common cryptography tools. Everything
here is implemented directly so the application does not depend on an external
cryptography package.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ecdsa_edu.core.types import Signature

if TYPE_CHECKING:
    from ecdsa_edu.core.curve import Curve

__all__ = ["sig_to_hex", "sig_from_hex", "sig_to_der", "sig_from_der"]


def _component_size(curve: "Curve") -> int:
    """Return the number of bytes needed to hold one scalar below ``n``."""
    n = getattr(curve, "n", None)
    if not isinstance(n, int) or isinstance(n, bool) or n <= 1:
        raise ValueError("curve order n must be an integer greater than 1")
    return (n.bit_length() + 7) // 8


def _validate_component(value: Any, n: int, name: str) -> int:
    """Check one ECDSA component and return it with a useful error message."""
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value < n:
        raise ValueError(f"signature {name} must be an integer in [1, n-1]")
    return value


def sig_to_hex(sig: "Signature", curve: "Curve") -> str:
    """Encode ``r`` and ``s`` as fixed-width ``r || s`` hexadecimal.

    Each half uses the byte length of the curve order, including leading zeroes.
    ``ValueError`` is raised when either component is outside ``[1, n-1]``.
    """
    size = _component_size(curve)
    r = _validate_component(getattr(sig, "r", None), curve.n, "r")
    s = _validate_component(getattr(sig, "s", None), curve.n, "s")
    width = size * 2  # two hex characters represent one byte
    return f"{r:0{width}x}{s:0{width}x}"


def sig_from_hex(s: str, curve: "Curve") -> "Signature":
    """Decode fixed-width ``r || s`` hexadecimal for ``curve``.

    Surrounding whitespace and an optional ``0x`` prefix are accepted. All
    malformed input, wrong lengths, and out-of-range values raise ``ValueError``.
    """
    size = _component_size(curve)
    if not isinstance(s, str):
        raise ValueError("signature hex must be text")
    encoded = s.strip()
    if encoded[:2].lower() == "0x":
        encoded = encoded[2:]
    expected_length = size * 4  # r and s, with two hex characters per byte
    if len(encoded) != expected_length:
        raise ValueError(f"signature hex must contain exactly {expected_length} hex characters")
    try:
        raw = bytes.fromhex(encoded)
    except ValueError as exc:
        raise ValueError("signature contains non-hexadecimal characters") from exc

    r = int.from_bytes(raw[:size], "big")
    component_s = int.from_bytes(raw[size:], "big")
    _validate_component(r, curve.n, "r")
    _validate_component(component_s, curve.n, "s")
    return Signature(r, component_s)


def _encode_length(length: int) -> bytes:
    """Encode a DER length using its shortest valid representation."""
    if length < 0:
        raise ValueError("DER length cannot be negative")
    if length < 0x80:
        return bytes([length])
    encoded = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(encoded)]) + encoded


def _encode_integer(value: Any, name: str) -> bytes:
    """Encode one positive integer in DER's signed INTEGER format."""
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"signature {name} must be a positive integer")
    content = value.to_bytes((value.bit_length() + 7) // 8, "big")
    # DER INTEGERs are signed. A zero byte keeps a high leading bit positive.
    if content[0] & 0x80:
        content = b"\x00" + content
    return b"\x02" + _encode_length(len(content)) + content


def sig_to_der(sig: "Signature") -> bytes:
    """Encode an ECDSA signature as a strict ASN.1 DER sequence.

    DER represents the signature as ``SEQUENCE(INTEGER(r), INTEGER(s))``.
    ``ValueError`` is raised when either component is not a positive integer.
    """
    r = _encode_integer(getattr(sig, "r", None), "r")
    s = _encode_integer(getattr(sig, "s", None), "s")
    content = r + s
    return b"\x30" + _encode_length(len(content)) + content


def _read_length(data: bytes, offset: int) -> tuple[int, int]:
    """Read one strict DER length and return ``(length, new_offset)``."""
    if offset >= len(data):
        raise ValueError("DER value ends before its length")
    first = data[offset]
    offset += 1
    if first < 0x80:
        return first, offset

    count = first & 0x7F
    if count == 0:
        raise ValueError("indefinite lengths are not valid DER")
    if count > len(data) - offset:
        raise ValueError("DER length is truncated")
    length_bytes = data[offset:offset + count]
    if length_bytes[0] == 0:
        raise ValueError("DER length has a redundant leading zero")
    length = int.from_bytes(length_bytes, "big")
    if length < 0x80:
        raise ValueError("DER length does not use its shortest form")
    return length, offset + count


def _read_integer(data: bytes, offset: int, limit: int, name: str) -> tuple[int, int]:
    """Read one minimal, positive DER INTEGER within ``limit``."""
    if offset >= limit or data[offset] != 0x02:
        raise ValueError(f"DER signature is missing INTEGER {name}")
    length, content_start = _read_length(data, offset + 1)
    content_end = content_start + length
    if length == 0 or content_end > limit:
        raise ValueError(f"DER INTEGER {name} has a bad length")

    content = data[content_start:content_end]
    if content[0] & 0x80:
        raise ValueError(f"DER INTEGER {name} must not be negative")
    if len(content) > 1 and content[0] == 0 and not (content[1] & 0x80):
        raise ValueError(f"DER INTEGER {name} has a redundant leading zero")
    value = int.from_bytes(content, "big")
    if value == 0:
        raise ValueError(f"DER INTEGER {name} must be positive")
    return value, content_end


def sig_from_der(b: bytes) -> "Signature":
    """Decode a strict ASN.1 DER ECDSA signature.

    The decoder rejects truncated values, non-minimal integers and lengths,
    negative or zero components, extra sequence fields, and trailing bytes.
    Every malformed input raises ``ValueError``.
    """
    if not isinstance(b, (bytes, bytearray, memoryview)):
        raise ValueError("DER signature must be bytes")
    data = bytes(b)
    try:
        if not data or data[0] != 0x30:
            raise ValueError("DER signature must start with a SEQUENCE")
        sequence_length, content_start = _read_length(data, 1)
        content_end = content_start + sequence_length
        if content_end != len(data):
            if content_end < len(data):
                raise ValueError("DER signature has trailing bytes")
            raise ValueError("DER SEQUENCE length exceeds the available bytes")

        r, offset = _read_integer(data, content_start, content_end, "r")
        s, offset = _read_integer(data, offset, content_end, "s")
        if offset != content_end:
            raise ValueError("DER signature contains extra fields")
        return Signature(r, s)
    except ValueError:
        raise
    except Exception as exc:  # keep malformed input errors predictable for the GUI
        raise ValueError("invalid DER signature") from exc
