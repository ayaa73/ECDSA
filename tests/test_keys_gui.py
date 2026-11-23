"""GUI tests for P2's widgets, Keys tab, custom-curve dialog and app shell (pytest-qt).

Runs headless: the "offscreen" Qt platform is selected below, so no display is needed.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # must be set before Qt starts

import threading

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QFileDialog, QMessageBox

from ecdsa_edu.core.curve import Curve, is_on_curve, make_custom_curve
from ecdsa_edu.core.curves_registry import CURVES, get_curve
from ecdsa_edu.core.key_io import (
    load_private_key,
    load_public_key,
    point_to_hex,
    save_private_key,
    save_public_key,
)
from ecdsa_edu.core.keys import public_from_private
from ecdsa_edu.core.types import PrivateKey, PublicKey
from ecdsa_edu.gui.app_state import AppState
from ecdsa_edu.gui.main_window import MainWindow
from ecdsa_edu.gui.tabs.custom_curve_dialog import CustomCurveDialog
from ecdsa_edu.gui.tabs.keys_tab import KeysTab
from ecdsa_edu.gui.widgets.bigint_field import BigIntField, format_bigint, parse_bigint
from ecdsa_edu.gui.widgets import worker as worker_module
from ecdsa_edu.gui.widgets.hex_field import HexField, HexOutputField, normalize_hex
from ecdsa_edu.gui.widgets.worker import busy_tracker, friendly_message, run_in_background

CUSTOM = Curve(name="my-curve", p=17, a=2, b=2, G=(5, 1), n=19, h=1)


@pytest.fixture
def toy() -> Curve:
    return get_curve("toy-17")


@pytest.fixture
def state(qapp) -> AppState:
    return AppState()


@pytest.fixture
def tab(qtbot, state) -> KeysTab:
    state.set_mode("expert")  # most tests use the full page; Beginner mode has its own tests
    widget = KeysTab(state)
    qtbot.addWidget(widget)
    # MainWindow normally makes this connection for every page.
    state.curveChanged.connect(widget.set_curve)
    return widget


def wait_idle(qtbot, widget) -> None:
    """Wait until the widget's background job has reported back."""
    qtbot.waitUntil(lambda: not widget._busy, timeout=10_000)


# ========================================================= BigIntField
@pytest.mark.parametrize(
    "text, value",
    [("7", 7), (" 42 ", 42), ("0x1f", 31), ("0X1F", 31), ("1_000", 1000), ("-3", -3), ("+5", 5),
     ("12 345", 12345), ("0", 0), (str(2**521 - 1), 2**521 - 1), (hex(2**256), 2**256)],
)
def test_parse_bigint(text, value):
    assert parse_bigint(text) == value


@pytest.mark.parametrize("text", ["", "  ", "abc", "1f", "0x", "0xzz", "1.5", "--3", "1e5", "٣"])
def test_parse_bigint_rejects(text):
    with pytest.raises(ValueError):
        parse_bigint(text)


def test_format_bigint():
    assert format_bigint(255, False) == "255" and format_bigint(255, True) == "0xff"


def test_bigint_field_value_and_signal(qtbot):
    field = BigIntField()
    qtbot.addWidget(field)
    with qtbot.waitSignal(field.valueChanged) as blocker:
        field.setText("0x10")
    assert blocker.args == [16] and field.value() == 16 and field.is_valid() and field.error() == ""
    with qtbot.waitSignal(field.valueChanged) as blocker:
        field.setText("0x1g")
    assert blocker.args == [None] and field.value() is None and field.error()
    assert field.property("invalid") is True
    field.setText("")
    assert field.value() is None and field.error() == "" and field.property("invalid") is False


def test_bigint_field_range(qtbot):
    field = BigIntField(minimum=1, maximum=18)
    qtbot.addWidget(field)
    for text, ok in [("1", True), ("18", True), ("0", False), ("19", False), ("-1", False)]:
        field.setText(text)
        assert field.is_valid() is ok, text
    field.setText("19")
    field.set_range(1, 96)  # widening the range re-validates the text
    assert field.value() == 19


def test_bigint_field_display_base(qtbot):
    field = BigIntField()
    qtbot.addWidget(field)
    field.set_value(255)
    assert field.text() == "255"
    field.set_display_hex(True)
    assert field.text() == "0xff" and field.value() == 255
    field.set_value(None)
    assert field.text() == "" and field.value() is None


def test_bigint_field_handles_very_large_numbers(qtbot):
    field = BigIntField()
    qtbot.addWidget(field)
    big = 2**521 - 1
    field.set_value(big)
    assert field.value() == big


# ============================================================ HexField
@pytest.mark.parametrize(
    "text, clean",
    [("0200", "0200"), ("02 00", "0200"), ("0xAB:CD", "abcd"), (" 04\n00 06 ", "040006"), ("", "")],
)
def test_normalize_hex(text, clean):
    assert normalize_hex(text) == clean


@pytest.mark.parametrize("text", ["0", "02g0", "xyz", "020"])
def test_normalize_hex_rejects(text):
    with pytest.raises(ValueError):
        normalize_hex(text)


