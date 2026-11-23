"""Shared pytest setup: run Qt without a display so GUI tests work everywhere."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # must be set before Qt starts


import pytest
from PySide6.QtCore import QSettings


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path):
    """Every test gets its own empty settings store, so the remembered curve, mode or
    window size of one test (or of your own use of the app) never leaks into another."""
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path / "settings"))
    # QSettings("ECDSA Lab", "ECDSA Lab") (used by the Start here page) uses the native format.
    QSettings.setPath(QSettings.Format.NativeFormat, QSettings.Scope.UserScope, str(tmp_path / "native"))
    yield


@pytest.fixture(autouse=True)
def _no_blocking_message_boxes(monkeypatch):
    """A real message box waits for a click, which would freeze a test forever.
    Replace them with versions that return at once. A test that wants to check a
    message box patches it again itself (that patch wins)."""
    from PySide6.QtWidgets import QMessageBox

    ok = QMessageBox.StandardButton.Ok
    for name in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, name, lambda *args, **kwargs: ok)
    monkeypatch.setattr(QMessageBox, "about", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: ok)
    yield
