"""Tests for core/key_io.py (owner: P2): SEC 1 point encoding and JSON key files."""
from __future__ import annotations

import json
import os
import stat
import sys

import pytest

from ecdsa_edu.core.curve import Curve, is_on_curve
from ecdsa_edu.core.curves_registry import CURVES, get_curve
from ecdsa_edu.core.key_io import (
    load_private_key,
    load_public_key,
    point_from_hex,
    point_to_hex,
    save_private_key,
    save_public_key,
)
from ecdsa_edu.core.keys import generate_keypair, public_from_private
from ecdsa_edu.core.types import PrivateKey, PublicKey

TOY_MULTIPLES = [
    (5, 1), (6, 3), (10, 6), (3, 1), (9, 16), (16, 13), (0, 6), (13, 7), (7, 6),
    (7, 11), (13, 10), (0, 11), (16, 4), (9, 1), (3, 16), (10, 11), (6, 14), (5, 16),
]
REAL_CURVES = ["secp256k1", "P-256"]
# Same parameters as toy-17 under another name -> treated as a custom curve.
CUSTOM = Curve(name="my-curve", p=17, a=2, b=2, G=(5, 1), n=19, h=1)
# y^2 = x^3 + x + 1 (mod 23): 28 points, G of order 7, contains (4, 0) and (0, 1).
COFACTOR_CURVE = Curve(name="cofactor-23", p=23, a=1, b=1, G=(5, 4), n=7, h=4)


@pytest.fixture
def toy() -> Curve:
    return get_curve("toy-17")


# ------------------------------------------------------------ point_to_hex
def test_known_toy_encodings(toy):
    assert point_to_hex(toy, (0, 6)) == "0200"  # y even -> 02
    assert point_to_hex(toy, (5, 1)) == "0305"  # y odd  -> 03
    assert point_to_hex(toy, (0, 6), compressed=False) == "040006"
    assert point_to_hex(toy, (16, 13), compressed=False) == "04100d"


def test_compressed_is_the_default(toy):
    assert point_to_hex(toy, (0, 6)) == point_to_hex(toy, (0, 6), compressed=True)


@pytest.mark.parametrize("name", REAL_CURVES)
def test_encoding_lengths_on_real_curves(name):
    curve = get_curve(name)
    _, pub = generate_keypair(curve)
    assert len(point_to_hex(curve, pub.Q, compressed=True)) == 2 * 33
    assert len(point_to_hex(curve, pub.Q, compressed=False)) == 2 * 65


def test_generator_of_secp256k1_has_the_well_known_encoding():
    curve = get_curve("secp256k1")
    assert point_to_hex(curve, curve.G) == "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"


@pytest.mark.parametrize("bad", [None, (5, 2), (17, 1), (-1, 1)])
def test_point_to_hex_rejects_invalid_points(toy, bad):
    with pytest.raises(ValueError):
        point_to_hex(toy, bad)


# ---------------------------------------------------------- point_from_hex
@pytest.mark.parametrize("Q", TOY_MULTIPLES)
@pytest.mark.parametrize("compressed", [True, False])
def test_roundtrip_every_toy_point(toy, Q, compressed):
    assert point_from_hex(toy, point_to_hex(toy, Q, compressed)) == Q


@pytest.mark.parametrize("name", ["toy-97", *REAL_CURVES])
@pytest.mark.parametrize("compressed", [True, False])
def test_roundtrip_on_other_curves(name, compressed):
    curve = get_curve(name)
    for _ in range(8):
        _, pub = generate_keypair(curve)
        assert point_from_hex(curve, point_to_hex(curve, pub.Q, compressed)) == pub.Q


@pytest.mark.parametrize("name", REAL_CURVES)
def test_encoding_matches_cryptography(name):
    ec = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ec")
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    reference_curve = {"secp256k1": ec.SECP256K1(), "P-256": ec.SECP256R1()}[name]
    curve = get_curve(name)
    for _ in range(5):
        _, pub = generate_keypair(curve)
        ref = ec.EllipticCurvePublicNumbers(pub.Q[0], pub.Q[1], reference_curve).public_key()
        compressed = ref.public_bytes(Encoding.X962, PublicFormat.CompressedPoint).hex()
        uncompressed = ref.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint).hex()
        assert point_to_hex(curve, pub.Q, compressed=True) == compressed
        assert point_to_hex(curve, pub.Q, compressed=False) == uncompressed
        # ...and we can decode what the reference library produced.
        assert point_from_hex(curve, compressed) == pub.Q
        assert point_from_hex(curve, uncompressed) == pub.Q