def test_hex_field(qtbot):
    field = HexField()
    qtbot.addWidget(field)
    with qtbot.waitSignal(field.valueChanged) as blocker:
        field.set_hex("04 00 06")
    assert blocker.args == ["040006"]
    assert field.hex_value() == "040006" and field.bytes_value() == b"\x04\x00\x06" and field.is_valid()
    field.set_hex("04 0")
    assert field.hex_value() == "" and field.bytes_value() is None and field.error()
    assert field.property("invalid") is True
    field.set_hex("")
    assert not field.is_valid() and field.error() == ""


# ====================================================== HexOutputField
def test_hex_output_field_is_read_only_and_starts_disabled(qtbot):
    out = HexOutputField()
    qtbot.addWidget(out)
    assert out.text_field.isReadOnly() and out.hex_value() == ""
    assert not out.copy_button.isEnabled() and not out.save_button.isEnabled()


def test_hex_output_field_copy(qtbot, qapp):
    out = HexOutputField()
    qtbot.addWidget(out)
    out.set_hex("04 AB cd")
    assert out.hex_value() == "04abcd" and out.bytes_value() == b"\x04\xab\xcd"
    assert out.copy_button.isEnabled() and out.save_button.isEnabled()
    out.copy_button.click()
    assert qapp.clipboard().text() == "04abcd" and "Copied" in out.copy_button.text()
    out.set_bytes(b"\x01\x02")
    assert out.hex_value() == "0102"
    out.clear()
    assert out.hex_value() == "" and not out.copy_button.isEnabled()


def test_hex_output_field_save(qtbot, tmp_path, monkeypatch):
    out = HexOutputField(save_name="sig")
    qtbot.addWidget(out)
    out.set_hex("0102ff")
    asked = []

    def fake_dialog(parent, title, suggested, filters):
        asked.append(suggested)
        return str(tmp_path / "out.txt"), "Hex text (*.txt)"

    monkeypatch.setattr("ecdsa_edu.gui.widgets.hex_field.QFileDialog.getSaveFileName", fake_dialog)
    out.save_button.click()
    assert asked == ["sig.txt"] and (tmp_path / "out.txt").read_text(encoding="utf-8") == "0102ff\n"

    monkeypatch.setattr("ecdsa_edu.gui.widgets.hex_field.QFileDialog.getSaveFileName",
                        lambda *a: (str(tmp_path / "out.bin"), "Raw bytes (*.bin)"))
    out.save_button.click()
    assert (tmp_path / "out.bin").read_bytes() == b"\x01\x02\xff"

    monkeypatch.setattr("ecdsa_edu.gui.widgets.hex_field.QFileDialog.getSaveFileName", lambda *a: ("", ""))
    out.save_button.click()  # cancelled: nothing happens


def test_hex_output_field_save_failure_is_reported(qtbot, tmp_path, monkeypatch):
    out = HexOutputField()
    qtbot.addWidget(out)
    out.set_hex("00")
    warnings = []
    monkeypatch.setattr("ecdsa_edu.gui.widgets.hex_field.QMessageBox.warning", lambda *a: warnings.append(a[1]))
    monkeypatch.setattr("ecdsa_edu.gui.widgets.hex_field.QFileDialog.getSaveFileName",
                        lambda *a: (str(tmp_path / "no_such_folder" / "x.txt"), "Hex text (*.txt)"))
    out.save_dialog()
    assert warnings == ["Could not save the file"]


# ============================================================== worker
@pytest.fixture
def error_boxes(monkeypatch) -> list:
    """Record the worker's message boxes instead of opening them."""
    shown: list = []
    monkeypatch.setattr(worker_module, "show_error", lambda exc, parent=None: shown.append(exc))
    return shown


def test_worker_delivers_result_on_the_gui_thread(qtbot, error_boxes):
    seen = {}

    def job(a, b):
        seen["job_thread"] = threading.current_thread()
        return a + b

    def done(result):
        seen["result"] = result
        seen["callback_thread"] = threading.current_thread()

    run_in_background(job, 2, 3, on_done=done, on_error=lambda exc: seen.setdefault("error", exc))
    qtbot.waitUntil(lambda: "result" in seen, timeout=5000)
    assert seen["result"] == 5 and "error" not in seen and error_boxes == []
    assert seen["callback_thread"] is threading.main_thread()
    assert seen["job_thread"] is not threading.main_thread()


def test_value_error_goes_to_on_error_and_a_friendly_box(qtbot, error_boxes):
    seen = {}

    def job():
        raise ValueError("d must be at least 1")

    def failed(exc):
        seen["error"] = exc
        seen["thread"] = threading.current_thread()
        seen["box_already_shown"] = bool(error_boxes)

    run_in_background(job, on_done=lambda r: seen.setdefault("result", r), on_error=failed)
    qtbot.waitUntil(lambda: bool(error_boxes), timeout=5000)
    assert isinstance(seen["error"], ValueError) and "result" not in seen
    assert seen["thread"] is threading.main_thread()
    assert seen["box_already_shown"] is False  # on_error runs first, then the box
    assert error_boxes == [seen["error"]]
    assert friendly_message(seen["error"]) == ("Please check your input", "D must be at least 1")


def test_on_error_returning_true_suppresses_the_box(qtbot, error_boxes):
    seen = []

    def job():
        raise ValueError("handled inline")

    def failed(exc):
        seen.append(exc)
        return True

    run_in_background(job, on_done=seen.append, on_error=failed)
    qtbot.waitUntil(lambda: bool(seen), timeout=5000)
    qtbot.wait(50)
    assert error_boxes == [] and str(seen[0]) == "handled inline"


