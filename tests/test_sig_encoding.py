"""Tests for P3 signature hex and DER encoding."""
from __future__ import annotations

import pytest

from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.sig_encoding import sig_from_der, sig_from_hex, sig_to_der, sig_to_hex
from ecdsa_edu.core.types import Signature


def test_hex_uses_fixed_width_for_the_curve_order():
    curve = get_curve("toy-17")
    sig = Signature(7, 13)

    assert sig_to_hex(sig, curve) == "070d"
    assert sig_from_hex("070d", curve) == sig
    assert sig_from_hex("  0x070D  ", curve) == sig


def test_hex_pads_both_p256_components_to_32_bytes():
    curve = get_curve("P-256")
    encoded = sig_to_hex(Signature(1, 2), curve)

    assert len(encoded) == 128
    assert encoded == "1".zfill(64) + "2".zfill(64)


@pytest.mark.parametrize("encoded", ["", "070", "070d00", "zzzz", "000d", "0713"])
def test_bad_hex_raises_value_error(encoded):
    with pytest.raises(ValueError):
        sig_from_hex(encoded, get_curve("toy-17"))


@pytest.mark.parametrize("sig", [Signature(0, 1), Signature(1, 0), Signature(19, 1), Signature(1, 19)])
def test_hex_rejects_components_outside_the_curve_order(sig):
    with pytest.raises(ValueError):
        sig_to_hex(sig, get_curve("toy-17"))


@pytest.mark.parametrize(
    "sig",
    [
        Signature(1, 1),
        Signature(127, 128),  # s needs DER's leading 00 because its high bit is set
        Signature(2**255 + 123, 2**256 - 189),
    ],
)
def test_der_matches_cryptography_in_both_directions(sig):
    utils = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.utils")

    library_der = utils.encode_dss_signature(sig.r, sig.s)
    assert sig_to_der(sig) == library_der
    assert sig_from_der(library_der) == sig
    assert utils.decode_dss_signature(sig_to_der(sig)) == (sig.r, sig.s)


def test_der_high_bit_has_one_required_leading_zero():
    assert sig_to_der(Signature(1, 128)) == bytes.fromhex("300702010102020080")
    assert sig_from_der(bytes.fromhex("300702010102020080")) == Signature(1, 128)


@pytest.mark.parametrize(
    "garbage",
    [
        b"",
        b"not DER",
        bytes.fromhex("3006020101020101ff"),  # valid value followed by an extra byte
        bytes.fromhex("3007020101020101"),  # sequence length is too large
        bytes.fromhex("30800201010201010000"),  # indefinite length is BER, not DER
        bytes.fromhex("308106020101020101"),  # long length used for a short value
        bytes.fromhex("3006020180020101"),  # negative r
        bytes.fromhex("300702020001020101"),  # redundant leading zero
        bytes.fromhex("3006020100020101"),  # zero r
        bytes.fromhex("3009020101020101020101"),  # a third INTEGER
    ],
)
def test_malformed_der_always_raises_value_error(garbage):
    with pytest.raises(ValueError):
        sig_from_der(garbage)


@pytest.mark.parametrize("garbage", [None, 7, "3006020101020101", object()])
def test_non_byte_der_input_always_raises_value_error(garbage):
    with pytest.raises(ValueError):
        sig_from_der(garbage)  # type: ignore[arg-type]