@pytest.mark.parametrize("text", ["0200", "02 00", "0x0200", " 02:00\n", "0X0200"])
def test_lenient_input_formats(toy, text):
    assert point_from_hex(toy, text) == (0, 6)


def test_uppercase_hex_is_accepted(toy):
    assert point_from_hex(toy, "04100D") == (16, 13)


@pytest.mark.parametrize(
    "text",
    [
        "",  # empty
        "zz",  # not hex
        "020",  # odd number of digits
        "00",  # point at infinity
        "0500",  # unknown prefix
        "0600",  # hybrid form: not supported
        "02",  # prefix only
        "020000",  # compressed, too long
        "0400",  # uncompressed, too short
        "04000600",  # uncompressed, too long
        "040007",  # not on the curve
        "0201",  # x = 1: x^3 + 2x + 2 = 5 is not a square mod 17
        "0211",  # x = 17 is not < p
        "041106",  # x = 17 is not < p
        "040017",  # y = 23 is not < p
    ],
)
def test_bad_encodings_are_rejected(toy, text):
    with pytest.raises(ValueError):
        point_from_hex(toy, text)


@pytest.mark.parametrize("not_text", [None, 512, b"0200"])
def test_non_string_input_is_rejected(toy, not_text):
    with pytest.raises(ValueError):
        point_from_hex(toy, not_text)  # type: ignore[arg-type]


def test_point_with_y_zero():
    """(4, 0) is its own negative: only the 'even' prefix can describe it."""
    assert point_to_hex(COFACTOR_CURVE, (4, 0)) == "0204"
    assert point_from_hex(COFACTOR_CURVE, "0204") == (4, 0)
    with pytest.raises(ValueError):
        point_from_hex(COFACTOR_CURVE, "0304")


def test_real_curve_rejects_point_from_other_curve():
    k1, p256 = get_curve("secp256k1"), get_curve("P-256")
    with pytest.raises(ValueError):
        point_from_hex(p256, point_to_hex(k1, k1.G, compressed=False))


# ---------------------------------------------------------------- key files
@pytest.mark.parametrize("name", ["toy-17", "toy-97", *REAL_CURVES])
def test_file_roundtrip_builtin_curves(tmp_path, name):
    curve = get_curve(name)
    priv, pub = generate_keypair(curve)
    save_private_key(tmp_path / "priv.json", priv)
    save_public_key(tmp_path / "pub.json", pub)
    loaded_priv = load_private_key(tmp_path / "priv.json")
    loaded_pub = load_public_key(tmp_path / "pub.json")
    assert loaded_priv == priv and loaded_pub == pub
    assert loaded_priv.curve is CURVES[name]  # the registry object, not a copy
    assert is_on_curve(curve, loaded_pub.Q)
    assert public_from_private(loaded_priv) == loaded_pub


def test_file_format_for_builtin_curves(tmp_path, toy):
    """Exactly {"curve": name, "d": hex} and {"curve": name, "Qx": hex, "Qy": hex}."""
    priv = PrivateKey(7, toy)
    save_private_key(tmp_path / "priv.json", priv)
    save_public_key(tmp_path / "pub.json", public_from_private(priv))
    assert _doc(tmp_path / "priv.json") == {"curve": "toy-17", "d": "0x7"}
    assert _doc(tmp_path / "pub.json") == {"curve": "toy-17", "Qx": "0x0", "Qy": "0x6"}
    assert "\n" in (tmp_path / "priv.json").read_text(encoding="utf-8").strip()  # indented, readable
    assert not list(tmp_path.glob("*.tmp"))  # the temp file was renamed away


def test_file_format_for_custom_curves(tmp_path):
    """A custom curve's parameters travel with the key."""
    priv = PrivateKey(7, CUSTOM)
    pub = public_from_private(priv)
    save_private_key(tmp_path / "priv.json", priv)
    save_public_key(tmp_path / "pub.json", pub)
    curve_fields = {"curve": "my-curve", "p": "0x11", "a": "0x2", "b": "0x2",
                    "Gx": "0x5", "Gy": "0x1", "n": "0x13", "h": "0x1"}
    assert _doc(tmp_path / "priv.json") == {**curve_fields, "d": "0x7"}
    assert _doc(tmp_path / "pub.json") == {**curve_fields, "Qx": "0x0", "Qy": "0x6"}
    assert load_private_key(tmp_path / "priv.json") == priv
    assert load_public_key(tmp_path / "pub.json") == pub
    assert load_public_key(tmp_path / "pub.json").curve == CUSTOM