def test_unexpected_exception_does_not_crash(qtbot, error_boxes, capsys):
    seen = []

    def job():
        return 1 // 0

    run_in_background(job, on_done=seen.append, on_error=seen.append)
    qtbot.waitUntil(lambda: bool(error_boxes), timeout=5000)
    assert isinstance(seen[0], ZeroDivisionError) and error_boxes == seen
    title, text = friendly_message(seen[0])
    assert title == "Unexpected error" and "bug" in text
    assert "ZeroDivisionError" in capsys.readouterr().err  # traceback for the developer


@pytest.mark.parametrize("failing", ["on_done", "on_error"])
def test_exception_inside_a_callback_does_not_crash(qtbot, error_boxes, capsys, failing):
    def bad_callback(_):
        raise RuntimeError("bug in the page")

    def job():
        if failing == "on_error":
            raise ValueError("first problem")
        return 1

    run_in_background(job, on_done=bad_callback, on_error=bad_callback)
    qtbot.waitUntil(lambda: bool(error_boxes), timeout=5000)
    assert isinstance(error_boxes[0], RuntimeError)
    assert "bug in the page" in capsys.readouterr().err


def test_friendly_messages():
    assert friendly_message(ValueError(""))[1] == "The input is not valid."
    assert friendly_message(FileNotFoundError(2, "No such file or directory"))[0] == "File problem"


def test_busy_indicator(qtbot, qapp, error_boxes):
    tracker = busy_tracker()
    events, release, results = [], threading.Event(), []
    tracker.busyChanged.connect(events.append)
    try:
        assert not tracker.is_busy()
        run_in_background(release.wait, 5, on_done=results.append, on_error=results.append)
        run_in_background(release.wait, 5, on_done=results.append, on_error=results.append)
        assert tracker.is_busy() and events == [True]
        assert qapp.overrideCursor() is not None  # busy mouse cursor
        release.set()
        qtbot.waitUntil(lambda: len(results) == 2, timeout=5000)
        assert not tracker.is_busy() and events == [True, False]  # one busy period for both jobs
        assert qapp.overrideCursor() is None
    finally:
        release.set()
        tracker.busyChanged.disconnect(events.append)


def test_busy_indicator_ends_after_a_failure(qtbot, error_boxes):
    def job():
        raise ValueError("nope")

    run_in_background(job, on_done=lambda r: None, on_error=lambda exc: True)
    qtbot.waitUntil(lambda: not busy_tracker().is_busy(), timeout=5000)


def test_worker_runs_many_jobs(qtbot, error_boxes):
    results = []
    for i in range(20):
        run_in_background(pow, i, 2, on_done=results.append, on_error=results.append)
    qtbot.waitUntil(lambda: len(results) == 20, timeout=5000)
    assert sorted(results) == [i * i for i in range(20)]


def test_worker_passes_a_trace_list_through(qtbot, toy, error_boxes):
    trace, out = [], []
    run_in_background(public_from_private, PrivateKey(7, toy), trace, on_done=out.append, on_error=out.append)
    qtbot.waitUntil(lambda: bool(out), timeout=5000)
    assert out[0].Q == (0, 6) and len(trace) >= 2


# ============================================================= KeysTab
def test_keys_tab_starts_empty(tab, state):
    assert tab.d_field.text() == "" and tab.qx_field.text() == ""
    assert tab.btn_generate.isEnabled() and not tab.btn_derive.isEnabled()
    assert not tab.btn_save_priv.isEnabled() and not tab.btn_save_pub.isEnabled()
    assert "18" in tab.d_hint.text()  # shows the allowed range 1..n-1


def test_generate_fills_state_and_view(qtbot, tab, state, toy):
    with qtbot.waitSignal(state.keysChanged, timeout=10_000):
        tab.btn_generate.click()
    wait_idle(qtbot, tab)
    assert state.priv is not None and state.pub == public_from_private(state.priv)
    assert tab.d_field.value() == state.priv.d
    assert (tab.qx_field.value(), tab.qy_field.value()) == state.pub.Q
    assert tab.compressed_field.hex_value()[:2] in ("02", "03")
    assert tab.uncompressed_field.hex_value().startswith("04")
    assert tab.btn_save_priv.isEnabled() and tab.btn_save_pub.isEnabled()


