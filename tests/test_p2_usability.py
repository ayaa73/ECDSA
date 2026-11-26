"""Tests for P2's usability features: curve picker, the Keys page, "Suggest values".

Runs headless (offscreen Qt platform), like the other GUI tests.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # must be set before Qt starts

import pytest

pytest.importorskip("pytestqt")

from ecdsa_edu.core import curves_registry
from ecdsa_edu.core.curve import Curve, is_on_curve
from ecdsa_edu.core.curves_registry import CURVES, get_curve
from ecdsa_edu.gui.app_state import AppState
from ecdsa_edu.gui.main_window import MainWindow
from ecdsa_edu.gui.tabs.custom_curve_dialog import CustomCurveDialog
from ecdsa_edu.gui.tabs.keys_tab import KeysTab
from ecdsa_edu.gui.widgets.curve_picker import CurvePicker, curve_description

CUSTOM = Curve(name="my-curve", p=17, a=2, b=2, G=(5, 1), n=19, h=1)
# A working curve mod 97 that a "suggest" function could return (G is on it, n = 79 is prime).
SUGGESTED = Curve(name="p97-a0-b5", p=97, a=0, b=5, G=(1, 43), n=79, h=1)


@pytest.fixture
def state(qapp):
    return AppState()


def wait_idle(qtbot, widget):
    qtbot.waitUntil(lambda: not widget._busy, timeout=10_000)


# ================================================================ curve picker
def test_picker_has_a_card_for_every_builtin_curve(qtbot, state):
    picker = CurvePicker(state)
    qtbot.addWidget(picker)
    assert set(CURVES) <= set(picker.cards)


def test_clicking_a_card_chooses_that_curve(qtbot, state):
    picker = CurvePicker(state)
    qtbot.addWidget(picker)
    picker.cards["secp256k1"].click()
    assert picker.result() == CurvePicker.DialogCode.Accepted
    assert picker.chosen() == CURVES["secp256k1"] and not picker.wants_custom()


def test_make_your_own_card(qtbot, state):
    picker = CurvePicker(state)
    qtbot.addWidget(picker)
    picker.custom_card.click()
    assert picker.wants_custom() and picker.chosen() is None


def test_custom_curves_get_their_own_cards(qtbot, state):
    state.register_curve(CUSTOM)
    picker = CurvePicker(state)
    qtbot.addWidget(picker)
    assert "my-curve" in picker.cards


def test_current_curve_is_highlighted_and_focused(qtbot, state):
    state.set_curve(CURVES["toy-97"])
    picker = CurvePicker(state)
    qtbot.addWidget(picker)
    assert picker.cards["toy-97"].property("current") is True
    assert picker.cards["toy-17"].property("current") is False


def test_card_text_for_builtin_and_custom_curves():
    info = curve_description(CURVES["secp256k1"])
    assert info["key_bits"] == 256 and info["drawable"] is False and info["summary"]
    info = curve_description(CUSTOM)
    assert info["label"] == "my-curve" and info["key_bits"] == 5 and info["drawable"] is True


def test_card_text_comes_from_p1_when_available(monkeypatch):
    fake = {"label": "From P1", "summary": "s", "used_in": "u", "key_bits": 5, "drawable": True}
    monkeypatch.setattr(curves_registry, "describe_curve", lambda name: dict(fake), raising=False)
    assert curve_description(CURVES["toy-17"])["label"] == "From P1"


# ============================================================ toolbar button
def test_curve_button_shows_the_curve_and_opens_the_picker(qtbot, state, monkeypatch):
    window = MainWindow(state)
    qtbot.addWidget(window)
    assert "toy-17" in window.curve_button.text()

    def fake_exec(picker):
        picker.cards["toy-97"].click()
        return picker.result()

    monkeypatch.setattr(CurvePicker, "exec", fake_exec)
    window.open_curve_picker()
    assert state.curve == CURVES["toy-97"] and "toy-97" in window.curve_button.text()


def test_there_is_only_one_curve_control(qtbot, state):
    window = MainWindow(state)
    qtbot.addWidget(window)
    combo_action = window._toolbar_actions[window.curve_combo]
    assert not combo_action.isVisible()
    assert "toy-17" in window.curve_button.text()


# ======================================================= Keys page
def test_keys_page_shows_every_feature(qtbot, state):
    tab = KeysTab(state)
    qtbot.addWidget(tab)
    assert not tab.d_field.isReadOnly()
    assert tab._pub_form.isRowVisible(tab.uncompressed_field)
    assert not tab._box_trace.isHidden() and not tab.hex_check.isHidden()


def test_curve_change_offers_new_keys(qtbot, state):
    tab = KeysTab(state)
    qtbot.addWidget(tab)
    state.curveChanged.connect(tab.set_curve)
    tab.btn_generate.click()
    wait_idle(qtbot, tab)
    state.set_curve(CURVES["toy-97"])
    assert not tab.btn_regenerate.isHidden() and tab.status.property("kind") == "warning"
    tab.btn_regenerate.click()
    wait_idle(qtbot, tab)
    assert state.priv is not None and state.priv.curve == CURVES["toy-97"]
    assert tab.btn_regenerate.isHidden()


# ======================================================= "Suggest values"
def test_suggest_button_waits_for_p1(qtbot, state, monkeypatch):
    monkeypatch.delattr(curves_registry, "suggest_small_curves", raising=False)
    dialog = CustomCurveDialog(state)
    qtbot.addWidget(dialog)
    dialog.p_field.set_value(97)
    assert not dialog.btn_suggest.isEnabled()


def test_suggest_values_fills_a_valid_curve(qtbot, state, monkeypatch):
    monkeypatch.setattr(curves_registry, "suggest_small_curves", lambda p: [SUGGESTED], raising=False)
    dialog = CustomCurveDialog(state)
    qtbot.addWidget(dialog)
    dialog.p_field.set_value(97)
    assert dialog.btn_suggest.isEnabled()
    dialog.btn_suggest.click()
    qtbot.waitUntil(lambda: len(dialog.suggestion_buttons) == 1, timeout=10_000)
    dialog.suggestion_buttons[0].click()
    values = [f.value() for f in (dialog.p_field, dialog.a_field, dialog.b_field, dialog.gx_field, dialog.gy_field)]
    assert values == [97, 0, 5, 1, 43]
    assert is_on_curve(SUGGESTED, SUGGESTED.G) and dialog.g_hint.property("kind") == "ok"
    dialog.create_curve()
    qtbot.waitUntil(lambda: dialog.curve() is not None, timeout=10_000)
    assert dialog.curve().n == 79
