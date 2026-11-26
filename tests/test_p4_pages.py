"""pytest-qt tests for P4's pages: Verify, Attack Demo and Start here.

They need PySide6 and pytest-qt (pip install PySide6 pytest-qt) and are skipped
without them. Background jobs are awaited with qtbot.waitUntil.
"""
from __future__ import annotations

import importlib.util

import pytest

HAS_QT = all(importlib.util.find_spec(m) for m in ("PySide6", "pytestqt"))
pytestmark = pytest.mark.skipif(not HAS_QT, reason="needs PySide6 and pytest-qt")

WAIT = 10_000  # ms; secp256k1 runs are still well under a second


@pytest.fixture
def state():
    from ecdsa_edu.core.curves_registry import get_curve
    from ecdsa_edu.gui.app_state import AppState
    return AppState(get_curve("toy-17"))


@pytest.fixture
def signed_state(state):
    from ecdsa_edu.core.keys import PrivateKey, public_from_private
    from ecdsa_edu.core.sign import sign
    # Some toy-curve keys also verify the changed message.
    priv = PrivateKey(2, state.curve)
    state.set_keys(priv, public_from_private(priv))
    state.set_signature(sign(priv, b"Hello Bob", "sha512"), b"Hello Bob", "sha512")  # as the Sign page does
    return state


# --- Verify ---------------------------------------------------------------------
def test_verify_valid_then_tamper_invalid(qtbot, signed_state):
    from ecdsa_edu.gui.tabs.verify_tab import VerifyTab
    tab = VerifyTab(signed_state)
    qtbot.addWidget(tab)
    assert tab.msg_edit.toPlainText() == "Hello Bob"  # pre-filled from the last signature

    tab.verify_button.click()
    qtbot.waitUntil(lambda: tab.banner.headline == "VALID", timeout=WAIT)
    assert tab.banner.kind == "good"

    tab.tamper_button.click()
    qtbot.waitUntil(lambda: tab.banner.headline == "INVALID", timeout=WAIT)
    assert tab.msg_edit.toPlainText() != "Hello Bob"
    assert tab.banner.kind == "bad"


def test_verify_without_key_explains_next_step(qtbot, state):
    from ecdsa_edu.gui.tabs.verify_tab import VerifyTab
    tab = VerifyTab(state)
    qtbot.addWidget(tab)
    tab.show()
    assert tab.key_go.isVisible()  # "Make a key on the Keys page"
    tab.verify_button.click()
    assert tab.banner.headline == "Not ready yet"


def test_verify_curve_change_clears(qtbot, signed_state):
    from ecdsa_edu.core.curves_registry import get_curve
    from ecdsa_edu.gui.tabs.verify_tab import VerifyTab
    tab = VerifyTab(signed_state)
    qtbot.addWidget(tab)
    signed_state.set_curve(get_curve("secp256k1"))
    tab.set_curve(signed_state.curve)
    assert "Curve changed" in tab.banner.headline


# --- Attack Demo ------------------------------------------------------------------
@pytest.mark.parametrize("curve_name", ["toy-17", "secp256k1"])
def test_attack_shows_match(qtbot, state, curve_name):
    from ecdsa_edu.core.curves_registry import get_curve
    from ecdsa_edu.gui.tabs.attack_tab import AttackTab
    state.set_curve(get_curve(curve_name))
    tab = AttackTab(state)
    qtbot.addWidget(tab)
    assert not tab.attack_button.isEnabled()

    tab.make_button.click()
    qtbot.waitUntil(lambda: tab.demo is not None, timeout=WAIT)
    assert tab.demo["sig1"].r == tab.demo["sig2"].r
    assert "same r" in tab.same_r.text()

    tab.attack_button.click()
    qtbot.waitUntil(lambda: tab.banner.headline == "MATCH", timeout=WAIT)
    assert tab.banner.kind == "good"


