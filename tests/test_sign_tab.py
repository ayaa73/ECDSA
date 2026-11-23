"""Focused GUI tests for P3's practical Sign tab."""
from __future__ import annotations

from PySide6.QtCore import QSettings

from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.keys import public_from_private
from ecdsa_edu.core.types import PrivateKey
from ecdsa_edu.gui import app as app_module
from ecdsa_edu.gui.app_state import AppState
from ecdsa_edu.gui.main_window import MainWindow
from ecdsa_edu.gui.tabs.sign_tab import SignTab


def _state_with_key() -> AppState:
    curve = get_curve("toy-17")
    state = AppState(curve=curve, settings=QSettings())
    priv = PrivateKey(7, curve)
    state.set_keys(priv, public_from_private(priv))
    return state


def _wait_idle(qtbot, tab: SignTab) -> None:
    qtbot.waitUntil(lambda: not tab._busy, timeout=10_000)


def test_no_key_empty_state_links_to_keys(qtbot):
    state = AppState(curve=get_curve("toy-17"), settings=QSettings())
    tab = SignTab(state)
    qtbot.addWidget(tab)
    requested = []
    state.pageRequested.connect(requested.append)

    assert tab.no_key_box.isVisibleTo(tab)
    assert not tab.sign_button.isEnabled()
    tab.go_to_keys_button.click()
    assert requested == ["Keys"]


def test_beginner_signing_on_toy17_produces_valid_values_and_hides_d(qtbot):
    state = _state_with_key()
    tab = SignTab(state)
    qtbot.addWidget(tab)
    tab.show()
    tab.message_edit.setPlainText("hello")

    tab.sign_button.click()
    _wait_idle(qtbot, tab)

    sig = state.last_sig
    assert sig is not None and 1 <= sig.r < state.curve.n and 1 <= sig.s < state.curve.n
    assert state.last_msg == b"hello"
    assert tab.r_output.hex_value() and tab.s_output.hex_value()
    assert tab.encoding_output.hex_value()
    assert all("d" not in {name.strip().lower() for name in step.values} for step in tab._last_trace)


def test_expert_mode_exposes_nonce_and_encoding_controls(qtbot):
    state = _state_with_key()
    tab = SignTab(state)
    qtbot.addWidget(tab)

    assert not tab.expert_options.isVisibleTo(tab)
    state.set_mode("expert")
    tab.show()
    assert tab.expert_options.isVisibleTo(tab)

    tab.manual_radio.click()
    tab.manual_k_field.setText("10")
    tab.message_edit.setPlainText("hello")
    tab.sign_button.click()
    _wait_idle(qtbot, tab)
    assert (state.last_sig.r, state.last_sig.s) == (7, 13)

    tab.der_encoding_radio.click()
    assert tab.encoding_output.hex_value().startswith("30")


def test_expert_file_signing_uses_the_file_path(qtbot, tmp_path, monkeypatch):
    state = _state_with_key()
    state.set_mode("expert")
    tab = SignTab(state)
    qtbot.addWidget(tab)
    path = tmp_path / "coursework.txt"
    path.write_bytes(b"file signing checks the bytes in this file")
    monkeypatch.setattr(
        "ecdsa_edu.gui.tabs.sign_tab.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(path), "All files (*)"),
    )

    tab.choose_file_button.click()
    assert tab._file_path == str(path) and not tab.manual_radio.isEnabled()
    tab.random_radio.click()
    tab.sign_button.click()
    _wait_idle(qtbot, tab)

    assert state.last_sig is not None
    assert state.last_msg is None  # files stay on disk instead of being copied into AppState
    assert tab._last_trace[0].title == "Hash the file"


def test_curve_change_clears_a_displayed_signature(qtbot):
    state = _state_with_key()
    tab = SignTab(state)
    qtbot.addWidget(tab)
    tab.sign_button.click()
    _wait_idle(qtbot, tab)
    assert tab.result_box.isVisibleTo(tab)

    state.set_curve(get_curve("toy-97"))
    tab.set_curve(state.curve)
    assert state.last_sig is None and not tab.result_box.isVisibleTo(tab)
    assert "curve changed" in tab.status.text().lower()


def test_main_window_loads_the_real_sign_page(qtbot):
    state = _state_with_key()
    window = MainWindow(state)
    qtbot.addWidget(window)

    assert isinstance(window.pages["Sign"], SignTab)


def test_sign_page_has_one_outer_scroll_area(qtbot):
    tab = SignTab(_state_with_key())
    qtbot.addWidget(tab)
    tab.resize(1000, 650)
    tab.show()

    assert tab.page_scroll.widgetResizable()
    assert tab.trace_view.minimumHeight() >= 360


def test_rapid_theme_toggles_settle_on_the_final_theme(qtbot, qapp):
    saved = (qapp.styleSheet(), qapp.palette(), qapp.style().objectName(), qapp.property("theme"))
    try:
        app_module.apply_theme(qapp, "light")
        tab = SignTab(_state_with_key())
        qtbot.addWidget(tab)
        tab.show()

        # These calls happen without a wait between them, just like several
        # quick clicks on the toolbar theme button.
        for theme in ("dark", "light", "dark", "light"):
            app_module.apply_theme(qapp, theme)

        qtbot.waitUntil(
            lambda: not tab._style_refresh_pending
            and not tab.trace_view._style_refresh_pending,
            timeout=2_000,
        )
        assert app_module.current_theme(qapp) == "light"
        assert tab._visual_dark is False
        assert tab.trace_view._visual_dark is False
    finally:
        qapp.setStyle(saved[2])
        qapp.setPalette(saved[1])
        qapp.setStyleSheet(saved[0])
        qapp.setProperty("theme", saved[3])
