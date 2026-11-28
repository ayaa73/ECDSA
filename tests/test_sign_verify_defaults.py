"""SHA-512 by default in Sign and Verify, and the shared 10 MB file limit."""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog

from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.keys import public_from_private
from ecdsa_edu.core.types import PrivateKey
from ecdsa_edu.gui.app_state import AppState
from ecdsa_edu.gui.tabs.sign_tab import SignTab
from ecdsa_edu.gui.tabs.verify_tab import VerifyTab
from ecdsa_edu.gui.widgets.file_limits import (
    FILE_LIMIT_TEXT, MAX_FILE_BYTES, file_size_problem, format_size,
)

WAIT = 15_000


def _state(curve_name: str = "toy-17") -> AppState:
    curve = get_curve(curve_name)
    state = AppState(curve=curve, settings=QSettings())
    priv = PrivateKey(7, curve)
    state.set_keys(priv, public_from_private(priv))
    return state


def _big_file(tmp_path, size):
    path = tmp_path / "big.bin"
    with open(path, "wb") as f:
        f.truncate(size)  # sparse: instant, uses no disk space
    return path


def test_limit_is_10_mb_and_explained():
    assert MAX_FILE_BYTES == 10 * 1024 * 1024
    assert FILE_LIMIT_TEXT == "Any file type · max 10 MB"
    assert format_size(MAX_FILE_BYTES) == "10 MB" and format_size(1536) == "1.5 KB" and format_size(12) == "12 bytes"


def test_file_size_problem(tmp_path):
    assert file_size_problem(_big_file(tmp_path, MAX_FILE_BYTES)) == ""
    problem = file_size_problem(_big_file(tmp_path, MAX_FILE_BYTES + 1))
    assert "10 MB" in problem and "limit" in problem
    assert "could not be read" in file_size_problem(tmp_path / "missing.bin")


def test_sign_defaults_to_sha512(qtbot):
    tab = SignTab(_state())
    qtbot.addWidget(tab)
    labels = [tab.hash_combo.itemText(i) for i in range(tab.hash_combo.count())]
    assert tab.hash_combo.currentData() == "sha512"
    assert tab.hash_combo.currentText() == "SHA-512 (recommended)"
    assert "SHA-256" in labels and "SHA-256 (recommended)" not in labels
    assert {tab.hash_combo.itemData(i) for i in range(tab.hash_combo.count())} == {"sha512", "sha384", "sha256",
                                                                                   "sha1"}
    assert tab.file_limit_label.text() == FILE_LIMIT_TEXT


def test_sign_rejects_a_file_over_10_mb_and_keeps_the_previous_one(qtbot, tmp_path, monkeypatch):
    tab = SignTab(_state())
    qtbot.addWidget(tab)
    small = tmp_path / "small.txt"
    small.write_bytes(b"ok")
    big = _big_file(tmp_path, MAX_FILE_BYTES + 1)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(small), ""))
    tab.choose_file()
    assert tab._file_path == str(small)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(big), ""))
    tab.choose_file()
    assert tab._file_path == str(small)  # previous selection kept
    assert "10 MB" in tab.status.text() and "big.bin" in tab.status.text()
    assert tab.status.property("kind") == "error"


def test_verify_rejects_a_file_over_10_mb(qtbot, tmp_path, monkeypatch):
    tab = VerifyTab(_state())
    qtbot.addWidget(tab)
    assert tab.file_limit_label.text() == FILE_LIMIT_TEXT
    big = _big_file(tmp_path, MAX_FILE_BYTES + 5)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(big), ""))
    tab._choose_file()
    assert tab._file_path is None and tab.msg_edit.isEnabled()
    assert tab.banner.headline == "File too large"


def test_verify_uses_the_hash_the_signature_was_made_with(qtbot):
    state = _state()
    sign_tab, verify_tab = SignTab(state), VerifyTab(state)
    qtbot.addWidget(sign_tab)
    qtbot.addWidget(verify_tab)
    assert verify_tab.hash_combo.currentData() == "sha512"  # same default before anything is signed

    sign_tab.message_edit.setPlainText("hello")
    sign_tab.hash_combo.setCurrentIndex(sign_tab.hash_combo.findData("sha384"))
    sign_tab.sign_button.click()
    qtbot.waitUntil(lambda: state.last_sig is not None, timeout=WAIT)
    assert state.last_hash == "sha384"
    assert verify_tab.hash_combo.currentData() == "sha384"
    verify_tab.run_verify()
    qtbot.waitUntil(lambda: verify_tab.banner.headline in ("VALID", "INVALID"), timeout=WAIT)
    assert verify_tab.banner.headline == "VALID"


def test_full_run_sha512_text_and_file_valid_then_tampered(qtbot, tmp_path, monkeypatch):
    """keygen -> sign a text and a file with SHA-512 -> verify valid -> tamper -> invalid."""
    for curve_name in ("toy-17", "P-256"):
        state = _state(curve_name)
        sign_tab, verify_tab = SignTab(state), VerifyTab(state)
        qtbot.addWidget(sign_tab)
        qtbot.addWidget(verify_tab)
        sign_tab.message_edit.setPlainText("Pay Bob 10 coins")
        sign_tab.sign_button.click()
        qtbot.waitUntil(lambda: state.last_sig is not None, timeout=WAIT)
        assert state.last_hash == "sha512"
        verify_tab.run_verify()
        qtbot.waitUntil(lambda: not verify_tab._busy and verify_tab.banner.headline == "VALID", timeout=WAIT)
        verify_tab.tamper_and_verify()
        qtbot.waitUntil(lambda: not verify_tab._busy and verify_tab.banner.headline == "INVALID", timeout=WAIT)

        document = tmp_path / f"{curve_name}.pdf"
        document.write_bytes(b"%PDF-1.4 pretend document " * 200)
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(document), ""))
        state.set_signature(None, None)
        sign_tab.choose_file()
        sign_tab.sign_button.click()
        qtbot.waitUntil(lambda: state.last_sig is not None, timeout=WAIT)
        verify_tab._choose_file()
        verify_tab.run_verify()
        qtbot.waitUntil(lambda: not verify_tab._busy and verify_tab.banner.headline == "VALID", timeout=WAIT)
        document.write_bytes(document.read_bytes() + b"!")  # change the file
        verify_tab.run_verify()
        qtbot.waitUntil(lambda: not verify_tab._busy and verify_tab.banner.headline == "INVALID", timeout=WAIT)


def test_selecting_another_file_clears_the_verdict_and_trace(qtbot, tmp_path, monkeypatch):
    from ecdsa_edu.core.sign import sign_file

    state = _state("P-256")
    original = tmp_path / "original.txt"
    original.write_bytes(b"Signed document")
    other = tmp_path / "other.txt"
    other.write_bytes(b"Different document")
    state.set_signature(sign_file(state.priv, original, "sha512"), None, "sha512")
    tab = VerifyTab(state)
    qtbot.addWidget(tab)
    selections = iter((original, other))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(next(selections)), ""))

    tab.file_button.click()
    tab.verify_button.click()
    qtbot.waitUntil(lambda: tab.banner.headline == "VALID", timeout=WAIT)
    tab.show_math.click()
    assert tab.show_math.isChecked()

    tab.file_button.click()
    assert tab.banner.headline == "Inputs changed"
    assert not tab.show_math.isEnabled()
    assert not tab.show_math.isChecked()

    tab.verify_button.click()
    qtbot.waitUntil(lambda: tab.banner.headline == "INVALID", timeout=WAIT)
