"""Hash messages and files before ECDSA signs or verifies them (P3).

ECDSA does not use the raw message directly.  It hashes the message and turns
the digest into an integer ``e``.  If the digest is longer than the bit length
of the curve order ``n``, SEC 1 says to keep the *leftmost* bits.
"""
from __future__ import annotations

import hashlib
from os import PathLike
from typing import TYPE_CHECKING

from ecdsa_edu.core.trace import add_step

if TYPE_CHECKING:
    from ecdsa_edu.core.curve import Curve
    from ecdsa_edu.core.trace import Trace

__all__ = ["HASHES", "hash_message", "hash_file"]


# SHA-1 is included because it is useful when comparing old examples, but it
# should not be chosen for a new real-world signature system.
HASHES = ["sha256", "sha384", "sha512", "sha1"]
_FILE_CHUNK_SIZE = 64 * 1024


def _new_hasher(hash_name: str):
    """Return a supported hashlib object, with one clear error for the GUI."""
    if not isinstance(hash_name, str) or hash_name.lower() not in HASHES:
        choices = ", ".join(HASHES)
        raise ValueError(f"unsupported hash algorithm: {hash_name!r}; choose one of {choices}")
    return hashlib.new(hash_name.lower())


def _digest_to_int(digest: bytes, n: int) -> tuple[int, int]:
    """Convert a digest to ECDSA's integer e and return (e, removed_bits)."""
    if not isinstance(n, int) or isinstance(n, bool) or n <= 1:
        raise ValueError("the curve order n must be an integer greater than 1")

    digest_bits = len(digest) * 8
    order_bits = n.bit_length()
    removed_bits = max(0, digest_bits - order_bits)

    # This is a right shift because the digest is read as one big-endian
    # integer.  It keeps the bits on the left; using ``value % n`` here would
    # be a different operation and would not match ECDSA implementations.
    e = int.from_bytes(digest, "big")
    if removed_bits:
        e >>= removed_bits
    return e, removed_bits


def _finish_hash(hasher, curve: "Curve", trace: "Trace | None", source: str) -> int:
    """Finish a prepared hash object and record the student-facing trace."""
    digest = hasher.digest()
    e, removed_bits = _digest_to_int(digest, curve.n)
    if hasher.name == "sha1":
        add_step(
            trace,
            "Warning: SHA-1 is insecure",
            "SHA-1 is available for comparison only; choose SHA-256 or stronger",
            hash="sha1",
            status="insecure, for comparison only",
        )
    add_step(
        trace,
        "Hash the message" if source == "message" else "Hash the file",
        "digest = HASH(data)",
        hash=hasher.name,
        digest=digest.hex(),
        source=source,
    )
    add_step(
        trace,
        "Convert the digest to the integer e",
        "e = leftmost min(hash_bits, bit_length(n)) bits of digest",
        digest_bits=len(digest) * 8,
        order_bits=curve.n.bit_length(),
        removed_bits=removed_bits,
        e=e,
    )
    return e


def hash_message(
    msg: bytes,
    curve: "Curve",
    hash_name: str = "sha256",
    trace: "Trace | None" = None,
) -> int:
    """Hash ``msg`` and return the integer ``e`` used by ECDSA.

    ``msg`` must already be bytes so the caller makes the text encoding choice
    explicitly (normally UTF-8 in the GUI).
    """
    if not isinstance(msg, bytes):
        raise TypeError("msg must be bytes")
    hasher = _new_hasher(hash_name)
    hasher.update(msg)
    return _finish_hash(hasher, curve, trace, "message")


def hash_file(
    path: str | PathLike,
    curve: "Curve",
    hash_name: str = "sha256",
    trace: "Trace | None" = None,
) -> int:
    """Hash a file in 64 KiB chunks and return the ECDSA integer ``e``.

    Reading in chunks lets the app sign a large file without loading the whole
    file into memory at once.
    """
    hasher = _new_hasher(hash_name)
    with open(path, "rb") as file:
        while chunk := file.read(_FILE_CHUNK_SIZE):
            hasher.update(chunk)
    return _finish_hash(hasher, curve, trace, "file")