def test_hand_written_files_are_accepted(tmp_path, toy):
    """Hex with or without 0x, upper or lower case."""
    path = tmp_path / "k.json"
    path.write_text('{"curve": "toy-17", "d": "7"}', encoding="utf-8")
    assert load_private_key(path) == PrivateKey(7, toy)
    path.write_text('{"curve": "toy-17", "d": "0X0A"}', encoding="utf-8")
    assert load_private_key(path).d == 10
    path.write_text('{"curve": "toy-17", "Qx": "10", "Qy": "d"}', encoding="utf-8")
    assert load_public_key(path).Q == (16, 13)  # "10" is hex: 16


def test_paths_may_be_strings(tmp_path):
    priv, _ = generate_keypair(get_curve("toy-17"))
    path = str(tmp_path / "k.json")
    save_private_key(path, priv)
    assert load_private_key(path) == priv


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_private_key_file_is_owner_only(tmp_path, toy):
    path = tmp_path / "priv.json"
    save_private_key(path, PrivateKey(7, toy))
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_saving_overwrites_an_existing_file(tmp_path, toy):
    path = tmp_path / "priv.json"
    save_private_key(path, PrivateKey(7, toy))
    save_private_key(path, PrivateKey(9, toy))
    assert load_private_key(path).d == 9


def test_invalid_keys_are_not_saved(tmp_path, toy):
    with pytest.raises(ValueError):
        save_private_key(tmp_path / "priv.json", PrivateKey(0, toy))
    with pytest.raises(ValueError):
        save_public_key(tmp_path / "pub.json", PublicKey((5, 2), toy))  # not on the curve
    impostor = Curve(name="toy-17", p=23, a=1, b=1, G=(5, 4), n=7, h=4)  # built-in name, other numbers
    with pytest.raises(ValueError):
        save_private_key(tmp_path / "priv.json", PrivateKey(3, impostor))
    assert not list(tmp_path.iterdir())


def test_missing_file_raises_oserror(tmp_path):
    with pytest.raises(OSError):
        load_private_key(tmp_path / "nope.json")


def test_wrong_kind_of_file_gives_a_clear_message(tmp_path, toy):
    priv = PrivateKey(7, toy)
    save_private_key(tmp_path / "priv.json", priv)
    save_public_key(tmp_path / "pub.json", public_from_private(priv))
    with pytest.raises(ValueError, match="contains a public key"):
        load_private_key(tmp_path / "pub.json")
    with pytest.raises(ValueError, match="contains a private key"):
        load_public_key(tmp_path / "priv.json")


@pytest.mark.parametrize(
    "content",
    [
        "",  # empty file
        "not json",
        '{"curve": "toy-17", "d": "0x7"',  # cut off
        "[1, 2, 3]",
        "42",
        "null",
        "{}",
        '{"hello": "world"}',
        "\xff\xfe",  # not UTF-8
    ],
)
def test_corrupted_files_are_rejected(tmp_path, content):
    path = tmp_path / "bad.json"
    path.write_text(content, encoding="latin-1")
    with pytest.raises(ValueError):
        load_private_key(path)
    with pytest.raises(ValueError):
        load_public_key(path)


def test_oversized_file_is_rejected(tmp_path):
    path = tmp_path / "big.json"
    path.write_text('{"curve": "toy-17", "d": "0x7", "junk": "' + "x" * 1_100_000 + '"}', encoding="utf-8")
    with pytest.raises(ValueError, match="too large"):
        load_private_key(path)


def _doc(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _saved_private_doc(tmp_path, priv) -> dict:
    save_private_key(tmp_path / "k.json", priv)
    return _doc(tmp_path / "k.json")


def _saved_public_doc(tmp_path, pub) -> dict:
    save_public_key(tmp_path / "k.json", pub)
    return _doc(tmp_path / "k.json")


def _write(tmp_path, doc: dict):
    path = tmp_path / "edited.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "edit",
    [
        lambda d: d.update(d="0x0"),  # d = 0
        lambda d: d.update(d="0x13"),  # d = n
        lambda d: d.update(d="-0x3"),  # negative
        lambda d: d.update(d="seven"),  # not a number
        lambda d: d.update(d=""),  # empty
        lambda d: d.update(d=7.5),  # wrong JSON type
        lambda d: d.update(d=True),  # bool is not a number here
        lambda d: d.update(d=None),
        lambda d: d.pop("d"),  # missing
        lambda d: d.pop("curve"),  # missing
        lambda d: d.update(curve=""),  # nameless
        lambda d: d.update(curve=17),  # wrong type
        lambda d: d.update(curve="no-such-curve"),  # unknown name, no parameters
        lambda d: d.update(p="0x13"),  # built-in name with (incomplete) other parameters
    ],
)
def test_tampered_private_key_files_are_rejected(tmp_path, toy, edit):
    doc = _saved_private_doc(tmp_path, PrivateKey(7, toy))
    edit(doc)
    with pytest.raises(ValueError):
        load_private_key(_write(tmp_path, doc))