# --- Start here -------------------------------------------------------------------
def test_tutorial_story_and_demo(qtbot, state):
    from ecdsa_edu.gui.tutorial.tutorial_content import FRAMES
    from ecdsa_edu.gui.tutorial.tutorial_tab import TutorialTab
    tab = TutorialTab(state)
    qtbot.addWidget(tab)
    assert not hasattr(tab, "play_button")
    assert not hasattr(tab, "timer")
    assert "Welcome to ECDSA Lab" in tab.welcome_heading.text()
    assert "sidebar" in tab.how_label.text()
    qtbot.wait(100)
    assert tab.canvas.frame == 0

    for i in range(len(FRAMES) - 1):
        assert tab.canvas.frame == i
        tab.next_button.click()
    assert tab.canvas.frame == len(FRAMES) - 1 and not tab.next_button.isEnabled()
    tab.canvas.grab()  # paints the last frame (catches drawing errors)

    tab.keys_button.click()
    qtbot.waitUntil(lambda: tab.sign_button.isEnabled(), timeout=WAIT)
    tab.sign_button.click()
    qtbot.waitUntil(lambda: tab.verify_button.isEnabled(), timeout=WAIT)
    tab.verify_button.click()
    qtbot.waitUntil(lambda: tab.banner.headline == "VALID", timeout=WAIT)
    tab.tamper_button.click()
    qtbot.waitUntil(lambda: tab.banner.headline == "INVALID", timeout=WAIT)
    assert state.pub is None  # the practice key never replaces the student's key


def test_learning_keys_explain_random_d_and_manual_learning_choice(qtbot, state):
    from ecdsa_edu.gui.learn.pages_keys import KeysPage
    from ecdsa_edu.gui.learn.model import LearnState

    page = KeysPage()
    qtbot.addWidget(page)
    page.enter(LearnState(state.curve))
    text = page.text_label.text()
    assert "selected randomly" in text
    assert "learning walkthrough" in text


def test_tutorial_every_frame_paints(qtbot):
    from ecdsa_edu.gui.tutorial.tutorial_content import FRAMES
    from ecdsa_edu.gui.tutorial.tutorial_tab import StoryCanvas
    canvas = StoryCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(700, 230)
    for i in range(len(FRAMES)):
        canvas.set_frame(i)
        assert not canvas.grab().isNull()



def test_tutorial_has_no_navigation_buttons(qtbot, state):
    from PySide6.QtWidgets import QPushButton
    from ecdsa_edu.gui.tutorial.tutorial_tab import TutorialTab
    requested = []
    state.pageRequested.connect(requested.append)
    tab = TutorialTab(state)
    qtbot.addWidget(tab)
    for button in tab.findChildren(QPushButton):
        if button.isEnabled():
            button.click()
    qtbot.wait(50)
    assert requested == []
    order = tab.order_label.text()
    assert order.index("Keys") < order.index("Sign") < order.index("Verify")


# --- Overview -----------------------------------------------------------------------
def test_overview_greeting_follows_the_clock():
    from PySide6.QtCore import QTime
    from ecdsa_edu.gui.overview_tab import greeting
    assert greeting(QTime(8, 0)) == "Good morning"
    assert greeting(QTime(14, 30)) == "Good afternoon"
    assert greeting(QTime(21, 0)) == "Good evening"
    assert greeting(QTime(2, 0)) == "Good evening"


def test_overview_diagram_opens_pages(qtbot, state):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QPushButton
    from ecdsa_edu.gui.overview_tab import OverviewTab
    requested = []
    state.pageRequested.connect(requested.append)
    tab = OverviewTab(state)
    qtbot.addWidget(tab)
    tab.resize(900, 600)
    tab.show()
    assert tab.findChildren(QPushButton) == []
    assert "Welcome to ECDSA Lab" in tab.heading.text()
    qtbot.mouseClick(tab.canvas, Qt.MouseButton.LeftButton, pos=tab.canvas.node_center("priv").toPoint())
    qtbot.keyClick(tab.canvas, Qt.Key.Key_Home)
    qtbot.keyClick(tab.canvas, Qt.Key.Key_Return)
    assert requested == ["Keys", "Curve Explorer"]
