"""Small, browser-independent checks for the verification game's host bridge."""

from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.gui.games.verification_game_tab import VerificationGameTab


def test_small_curve_is_serialized_for_the_game():
    curve = get_curve("toy-17")
    assert VerificationGameTab._curve_payload(curve) == {
        "name": "toy-17",
        "p": 17,
        "a": 2,
        "b": 2,
        "G": [5, 1],
        "n": 19,
        "h": 1,
    }


def test_large_curve_is_kept_out_of_the_enumerating_game():
    assert VerificationGameTab._curve_payload(get_curve("secp256k1")) is None

