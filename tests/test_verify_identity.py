"""Verify: the signer's identity as a public key OR a certificate (exported from Keys)."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog

from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.key_io import point_to_hex
from ecdsa_edu.core.keys import generate_keypair
from ecdsa_edu.core.sign import sign
from ecdsa_edu.gui.app_state import AppState
from ecdsa_edu.gui.tabs.keys_tab import KeysTab
from ecdsa_edu.gui.tabs.verify_tab import CERTIFICATE_MODE, PASTE, PUBLIC_KEY_MODE, VerifyTab
from ecdsa_edu.gui.widgets.file_limits import MAX_FILE_BYTES

WAIT = 15_000


def _verdict(qtbot, tab) -> str:
    tab.banner.show_message("info", "", "")
    tab.run_verify()
    qtbot.waitUntil(lambda: not tab._busy and tab.banner.headline != "", timeout=WAIT)
    return tab.banner.headline


@pytest.fixture
def p256_state(qapp):
    return AppState(curve=get_curve("P-256"), settings=QSettings())


def test_full_certificate_flow_from_keys_to_verify(qtbot, p256_state, tmp_path, monkeypatch):
    state = p256_state
    keys, verify = KeysTab(state), VerifyTab(state)
    qtbot.addWidget(keys)
    qtbot.addWidget(verify)
    assert not keys.btn_export_cert.isEnabled()  # no key yet
    keys.generate()
    qtbot.waitUntil(lambda: not keys._busy, timeout=WAIT)
    assert keys.btn_export_cert.isEnabled() and keys.cert_note.isHidden()

    for name in ("alice.pem", "alice.der"):
        path = tmp_path / name
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, p=path, **k: (str(p), ""))
        keys.export_certificate_dialog()
        assert path.exists() and "Certificate saved" in keys.status.text()
    assert (tmp_path / "alice.pem").read_text().startswith("-----BEGIN CERTIFICATE-----")
    assert (tmp_path / "alice.der").read_bytes()[:1] == b"\x30"

    state.set_signature(sign(state.priv, b"Hello Bob", "sha512"), b"Hello Bob", "sha512")
    verify.certificate_button.click()
    assert verify.identity_mode() == CERTIFICATE_MODE
    assert verify.cert_panel.isVisibleTo(verify) and not verify.key_panel.isVisibleTo(verify)
    assert _verdict(qtbot, verify) == "Not ready yet" and "certificate first" in verify.banner.text()

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(tmp_path / "alice.der"), ""))
    verify._load_certificate()
    assert verify.banner.headline == "Certificate loaded"
    text = verify.cert_status.text()
    assert "ECDSA Lab key" in text and "P-256" in text and "valid (self-signed)" in text
    assert _verdict(qtbot, verify) == "VALID"
    verify._set_message("Hello Eve")
    assert _verdict(qtbot, verify) == "INVALID"


def test_certificate_mode_is_greyed_out_on_toy_curves(qtbot):
    state = AppState(curve=get_curve("toy-17"), settings=QSettings())
    verify, keys = VerifyTab(state), KeysTab(state)
    qtbot.addWidget(verify)
    qtbot.addWidget(keys)
    assert not verify.certificate_button.isEnabled() and not verify.cert_note.isHidden()
    assert "secp256k1 and P-256" in verify.cert_note.text()
    keys.generate()
    qtbot.waitUntil(lambda: not keys._busy, timeout=WAIT)
    assert not keys.btn_export_cert.isEnabled() and not keys.cert_note.isHidden()
    state.set_curve(get_curve("secp256k1"))
    verify.set_curve(state.curve)
    assert verify.certificate_button.isEnabled() and verify.cert_note.isHidden()


@pytest.mark.parametrize("name, content, headline", [
    ("notes.txt", b"hello", "Not a certificate file"),
    ("broken.pem", b"-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----\n", "Not a valid certificate"),
    ("random.der", b"\x30\x03\x01\x02", "Not a valid certificate"),
])
def test_wrong_or_corrupt_certificate_files_are_explained(qtbot, p256_state, tmp_path, monkeypatch,
                                                         name, content, headline):
    verify = VerifyTab(p256_state)
    qtbot.addWidget(verify)
    verify.certificate_button.click()
    path = tmp_path / name
    path.write_bytes(content)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(path), ""))
    verify._load_certificate()
    assert verify.banner.headline == headline and verify._certificate is None


def test_certificate_over_10_mb_is_refused(qtbot, p256_state, tmp_path, monkeypatch):
    verify = VerifyTab(p256_state)
    qtbot.addWidget(verify)
    path = tmp_path / "huge.pem"
    with open(path, "wb") as f:
        f.truncate(MAX_FILE_BYTES + 1)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(path), ""))
    verify._load_certificate()
    assert verify.banner.headline == "File too large" and verify._certificate is None


def test_certificate_on_another_curve_asks_to_switch(qtbot, tmp_path, monkeypatch):
    from ecdsa_edu.core.x509 import make_self_signed_certificate, to_pem
    k1 = get_curve("secp256k1")
    priv, pub = generate_keypair(k1)
    path = tmp_path / "bob.crt"
    path.write_text(to_pem(make_self_signed_certificate(priv, pub, "Bob")))
    state = AppState(curve=get_curve("P-256"), settings=QSettings())
    verify = VerifyTab(state)
    qtbot.addWidget(verify)
    verify.certificate_button.click()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(path), ""))
    verify._load_certificate()
    state.set_signature(sign(priv, b"hi", "sha512"), b"hi", "sha512")
    verify._set_message("hi")
    verify.run_verify()
    assert "secp256k1" in verify.banner.text() and "Select that curve" in verify.banner.text()


def test_someone_elses_public_key_can_be_pasted(qtbot):
    state = AppState(curve=get_curve("toy-97"), settings=QSettings())
    verify = VerifyTab(state)
    qtbot.addWidget(verify)
    priv, pub = generate_keypair(state.curve)  # Bob's key: not the app's own
    state.set_signature(sign(priv, b"from Bob", "sha512"), b"from Bob", "sha512")
    assert verify.identity_mode() == PUBLIC_KEY_MODE
    verify.key_source.setCurrentIndex(verify.key_source.findData(PASTE))
    verify._on_key_source()
    assert "Someone else" in verify.key_source.currentText() and verify.key_hex.isVisibleTo(verify)
    verify.key_hex.setText(point_to_hex(state.curve, pub.Q, compressed=True))
    assert _verdict(qtbot, verify) == "VALID"
    verify.key_hex.setText("040102")  # (1, 2) is not a point on toy-97
    assert _verdict(qtbot, verify) == "Check your input"