def test_generate_on_toy17_show_save_and_load_again(qtbot, tab, state, toy, tmp_path, monkeypatch):
    """The whole story: generate, see the values, Q is on the curve, save, load -> same key."""
    assert state.curve == toy
    with qtbot.waitSignal(state.keysChanged, timeout=10_000):  # Sign and Verify listen to this
        tab.btn_generate.click()
    wait_idle(qtbot, tab)
    priv, pub = state.priv, state.pub

    # values shown
    assert 1 <= priv.d <= 18 and tab.d_field.text() == str(priv.d)
    assert (tab.qx_field.text(), tab.qy_field.text()) == (str(pub.Q[0]), str(pub.Q[1]))
    assert tab.compressed_field.hex_value() == point_to_hex(toy, pub.Q, compressed=True)
    assert tab.uncompressed_field.hex_value() == point_to_hex(toy, pub.Q, compressed=False)
    # Q is on the curve
    assert is_on_curve(toy, pub.Q)

    # save both keys, wipe, load them back
    priv_path, pub_path = str(tmp_path / "priv.json"), str(tmp_path / "pub.json")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (priv_path, ""))
    tab.btn_save_priv.click()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (pub_path, ""))
    tab.btn_save_pub.click()
    state.clear_keys()
    assert tab.qx_field.text() == ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (priv_path, ""))
    tab.btn_load_priv.click()
    wait_idle(qtbot, tab)
    assert state.priv == priv and state.pub == pub  # the same key pair
    assert tab.d_field.value() == priv.d

    state.clear_keys()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (pub_path, ""))
    tab.btn_load_pub.click()
    wait_idle(qtbot, tab)
    assert state.priv is None and state.pub == pub


def test_generate_shortcut_is_ctrl_g(tab):
    assert tab.btn_generate.shortcut().toString() == "Ctrl+G"
    assert tab.btn_generate.text() == "Generate key pair"


def test_warning_while_d_is_visible_and_hide_toggle(qtbot, tab, state, monkeypatch):
    shown = []
    monkeypatch.setattr(tab.trace_view, "set_trace", shown.append, raising=False)
    assert tab.warning.isHidden()  # no private key yet -> nothing to warn about
    tab.d_field.setText("7")
    assert not tab.warning.isHidden() and "visible" in tab.warning.text()
    tab.derive()
    wait_idle(qtbot, tab)
    assert not tab.warning.isHidden() and len(shown[-1]) >= 2

    tab.hide_check.setChecked(True)
    assert tab.warning.isHidden()
    assert tab.d_field.echoMode() == tab.d_field.EchoMode.Password
    assert tab.d_field.displayText() != "7" and tab.d_field.value() == 7  # masked, not lost
    assert shown[-1] == [] and "hidden" in tab.trace_note.text()  # the steps contain d
    assert tab.qx_field.text() == "0"  # the public key stays visible

    tab.hide_check.setChecked(False)
    assert not tab.warning.isHidden() and tab.d_field.displayText() == "7"
    assert len(shown[-1]) >= 2


def test_no_warning_for_a_public_key_only(qtbot, tab, state, toy):
    state.set_keys(None, PublicKey((0, 6), toy))
    assert tab.warning.isHidden()


def test_derive_from_typed_d(qtbot, tab, state):
    tab.d_field.setText("7")
    assert tab.btn_derive.isEnabled() and "Compute Q" in tab.d_hint.text()
    with qtbot.waitSignal(state.keysChanged, timeout=10_000):
        tab.btn_derive.click()
    wait_idle(qtbot, tab)
    assert state.priv.d == 7 and state.pub.Q == (0, 6)
    assert tab.qx_field.text() == "0" and tab.qy_field.text() == "6"
    assert tab.compressed_field.hex_value() == "0200"
    assert tab.uncompressed_field.hex_value() == "040006"


def test_trace_is_shown_after_computation(qtbot, tab, state, monkeypatch):
    shown = []
    monkeypatch.setattr(tab.trace_view, "set_trace", shown.append, raising=False)
    tab.d_field.setText("7")
    tab.derive()
    wait_idle(qtbot, tab)
    assert shown and len(shown[-1]) >= 2 and "Q = d * G" in shown[-1][-1].title


@pytest.mark.parametrize("text", ["0", "19", "abc", "-4"])
def test_invalid_d_is_explained_and_blocked(qtbot, tab, state, text):
    tab.d_field.setText(text)
    assert not tab.btn_derive.isEnabled()
    assert "Not a valid private key" in tab.d_hint.text()
    tab.derive()  # e.g. Enter pressed: must do nothing harmful
    assert state.priv is None and not tab._busy


def test_hex_toggle_and_real_curve(qtbot, tab, state):
    state.set_curve(get_curve("secp256k1"))
    assert tab.hex_check.isChecked()  # hex is the default on real curves
    tab.generate()
    wait_idle(qtbot, tab)
    assert tab.d_field.text() == hex(state.priv.d)
    assert len(tab.compressed_field.hex_value()) == 66
    tab.hex_check.setChecked(False)
    assert tab.d_field.text() == str(state.priv.d) and tab.qx_field.text() == str(state.pub.Q[0])
    assert tab.d_field.value() == state.priv.d


def test_curve_change_clears_the_tab(qtbot, tab, state):
    tab.d_field.setText("7")
    tab.derive()
    wait_idle(qtbot, tab)
    state.set_curve(get_curve("toy-97"))
    assert tab.d_field.text() == "" and tab.qx_field.text() == "" and tab.compressed_field.hex_value() == ""
    assert not tab.btn_save_priv.isEnabled()
    assert state.priv is None and state.pub is None
    assert tab.status.property("kind") == "warning"  # ...with a notice
    assert "toy-97" in tab.status.text() and "toy-17" in tab.status.text() and "cleared" in tab.status.text()
    toy97 = get_curve("toy-97")
    tab.d_field.setText(str(toy97.n - 1))  # largest valid d on toy-97; too big for toy-17 (n = 19)
    assert tab.btn_derive.isEnabled()


