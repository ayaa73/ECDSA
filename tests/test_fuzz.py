"""Fuzz tests (P4): many random round trips, and random garbage into every parser.

Two rules are checked here:
1. Anything we sign verifies, and a changed message does not (round trips).
2. Parsers and verify() never crash on bad input: parsers raise ValueError only,
   and verify() just returns False.

The random generators use fixed seeds, so a failure can be reproduced exactly.
"""
from __future__ import annotations

import json
import random

import pytest

from ecdsa_edu.core.attacks import recover_from_nonce_reuse
from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.hashing import hash_message
from ecdsa_edu.core.key_io import load_private_key, load_public_key, point_from_hex, point_to_hex
from ecdsa_edu.core.keys import generate_keypair
from ecdsa_edu.core.sign import sign
from ecdsa_edu.core.types import PublicKey, Signature
from ecdsa_edu.core.verify import verify

CURVE_NAMES = ["toy-17", "toy-97", "secp256k1", "P-256"]


def random_message(rng: random.Random) -> bytes:
    return rng.randbytes(rng.randint(0, 64))


def tampered(msg: bytes, rng: random.Random) -> bytes:
    """Flip one random bit (or add a byte to an empty message)."""
    if not msg:
        return b"\x00"
    i = rng.randrange(len(msg))
    return msg[:i] + bytes([msg[i] ^ (1 << rng.randrange(8))]) + msg[i + 1:]


# --- 1. Round trips ---------------------------------------------------------
@pytest.mark.parametrize("curve_name, rounds", [("toy-97", 1000), ("P-256", 50), ("secp256k1", 50)])
def test_sign_verify_round_trips(curve_name, rounds):
    rng = random.Random(f"round-trip-{curve_name}")
    curve = get_curve(curve_name)
    n = curve.n
    toy = n.bit_length() < 64
    priv, pub = generate_keypair(curve)
    tamper_checks = lucky_forgeries = 0
    for i in range(rounds):
        if i % 50 == 0:  # a fresh key now and then
            priv, pub = generate_keypair(curve)
        msg = random_message(rng)
        sig = sign(priv, msg, deterministic=bool(i % 2))  # alternate RFC 6979 and random k
        assert 1 <= sig.r < n and 1 <= sig.s < n
        assert verify(pub, msg, sig), f"round {i}: our own signature did not verify"

        other = tampered(msg, rng)
        # On toy curves the hash is cut to bitlen(n) bits, so two messages can
        # genuinely share e mod n; then the same signature is valid for both.
        if hash_message(other, curve) % n == hash_message(msg, curve) % n:
            continue
        tamper_checks += 1
        accepted = verify(pub, other, sig)
        if toy:
            # With a tiny n, the point u1*G + u2*Q of a changed message has
            # x mod n == r by pure chance about 2/n of the time (2.5% for n = 79).
            # That is the toy curve's weakness, not a bug, so only check the rate.
            lucky_forgeries += accepted
        else:
            assert not accepted, f"round {i}: a changed message still verified"
    if toy:
        assert lucky_forgeries / tamper_checks < 6 / n, (
            f"{lucky_forgeries} of {tamper_checks} changed messages verified; expected about 2/n")


# --- 2. Garbage into verify(): never raises, returns False -----------------
GARBAGE_SIGS = [Signature(0, 0), Signature(-1, 5), Signature(5, -1), Signature(2**600, 3),
                Signature(1.5, 2), Signature("12", 3), Signature(None, None), Signature(True, True)]


@pytest.mark.parametrize("curve_name", CURVE_NAMES)
def test_verify_never_raises_on_garbage(curve_name):
    rng = random.Random(f"verify-garbage-{curve_name}")
    curve = get_curve(curve_name)
    _, pub = generate_keypair(curve)
    bad_keys = [PublicKey((0, 0), curve), PublicKey((curve.p, 1), curve), PublicKey((-1, -1), curve),
                PublicKey(None, curve), PublicKey((1, 2, 3), curve), PublicKey("04abcd", curve)]
    cases = [(pub, b"msg", s) for s in GARBAGE_SIGS]
    cases += [(k, b"msg", Signature(1, 1)) for k in bad_keys]
    cases += [(pub, m, Signature(1, 1)) for m in ("text, not bytes", None, 123)]
    for _ in range(200):
        r = rng.choice([0, 1, curve.n - 1, curve.n, rng.randrange(-curve.n, 2 * curve.n)])
        s = rng.choice([0, 1, curve.n - 1, curve.n, rng.randrange(-curve.n, 2 * curve.n)])
        cases.append((pub, random_message(rng), Signature(r, s)))
    for key, msg, sig in cases:
        trace: list = []
        result = verify(key, msg, sig, trace=trace)  # must not raise
        assert result is False or (result is True and isinstance(sig.r, int))
        if result is False:
            assert trace and trace[-1].title.startswith("INVALID"), "a rejection must say why"


