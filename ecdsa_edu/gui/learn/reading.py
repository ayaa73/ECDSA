"""Longer "Go deeper" reading for the Learn ECDSA steps (P4).

The HTML files in ``reading/`` hold the background theory that the short step
texts leave out: the group law, double-and-add, key encodings, why
verification works, the classic pitfalls and a glossary. ``ReadingView``
shows one file at its full height (no scrollbar of its own), so the page's
single scrollbar moves through the step and its reading together.
Formula images live in ``reading/img`` (made by ``build_formulas.py``).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QFrame, QSizePolicy, QTextBrowser, QWidget

from ecdsa_edu.gui.app import current_theme, theme_colors

__all__ = ["READING_DIR", "ReadingView", "reading_css"]

READING_DIR = Path(__file__).parent / "reading"


def reading_css(colors: dict[str, str]) -> str:
    """Document style for the reading text, in the colours of the current theme."""
    return f"""
body  {{ font-size: 11pt; color: {colors['text']}; }}
h2    {{ font-size: 14pt; color: {colors['heading']}; margin-top: 16px; }}
h3    {{ font-size: 12pt; color: {colors['heading']}; margin-top: 12px; }}
code, pre {{ font-family: Consolas, 'Courier New', monospace; background: {colors['input_readonly']}; }}
table {{ border-collapse: collapse; }}
td, th {{ border: 1px solid {colors['border']}; padding: 5px 9px; }}
th    {{ background: {colors['hover']}; }}
.note {{ background: {colors['hover']}; padding: 8px 12px; }}
.warn {{ background: {colors['invalid']}; padding: 8px 12px; }}
"""


class ReadingView(QTextBrowser):
    """Read-only HTML that grows to fit its text instead of scrolling inside the page."""

    def __init__(self, file_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.file_name = file_name
        self.setObjectName("learnReading")
        self.setOpenExternalLinks(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSearchPaths([str(READING_DIR)])
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._load()

    def html_source(self) -> str:
        return (READING_DIR / self.file_name).read_text(encoding="utf-8")

    def _load(self) -> None:
        self.document().setDefaultStyleSheet(reading_css(theme_colors(current_theme())))
        self.setHtml(self.html_source())
        self._fit_height()

    def _fit_height(self) -> None:
        width = self.viewport().width()
        if width <= 0:
            return
        self.document().setTextWidth(width)
        margins = self.contentsMargins()
        self.setFixedHeight(int(self.document().size().height()) + margins.top() + margins.bottom() + 4)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        if event.oldSize().width() != event.size().width():
            self._fit_height()

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        self._fit_height()

    def changeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self._load()  # light/dark theme switched: rebuild with the new colours

    def wheelEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        event.ignore()  # nothing to scroll here: let the page scroll