def test_result_for_an_old_curve_is_dropped(qtbot, tab, state):
    """Switching curve while a job runs must not install keys of the old curve."""
    tab.d_field.setText("7")
    tab.derive()
    state.set_curve(get_curve("toy-97"))  # before the job's answer is delivered
    qtbot.wait(300)
    assert state.priv is None and state.pub is None and not tab._busy


def test_curve_change_without_keys_gives_no_notice(tab, state):
    state.set_curve(get_curve("toy-97"))
    assert tab.status.text() == ""


def test_set_curve_called_directly_clears_stale_keys(qtbot, tab, state, toy):
    """Even if only the page is told about a new curve, keys of the old one must go."""
    state.set_keys(PrivateKey(7, toy), PublicKey((0, 6), toy))
    tab.set_curve(get_curve("toy-97"))
    assert state.priv is None and state.pub is None and tab.d_field.text() == ""
    assert "cleared" in tab.status.text()


def test_save_error_is_shown_in_a_message_box(qtbot, tab, state, tmp_path, monkeypatch, boxes):
    tab.d_field.setText("7")
    tab.derive()
    wait_idle(qtbot, tab)
    bad_path = str(tmp_path / "no_such_folder" / "priv.json")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (bad_path, ""))
    tab.save_private_key_dialog()
    tab.save_public_key_dialog()
    assert [title for title, _ in boxes] == ["Could not save the private key", "Could not save the public key"]


def test_keys_set_elsewhere_show_up(qtbot, tab, state, toy):
    state.set_keys(PrivateKey(2, toy), PublicKey((6, 3), toy))
    assert tab.d_field.value() == 2 and tab.compressed_field.hex_value() == "0306"


@pytest.mark.parametrize("text", ["0200", "04 00 06", "0x0200"])
def test_import_public_key_hex(qtbot, tab, state, text):
    tab.import_field.set_hex(text)
    assert tab.btn_import.isEnabled()
    with qtbot.waitSignal(state.keysChanged, timeout=10_000):
        tab.btn_import.click()
    wait_idle(qtbot, tab)
    assert state.priv is None and state.pub.Q == (0, 6)
    assert tab.d_field.text() == "" and "Public key only" in tab.d_hint.text()
    assert tab.btn_save_pub.isEnabled() and not tab.btn_save_priv.isEnabled()


@pytest.mark.parametrize("text", ["040007", "0201", "0500"])
def test_import_rejects_points_that_are_not_on_the_curve(qtbot, tab, state, text):
    tab.import_field.set_hex(text)
    tab.import_public_hex()
    wait_idle(qtbot, tab)
    assert state.pub is None and tab.status.property("kind") == "error"


def test_copy_buttons(qtbot, tab, state, qapp):
    tab.d_field.setText("7")
    tab.derive()
    wait_idle(qtbot, tab)
    tab.uncompressed_field.copy_button.click()
    assert qapp.clipboard().text() == "040006"
    tab.compressed_field.copy_button.click()
    assert qapp.clipboard().text() == "0200"


def test_save_and_load_through_the_dialogs(qtbot, tab, state, tmp_path, monkeypatch):
    priv_path, pub_path = str(tmp_path / "priv.json"), str(tmp_path / "pub.json")
    tab.d_field.setText("7")
    tab.derive()
    wait_idle(qtbot, tab)

    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (priv_path, ""))
    tab.save_private_key_dialog()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (pub_path, ""))
    tab.save_public_key_dialog()
    assert load_private_key(priv_path).d == 7 and load_public_key(pub_path).Q == (0, 6)

    state.clear_keys()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (pub_path, ""))
    tab.load_public_key_dialog()
    wait_idle(qtbot, tab)
    assert state.priv is None and state.pub.Q == (0, 6)

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (priv_path, ""))
    tab.load_private_key_dialog()
    wait_idle(qtbot, tab)
    assert state.priv.d == 7 and state.pub.Q == (0, 6) and tab.d_field.value() == 7


def test_cancelled_dialogs_change_nothing(qtbot, tab, state, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    tab.load_private_key_dialog()
    tab.load_public_key_dialog()
    tab.save_private_key_dialog()  # nothing to save: just a status message
    assert state.priv is None and not tab._busy


def test_loading_a_key_switches_to_its_curve(qtbot, tab, state, tmp_path, monkeypatch):
    k1 = get_curve("secp256k1")
    save_private_key(tmp_path / "k1.json", PrivateKey(12345, k1))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(tmp_path / "k1.json"), ""))
    tab.load_private_key_dialog()
    wait_idle(qtbot, tab)
    assert state.curve is k1 and state.priv.d == 12345
    assert tab.d_field.value() == 12345 and tab.hex_check.isChecked()


def test_loading_a_key_on_a_custom_curve_registers_the_curve(qtbot, tab, state, tmp_path, monkeypatch):
    save_public_key(tmp_path / "c.json", PublicKey((0, 6), CUSTOM))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(tmp_path / "c.json"), ""))
    tab.load_public_key_dialog()
    wait_idle(qtbot, tab)
    assert state.curve == CUSTOM and "my-curve" in state.available_curves()
    assert state.pub.Q == (0, 6)