def test_builtin_curve_cannot_be_redefined_by_a_file(tmp_path, toy):
    doc = _saved_private_doc(tmp_path, PrivateKey(3, CUSTOM))
    doc["curve"] = "toy-17"  # same numbers as toy-17: fine, and we get the registry object
    assert load_private_key(_write(tmp_path, doc)).curve is toy
    doc.update(p="0x17", a="0x1", b="0x1", Gx="0x5", Gy="0x4", n="0x7", h="0x4")  # a different, valid curve
    with pytest.raises(ValueError, match="do not match the built-in curve"):
        load_private_key(_write(tmp_path, doc))


def test_unknown_curve_message_lists_the_builtin_curves(tmp_path):
    path = _write(tmp_path, {"curve": "brainpool", "d": "0x7"})
    with pytest.raises(ValueError, match="unknown curve 'brainpool'.*toy-17"):
        load_private_key(path)


@pytest.mark.parametrize(
    "edit",
    [
        lambda c: c.update(p="0x15"),  # p = 21 is not prime
        lambda c: c.update(p="0x10"),  # even p
        lambda c: c.update(b="0x3"),  # G no longer on the curve
        lambda c: c.update(n="0x12"),  # 18 * G != O
        lambda c: c.update(n="0x0"),
        lambda c: c.update(h="0x0"),
        lambda c: c.update(Gx="0x16"),  # G out of range
        lambda c: c.update(a="0x0", b="0x0"),  # singular curve
        lambda c: c.update(p=hex(2**600 + 1)),  # absurdly large field
        lambda c: c.pop("n"),  # incomplete parameters
        lambda c: c.update(p="zz"),  # not hex
    ],
)
def test_invalid_custom_curves_are_rejected(tmp_path, edit):
    doc = _saved_private_doc(tmp_path, PrivateKey(7, CUSTOM))
    edit(doc)
    with pytest.raises(ValueError):
        load_private_key(_write(tmp_path, doc))


def test_custom_curve_over_a_composite_modulus_is_rejected(tmp_path):
    """p = 15: G = (1, 2) satisfies the equation, but the arithmetic breaks down."""
    doc = {"curve": "fake", "p": "0xf", "a": "0x1", "b": "0x2", "Gx": "0x1", "Gy": "0x2",
           "n": "0x7", "h": "0x1", "d": "0x3"}
    with pytest.raises(ValueError):
        load_private_key(_write(tmp_path, doc))


@pytest.mark.parametrize(
    "edit",
    [
        lambda d: d.update(Qy="0x7"),  # (0, 7) is not on the curve
        lambda d: d.update(Qx="0x1"),  # (1, 6) is not on the curve
        lambda d: d.update(Qx="0x11"),  # x = 17 is not < p
        lambda d: d.update(Qy="-0x6"),  # negative
        lambda d: d.update(Qx="zz"),  # not hex
        lambda d: d.update(Qy=None),
        lambda d: d.update(Qy=6.0),
        lambda d: d.pop("Qx"),
        lambda d: d.pop("Qy"),
    ],
)
def test_tampered_public_key_files_are_rejected(tmp_path, toy, edit):
    doc = _saved_public_doc(tmp_path, PublicKey((0, 6), toy))
    edit(doc)
    with pytest.raises(ValueError):
        load_public_key(_write(tmp_path, doc))


def test_off_curve_point_message_is_friendly(tmp_path, toy):
    doc = _saved_public_doc(tmp_path, PublicKey((0, 6), toy))
    doc["Qy"] = "0x7"
    with pytest.raises(ValueError, match="not on the curve"):
        load_public_key(_write(tmp_path, doc))


def test_public_key_outside_the_subgroup_is_rejected(tmp_path):
    doc = _saved_public_doc(tmp_path, PublicKey(COFACTOR_CURVE.G, COFACTOR_CURVE))
    assert load_public_key(_write(tmp_path, doc)).Q == COFACTOR_CURVE.G
    doc.update(Qx="0x0", Qy="0x1")  # (0, 1) is on the curve but has order 28, not 7
    with pytest.raises(ValueError, match="subgroup"):
        load_public_key(_write(tmp_path, doc))
