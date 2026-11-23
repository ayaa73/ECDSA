"""Focused tests for P3 message and file hashing."""
from __future__ import annotations

import hashlib

import pytest

from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.hashing import HASHES, hash_file, hash_message


def test_supported_hashes_match_the_contract():
    assert HASHES == ["sha256", "sha384", "sha512", "sha1"]


def test_sha256_message_matches_hashlib_on_256_bit_order():
    curve = get_curve("secp256k1")
    message = b"EECE 455 ECDSA Lab"
    expected = int.from_bytes(hashlib.sha256(message).digest(), "big")
    assert hash_message(message, curve) == expected


def test_hash_is_truncated_to_leftmost_order_bits():
    curve = get_curve("toy-17")
    digest = hashlib.sha256(b"hello").digest()
    expected = int.from_bytes(digest, "big") >> (256 - curve.n.bit_length())
    result = hash_message(b"hello", curve)
    assert result == expected
    assert result.bit_length() <= curve.n.bit_length()


def test_file_hash_matches_message_hash_across_many_chunks(tmp_path):
    data = b"ECDSA file data\x00" * 20_000
    path = tmp_path / "large.bin"
    path.write_bytes(data)
    curve = get_curve("P-256")
    assert hash_file(path, curve, "sha384") == hash_message(data, curve, "sha384")


def test_hash_trace_explains_digest_and_truncation():
    trace = []
    hash_message(b"hello", get_curve("toy-17"), trace=trace)
    assert [step.title for step in trace] == [
        "Hash the message",
        "Convert the digest to the integer e",
    ]
    assert trace[-1].values["order_bits"] == "5"
    assert trace[-1].values["removed_bits"] == "251"


def test_sha1_trace_marks_it_as_insecure():
    trace = []
    hash_message(b"historical example", get_curve("toy-17"), "sha1", trace)
    assert trace[0].title == "Warning: SHA-1 is insecure"
    assert trace[0].values["status"] == "insecure, for comparison only"


def test_rejects_unknown_hash_and_non_bytes_message():
    curve = get_curve("toy-17")
    with pytest.raises(ValueError, match="unsupported hash"):
        hash_message(b"hello", curve, "md5")
    with pytest.raises(TypeError, match="must be bytes"):
        hash_message("hello", curve)  # type: ignore[arg-type]