def test_loading_a_bad_file_shows_a_warning(qtbot, tab, state, tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text("this is not a key", encoding="utf-8")
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: warnings.append((title, text)))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(bad), ""))
    tab.load_private_key_dialog()
    wait_idle(qtbot, tab)
    tab.load_public_key_dialog()
    wait_idle(qtbot, tab)
    assert len(warnings) == 2 and "private key" in warnings[0][0] and state.pub is None
    assert tab.btn_generate.isEnabled()  # the tab is usable again


# ================================================== CustomCurveDialog
@pytest.fixture
def boxes(monkeypatch) -> list:
    """Record QMessageBox.warning calls (title, text) instead of opening a modal box."""
    shown: list = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: shown.append((title, text)))
    return shown


@pytest.fixture
def dialog(qtbot, state) -> CustomCurveDialog:
    dlg = CustomCurveDialog(state)
    qtbot.addWidget(dlg)
    return dlg


def _fill(dlg: CustomCurveDialog, p, a, b, gx, gy) -> None:
    for field, value in zip(dlg._fields, (p, a, b, gx, gy)):
        field.setText(str(value))


def _wait_dialog(qtbot, dlg) -> None:
    qtbot.waitUntil(lambda: not dlg._busy, timeout=10_000)


def test_dialog_layout_and_help_text(dialog):
    assert [type(f).__name__ for f in dialog._fields] == ["BigIntField"] * 5
    assert dialog.help_label.text() == "p must be prime and < 5000, G must lie on the curve."
    assert list(dialog.preset_buttons) == ["toy-17", "toy-97"]
    assert dialog.btn_example is dialog.preset_buttons["toy-97"]
    assert dialog.curve() is None and not dialog.btn_ok.isEnabled()  # nothing filled in yet


def test_try_toy97_values_fills_the_fields(dialog):
    toy97 = get_curve("toy-97")
    dialog.btn_example.click()
    assert [f.value() for f in dialog._fields] == [toy97.p, toy97.a, toy97.b, *toy97.G]
    assert f"mod {toy97.p}" in dialog.equation_label.text() and dialog.btn_ok.isEnabled()


def test_valid_input_creates_the_curve_and_closes_the_dialog(qtbot, dialog, boxes):
    _fill(dialog, 17, 2, 2, 5, 1)
    with qtbot.waitSignal(dialog.accepted, timeout=10_000):
        dialog.btn_ok.click()
    curve = dialog.curve()
    assert (curve.p, curve.a, curve.b, curve.G, curve.n, curve.h) == (17, 2, 2, (5, 1), 19, 1)
    assert curve.name not in CURVES and boxes == []


def test_toy97_values_are_accepted(qtbot, dialog, boxes):
    dialog.fill_example()
    with qtbot.waitSignal(dialog.accepted, timeout=10_000):
        dialog.create_curve()
    toy97 = get_curve("toy-97")
    assert (dialog.curve().n, dialog.curve().h) == (toy97.n, toy97.h) and boxes == []


@pytest.mark.parametrize(
    "params, expected_in_message",
    [
        ((15, 2, 2, 5, 1), "prime"),  # p is not prime
        ((17, 2, 2, 5, 2), "not on the curve"),  # G is not on the curve
        ((17, 0, 0, 0, 0), "singular"),  # singular curve
    ],
)
def test_invalid_input_shows_the_cores_error_message(qtbot, dialog, boxes, params, expected_in_message):
    """A ValueError from make_custom_curve is shown in a message box, word for word."""
    try:
        make_custom_curve(*params[:3], params[3:])
    except ValueError as exc:
        core_message = str(exc)
    _fill(dialog, *params)
    dialog.btn_ok.click()
    _wait_dialog(qtbot, dialog)
    qtbot.waitUntil(lambda: bool(boxes), timeout=5000)
    assert boxes == [("Not a usable curve", core_message)]
    assert expected_in_message in core_message
    assert dialog.curve() is None and dialog.result() != CustomCurveDialog.DialogCode.Accepted
    assert dialog.btn_ok.isEnabled()  # the student can correct the numbers and try again


@pytest.mark.parametrize(
    "params, expected",
    [
        ((23, 1, 1, 0, 1), "not prime"),  # G has composite order 28
        ((23, 1, 1, 4, 0), "only has order n = 2"),  # G has order 2
    ],
)
def test_base_point_without_a_usable_order_is_rejected(qtbot, dialog, boxes, params, expected):
    _fill(dialog, *params)
    dialog.create_curve()
    qtbot.waitUntil(lambda: bool(boxes), timeout=10_000)
    assert expected in boxes[0][1] and dialog.curve() is None


def test_prime_order_subgroup_is_accepted(qtbot, dialog, boxes):
    _fill(dialog, 23, 1, 1, 5, 4)  # 28 points, G of order 7, cofactor 4
    with qtbot.waitSignal(dialog.accepted, timeout=10_000):
        dialog.create_curve()
    assert (dialog.curve().n, dialog.curve().h) == (7, 4)


def test_mistyped_field_blocks_ok_and_is_explained(dialog, boxes):
    _fill(dialog, "17", "two", "2", "5", "1")
    assert not dialog.btn_ok.isEnabled() and "a:" in dialog.hint_label.text()
    assert dialog.a_field.property("invalid") is True
    dialog.create_curve()  # e.g. Enter pressed: nothing is sent to the core
    assert not dialog._busy and boxes == []