# --- 3. Garbage into the parsers: ValueError only ----------------------------
def garbage_strings(rng: random.Random, count: int) -> list[str]:
    out = ["", " ", "0x", "zz", "04", "02", "03", "05" + "00" * 32, "04" + "ff" * 64, "0x02" + "ab" * 33,
           "not hex at all", "\x00\x01", "02:ab:cd", "🙂"]
    for _ in range(count):
        kind = rng.randrange(4)
        if kind == 0:
            out.append(rng.randbytes(rng.randint(1, 70)).hex())
        elif kind == 1:
            out.append(rng.choice(["02", "03", "04"]) + rng.randbytes(rng.randint(0, 70)).hex())
        elif kind == 2:
            out.append("".join(rng.choice("0123456789abcdefxyz :") for _ in range(rng.randint(1, 140))))
        else:
            out.append(rng.randbytes(rng.randint(1, 40)).decode("latin-1"))
    return out


@pytest.mark.parametrize("curve_name", CURVE_NAMES)
def test_point_from_hex_only_raises_value_error(curve_name):
    rng = random.Random(f"point-hex-{curve_name}")
    curve = get_curve(curve_name)
    _, pub = generate_keypair(curve)
    for compressed in (True, False):  # sanity: real points still round-trip
        assert point_from_hex(curve, point_to_hex(curve, pub.Q, compressed)) == pub.Q
    for text in garbage_strings(rng, 400):
        try:
            Q = point_from_hex(curve, text)
        except ValueError:
            continue
        assert Q is not None  # if it parsed, it must be a real point (checked inside)


def garbage_json_docs(rng: random.Random, count: int) -> list[str]:
    docs = ["", "{", "[]", "null", "42", '"text"', "{}", '{"curve": 5}', '{"curve": "nope", "d": "0x1"}',
            '{"curve": "toy-17", "d": "zz"}', '{"curve": "toy-17", "d": "0x0"}', '{"curve": "toy-17", "d": -3}',
            '{"curve": "toy-17", "Qx": "0x1", "Qy": "0x1"}', '{"curve": "toy-17", "Qx": [], "Qy": {}}',
            '{"curve": "custom", "p": "0x11", "a": "2", "b": "2", "Gx": "5", "Gy": "1", "n": "19", "h": "1", '
            '"d": "0x3"}',
            '{"curve": "custom", "p": "abc", "d": "0x3"}', '{"curve": "toy-17", "d": "0x3", "extra": [1, 2]}',
            json.dumps({"curve": "toy-17", "d": "0x" + "f" * 300})]
    keys = ["curve", "d", "Qx", "Qy", "p", "a", "b", "Gx", "Gy", "n", "h"]
    values = [None, True, 0, -1, 3, 2**300, 1.5, "", "0x", "0x13", "12", "toy-17", "secp256k1", [], {}, "zz"]
    for _ in range(count):
        doc = {k: rng.choice(values) for k in rng.sample(keys, rng.randint(0, len(keys)))}
        docs.append(json.dumps(doc))
    return docs


@pytest.mark.parametrize("loader", [load_private_key, load_public_key], ids=["private", "public"])
def test_key_file_loaders_only_raise_value_error(tmp_path, loader):
    rng = random.Random(f"key-files-{loader.__name__}")
    path = tmp_path / "key.json"
    contents = garbage_json_docs(rng, 300)
    for text in contents:
        path.write_text(text, encoding="utf-8")
        try:
            loader(path)
        except ValueError:
            pass
    for _ in range(50):  # raw random bytes, not even text
        path.write_bytes(rng.randbytes(rng.randint(0, 200)))
        try:
            loader(path)
        except ValueError:
            pass


def test_signature_parsers_only_raise_value_error():
    enc = pytest.importorskip("ecdsa_edu.core.sig_encoding")  # P3's module
    from ecdsa_edu.gui.tabs.p4_logic import signature_formats_available
    if not signature_formats_available():
        pytest.skip("sig_encoding.py is still a stub (raises NotImplementedError)")
    rng = random.Random("sig-parsers")
    for curve_name in CURVE_NAMES:
        curve = get_curve(curve_name)
        for text in garbage_strings(rng, 200):
            try:
                enc.sig_from_hex(text, curve)
            except ValueError:
                pass
    for _ in range(500):
        blob = rng.randbytes(rng.randint(0, 80))
        if rng.random() < 0.5:  # make it look like DER: SEQUENCE tag and a plausible length
            blob = b"\x30" + bytes([len(blob)]) + blob
        try:
            enc.sig_from_der(blob)
        except ValueError:
            pass


# --- 4. Garbage into the attack: ValueError only ------------------------------
@pytest.mark.parametrize("curve_name", ["toy-17", "toy-97", "secp256k1"])
def test_attack_only_raises_value_error(curve_name):
    rng = random.Random(f"attack-{curve_name}")
    curve = get_curve(curve_name)
    n = curve.n
    for _ in range(300):
        r = rng.choice([0, 1, n - 1, n, rng.randrange(-n, 2 * n)])
        r2 = r if rng.random() < 0.7 else rng.randrange(-n, 2 * n)
        sig1 = Signature(r, rng.randrange(-n, 2 * n))
        sig2 = Signature(r2, rng.randrange(-n, 2 * n))
        try:
            recover_from_nonce_reuse(curve, random_message(rng), sig1, random_message(rng), sig2)
        except ValueError:
            pass
