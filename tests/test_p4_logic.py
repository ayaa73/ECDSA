"""Tests for the plain-Python helpers behind P4's pages (no Qt needed)."""
from __future__ import annotations

import pytest

from ecdsa_edu.core.attacks import demo_nonce_reuse, recover_from_nonce_reuse
from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.keys import generate_keypair
from ecdsa_edu.core.sign import sign
from ecdsa_edu.core.types import PublicKey, Signature
from ecdsa_edu.core.verify import verify
from ecdsa_edu.gui.tabs.p4_logic import (
    attack_result, fmt_number, fmt_point, parse_signature_text, signature_formats_available, tamper_text,
    verdict_from_trace,
)
from ecdsa_edu.gui.tutorial.tutorial_content import FRAMES, SUGGESTED_ORDER

TOY = get_curve("toy-17")
BIG = get_curve("secp256k1")


# --- signature input ------------------------------------------------------------
@pytest.mark.parametrize("text", ["7, 17", "7,17", "(7, 17)", "7 17", "r=7, s=17", "r = 0x7 s = 0x11", " 0x7 ; 17 "])
def test_parse_r_s_pairs(text):
    assert parse_signature_text(text, TOY) == Signature(7, 17)


@pytest.mark.parametrize("text", ["", "   ", "seven, seventeen", "7", "7, 17, 3"])
def test_parse_rejects_with_value_error(text):
    with pytest.raises(ValueError):
        parse_signature_text(text, TOY)


def test_parse_big_numbers():
    sig = parse_signature_text(f"{hex(BIG.n - 1)}, {BIG.n - 2}", BIG)
    assert sig == Signature(BIG.n - 1, BIG.n - 2)


def test_parse_hex_before_sig_encoding_explains_what_to_do():
    if signature_formats_available():
        pytest.skip("P3's sig_encoding.py is merged; hex input is supported")
    with pytest.raises(ValueError, match="r, s"):
        parse_signature_text("3006020107020111", TOY)


# --- tamper ---------------------------------------------------------------------
@pytest.mark.parametrize("text", ["Hello", "Pay Bob 10 USD", "1234", "a b", "!!!", "x", "é漢字"])
def test_tamper_changes_exactly_one_character(text):
    new, what = tamper_text(text)
    assert len(new) == len(text)
    assert sum(a != b for a, b in zip(new, text)) == 1
    assert "changed character" in what


def test_tamper_empty_message():
    assert tamper_text("")[0] == "!"


# --- verdicts -------------------------------------------------------------------
def test_verdict_valid_and_tampered():
    priv, pub = generate_keypair(BIG)
    sig = sign(priv, b"Hello")
    trace: list = []
    assert verdict_from_trace(verify(pub, b"Hello", sig, trace=trace), trace).headline == "VALID"
    trace = []
    v = verdict_from_trace(verify(pub, b"hello", sig, trace=trace), trace)
    assert (v.valid, v.headline) == (False, "INVALID")
    assert "does not match r" in v.reason


@pytest.mark.parametrize("sig, words", [(Signature(0, 5), "r must be"), (Signature(5, 0), "s must be")])
def test_verdict_explains_range_errors(sig, words):
    _, pub = generate_keypair(TOY)
    trace: list = []
    v = verdict_from_trace(verify(pub, b"m", sig, trace=trace), trace)
    assert words in v.reason


def test_verdict_explains_bad_key():
    trace: list = []
    v = verdict_from_trace(verify(PublicKey((1, 1), TOY), b"m", Signature(1, 1), trace=trace), trace)
    assert "not a point on the selected curve" in v.reason


# --- attack ---------------------------------------------------------------------
@pytest.mark.parametrize("name", ["toy-17", "secp256k1"])
def test_attack_result_match(name):
    demo = demo_nonce_reuse(get_curve(name))
    found = recover_from_nonce_reuse(demo["curve"], demo["msg1"], demo["sig1"], demo["msg2"], demo["sig2"])
    result = attack_result(demo, found)
    assert result.match and result.recovered_d == result.real_d
    assert result.headline.startswith("MATCH")


def test_attack_result_no_match():
    demo = demo_nonce_reuse(TOY)
    wrong_d = demo["d"] % (TOY.n - 1) + 1
    assert not attack_result(demo, (wrong_d, demo["k"])).match


# --- formatting and tutorial content ------------------------------------------
def test_formatting_small_and_big():
    assert fmt_number(19, TOY) == "19"
    assert fmt_number(BIG.n, BIG).startswith("0x")
    assert fmt_point(None) == "O (the point at infinity)"
    assert fmt_point((5, 1), TOY) == "(5, 1)"


def test_tutorial_content():
    assert len(FRAMES) == 5 and all(f.title and f.text for f in FRAMES)
    from ecdsa_edu.gui.main_window import PAGE_SPECS
    pages = [stop.page for stop in SUGGESTED_ORDER]
    assert set(pages) <= {spec.title for spec in PAGE_SPECS}  # every suggested stop is a real sidebar page
    assert len(pages) == len(set(pages))