def test_start_from_toy17_fills_the_fields(dialog):
    toy = get_curve("toy-17")
    dialog.preset_buttons["toy-17"].click()
    assert [f.value() for f in dialog._fields] == [toy.p, toy.a, toy.b, *toy.G]
    assert dialog.p_hint.property("kind") == "ok" and dialog.g_hint.property("kind") == "ok"


@pytest.mark.parametrize(
    "p_text, kind, words",
    [
        ("", "info", "prime number from 5"),
        ("abc", "error", "whole number"),
        ("3", "error", "at least 5"),
        ("15", "error", "15 is not a prime"),
        ("6007", "error", "below 5000"),
        ("97", "ok", "✓"),
    ],
)
def test_live_hint_under_p(dialog, p_text, kind, words):
    dialog.p_field.setText(p_text)
    assert dialog.p_hint.property("kind") == kind and words in dialog.p_hint.text()


@pytest.mark.parametrize(
    "params, kind, words",
    [
        ((17, 2, 2, 5, 1), "ok", "lies on this curve"),
        ((17, 2, 2, 5, 2), "error", "not on this curve"),
        ((17, 2, 2, 17, 1), "error", "between 0 and p - 1"),
        ((15, 2, 2, 5, 1), "info", "Pick a point"),  # p is wrong: first fix p
    ],
)
def test_live_hint_under_g(dialog, params, kind, words):
    _fill(dialog, *params)
    assert dialog.g_hint.property("kind") == kind and words in dialog.g_hint.text()


def test_hints_do_not_block_ok(qtbot, dialog, boxes):
    """A hint is advice: OK still asks the core, which explains the problem in a box."""
    _fill(dialog, 17, 2, 2, 5, 2)
    assert dialog.g_hint.property("kind") == "error" and dialog.btn_ok.isEnabled()
    dialog.btn_ok.click()
    qtbot.waitUntil(lambda: bool(boxes), timeout=10_000)
    assert boxes[0][0] == "Not a usable curve"


def test_second_custom_curve_gets_its_own_name(qtbot, state, boxes):
    names = []
    for params in ((17, 2, 2, 5, 1), (23, 1, 1, 5, 4), (17, 2, 2, 5, 1)):
        dlg = CustomCurveDialog(state)
        qtbot.addWidget(dlg)
        _fill(dlg, *params)
        with qtbot.waitSignal(dlg.accepted, timeout=10_000):
            dlg.create_curve()
        state.register_curve(dlg.curve())
        names.append(dlg.curve().name)
    assert names[0] != names[1] and names[2] == names[0]  # same curve again -> same entry
    assert len(state.custom_curves) == 2


# ========================================================== MainWindow
# (The shell itself is tested in test_app_shell.py; here: the real Keys page inside it.)
@pytest.fixture
def window(qtbot, state) -> MainWindow:
    win = MainWindow(state)
    qtbot.addWidget(win)
    return win


def test_main_window_shows_the_real_keys_page(window):
    assert isinstance(window.pages["Keys"], KeysTab)
    window.show_page("Keys")
    assert window.stack.currentWidget() is window.pages["Keys"]


def test_curve_selector_reaches_the_keys_page(qtbot, window, state):
    combo = window.curve_combo
    assert [combo.itemText(i) for i in range(len(CURVES))] == list(CURVES)
    index = combo.findText("secp256k1")
    combo.setCurrentIndex(index)
    combo.activated.emit(index)  # what a user click sends
    assert state.curve.name == "secp256k1"
    assert window.pages["Keys"]._curve is state.curve  # the page was told via set_curve


def test_status_bar_follows_the_keys_page(qtbot, window, state):
    keys_page = window.pages["Keys"]
    keys_page.generate()
    wait_idle(qtbot, keys_page)
    assert "key pair ready" in window.status_keys.text()


def test_status_bar_busy_indicator(qtbot, window):
    window.show()
    qtbot.waitExposed(window)
    assert not window.busy_bar.isVisible()
    release, results = threading.Event(), []
    run_in_background(release.wait, 5, on_done=results.append, on_error=results.append)
    assert window.busy_bar.isVisible()
    release.set()
    qtbot.waitUntil(lambda: bool(results), timeout=5000)
    assert not window.busy_bar.isVisible()


def test_file_menu_has_key_actions(window):
    file_menu = window.menuBar().actions()[0].menu()
    texts = [a.text().replace("&", "") for a in file_menu.actions() if not a.isSeparator()]
    assert texts == ["Load private key…", "Load public key…", "Save private key…", "Save public key…",
                     "Custom curve…", "Quit"]


def test_custom_curve_entry_opens_the_real_dialog(qtbot, window, state, monkeypatch):
    opened = []

    def fake_exec(dialog):
        opened.append(dialog)
        dialog._curve = CUSTOM  # as if the user had checked a curve and pressed OK
        return 1

    monkeypatch.setattr(CustomCurveDialog, "exec", fake_exec)
    index = window.curve_combo.findText("Custom curve…")
    window.curve_combo.setCurrentIndex(index)
    window.curve_combo.activated.emit(index)
    assert len(opened) == 1 and isinstance(opened[0], CustomCurveDialog)
    assert state.curve == CUSTOM and window.curve_combo.currentText() == "my-curve"
    assert window.pages["Keys"]._curve == CUSTOM


