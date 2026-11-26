"""Pages must fit the window: no sideways scrolling at 1024x700 or 1440x900,
even with a secp256k1 trace (78-digit numbers) on screen."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QScrollArea

from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.keys import generate_keypair
from ecdsa_edu.core.sign import sign
from ecdsa_edu.core.verify import verify
from ecdsa_edu.gui.app_state import AppState
from ecdsa_edu.gui.main_window import MainWindow
from ecdsa_edu.gui.widgets.wrap import ZWSP, soft_wrap, unwrap

SIZES = [(1024, 700), (1440, 900)]


def test_soft_wrap_only_breaks_long_runs():
    number = "1" * 78
    wrapped = soft_wrap(f"x = {number} mod n")
    assert ZWSP in wrapped and unwrap(wrapped) == f"x = {number} mod n"
    assert soft_wrap("short words stay as they are") == "short words stay as they are"
    assert soft_wrap("<b>" + "a" * 40 + "</b>").startswith("<b>")  # tags are left alone


@pytest.fixture
def window(qtbot, qapp):
    from ecdsa_edu.gui.app import apply_theme, current_theme
    if current_theme(qapp) != "dark":
        apply_theme(qapp, "dark")  # the app's real look (fonts and paddings decide the widths)
    state = AppState(get_curve("secp256k1"))
    win = MainWindow(state)
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    priv, pub = generate_keypair(state.curve)
    state.set_keys(priv, pub)
    sig = sign(priv, b"hi", "sha512")
    state.set_signature(sig, b"hi", "sha512")
    return win


def _overflow(page) -> int:
    scrolls = [s for s in page.findChildren(QScrollArea) if s.isVisible() and s.widgetResizable()
               and s.objectName() != "learnStepper"]  # the Learn stepper scrolls sideways on purpose
    return max((s.horizontalScrollBar().maximum() for s in scrolls), default=0)


@pytest.mark.parametrize("size", SIZES)
def test_verify_trace_does_not_widen_the_page(qtbot, window, size):
    state = window.state
    verify_page = window.pages["Verify"]
    trace: list = []
    ok = verify(state.pub, b"hi", state.last_sig, "sha512", trace)
    verify_page._show_result(ok, trace)
    verify_page.show_math.setChecked(True)
    window.resize(*size)
    window.show_page("Verify")
    qtbot.wait(100)
    assert verify_page.trace_card.isVisible()
    assert verify_page.trace_view.minimumSizeHint().width() < 400  # buttons wrap, numbers wrap
    assert _overflow(verify_page) == 0


@pytest.mark.parametrize("size", SIZES)
def test_no_page_scrolls_sideways(qtbot, window, size):
    window.resize(*size)
    too_wide = []
    for title in window.pages:
        window.show_page(title)
        qtbot.wait(30)
        if _overflow(window.pages[title]):
            too_wide.append(title)
    assert too_wide == []
