"""Embedded version of the ECDSA signature-verification investigation game."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QUrlQuery
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

__all__ = ["VerificationGameTab"]


class VerificationGameTab(QWidget):
    """Load the self-contained HTML game when its sidebar page is first shown."""

    HELP = (
        "Choose a difficulty, inspect each suspect's public key, and use ECDSA "
        "verification to decide who signed the threat. The game uses the toy-97 "
        "curve so every calculation is small enough to follow by hand."
    )

    def __init__(self, state, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view = None
        self._active = False
        self._loaded = False

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._loading = QLabel("Loading verification game…")
        self._loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._loading)

    def activate(self) -> None:
        """Load/start the game only after the player actually selects its tab."""
        self._active = True
        self._ensure_view()
        self._start_intro()

    def deactivate(self) -> None:
        self._active = False

    def _ensure_view(self) -> None:
        if self._view is not None:
            return

        try:
            from PySide6.QtWebEngineCore import QWebEngineSettings
            from PySide6.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            self._loading.setText(
                "The verification game requires the Qt WebEngine component.\n"
                "Install the full PySide6 package, then restart ECDSA Lab."
            )
            return

        game_path = Path(__file__).with_name("case_file_signed_threat.html").resolve()
        if not game_path.is_file():
            self._loading.setText(f"Verification game file is missing:\n{game_path}")
            return

        view = QWebEngineView(self)
        view.page().setBackgroundColor(Qt.GlobalColor.transparent)
        view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        view.setAccessibleName("ECDSA verification investigation game")
        view.loadFinished.connect(self._on_load_finished)
        url = QUrl.fromLocalFile(str(game_path))
        url.setQuery(QUrlQuery("embedded=1&autostart=0"))
        view.load(url)

        self._layout.replaceWidget(self._loading, view)
        self._loading.deleteLater()
        self._view = view

    def _on_load_finished(self, ok: bool) -> None:
        self._loaded = ok
        self._start_intro()

    def _start_intro(self) -> None:
        if self._active and self._loaded and self._view is not None:
            self._view.page().runJavaScript(
                "window.startEmbeddedGame && window.startEmbeddedGame()"
            )

    def set_curve(self, _curve) -> None:
        """The investigation intentionally stays on its small built-in toy curve."""