def _use_custom_entry(window) -> None:
    index = window.curve_combo.findText("Custom curve…")
    window.curve_combo.setCurrentIndex(index)
    window.curve_combo.activated.emit(index)  # what a user click sends


def test_valid_custom_curve_is_added_to_the_selector_and_selected(qtbot, window, state, monkeypatch, boxes):
    def fake_exec(dialog):  # the "user": types valid numbers and presses OK
        _fill(dialog, 23, 1, 1, 5, 4)
        dialog.btn_ok.click()
        qtbot.waitUntil(lambda: dialog.result() == CustomCurveDialog.DialogCode.Accepted, timeout=10_000)
        return dialog.result()

    monkeypatch.setattr(CustomCurveDialog, "exec", fake_exec)
    before = window.curve_combo.count()
    _use_custom_entry(window)
    curve = state.curve
    assert (curve.p, curve.n, curve.h) == (23, 7, 4) and boxes == []
    texts = [window.curve_combo.itemText(i) for i in range(window.curve_combo.count())]
    assert window.curve_combo.count() == before + 1 and curve.name in texts
    assert window.curve_combo.currentText() == curve.name  # selected
    assert "n = 7" in window.status_curve.text() and "h = 4" in window.status_curve.text()
    assert "n = 7, h = 4" in window.statusBar().currentMessage()
    assert window.pages["Keys"]._curve == curve  # every page was told


def test_invalid_custom_curve_shows_the_error_and_changes_nothing(qtbot, window, state, monkeypatch, boxes):
    def fake_exec(dialog):  # the "user": G not on the curve, OK, reads the error, cancels
        _fill(dialog, 17, 2, 2, 5, 2)
        dialog.btn_ok.click()
        qtbot.waitUntil(lambda: bool(boxes), timeout=10_000)
        dialog.reject()
        return dialog.result()

    monkeypatch.setattr(CustomCurveDialog, "exec", fake_exec)
    before = window.curve_combo.count()
    _use_custom_entry(window)
    assert len(boxes) == 1 and boxes[0][0] == "Not a usable curve" and "not on the curve" in boxes[0][1]
    assert state.curve.name == "toy-17" and window.curve_combo.count() == before
    assert window.curve_combo.currentText() == "toy-17"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_keys_page_renders_in_both_themes(qapp, qtbot, state, theme):
    from ecdsa_edu.gui.app import apply_theme

    saved = (qapp.styleSheet(), qapp.palette(), qapp.style().objectName(), qapp.property("theme"))
    try:
        apply_theme(qapp, theme)
        win = MainWindow(state)
        qtbot.addWidget(win)
        win.show()
        qtbot.waitExposed(win)
        page = win.pages["Keys"]
        page.d_field.setText("0")  # invalid -> error-coloured hint
        assert page.d_hint.property("kind") == "error"
    finally:
        qapp.setStyleSheet(saved[0])
        qapp.setPalette(saved[1])
        qapp.setStyle(saved[2])
        qapp.setProperty("theme", saved[3])


# ========================================================= Learn pages
def test_learn_keys_page(qtbot, toy):
    """Step 2 plugs into P4's wizard: random d first, typed d works, d and Q go into the state."""
    from ecdsa_edu.gui.learn.model import LearnState
    from ecdsa_edu.gui.learn.pages_keys import PAGES, KeysPage
    from ecdsa_edu.gui.learn.wizard import LearnPage

    assert PAGES == [KeysPage] and issubclass(KeysPage, LearnPage)
    page = KeysPage()
    qtbot.addWidget(page)

    st = LearnState(curve=toy)
    page.enter(st)  # no d yet -> a random one is picked
    assert 1 <= st["d"] <= 18 and st["Q"] == public_from_private(PrivateKey(st["d"], toy)).Q
    assert page.d_field.value() == st["d"]

    page.d_field.setText("7")
    page.use_button.click()
    assert st["d"] == 7 and st["Q"] == (0, 6)
    values = [page.values_table.item(r, 1).text() for r in range(page.values_table.rowCount())]
    assert "(0, 6)" in values and "0200" in values
    assert page.hint.property("kind") == "ok"

    page.d_field.setText("19")  # too big on toy-17: explained, state unchanged
    page.use_button.click()
    assert st["d"] == 7 and page.hint.property("kind") == "error"

    page.enter(st)  # coming back keeps the chosen d
    assert st["d"] == 7 and st["Q"] == (0, 6)


def test_learn_keys_page_without_a_curve(qtbot):
    from ecdsa_edu.gui.learn.model import LearnState
    from ecdsa_edu.gui.learn.pages_keys import KeysPage

    page = KeysPage()
    qtbot.addWidget(page)
    st = LearnState(curve=None)
    page.enter(st)  # falls back to the toy curve
    assert st["curve"].name == "toy-17" and st["Q"] is not None


def test_learn_keys_page_inside_the_wizard(qtbot):
    from ecdsa_edu.gui.learn.model import load_page_modules

    loaded = {m.spec.module: m for m in load_page_modules()}
    assert loaded["pages_keys"].pages is not None, loaded["pages_keys"].error
    assert len(loaded["pages_keys"].pages) == 1  # the wizard expects one keys step
