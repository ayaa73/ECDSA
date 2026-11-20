"""Hex widgets shared by all pages (owner: P2).

* ``HexOutputField`` - read-only, monospace display of a hex string with
  **Copy** and **Save** buttons. Use it for results (public keys, signatures,
  hashes).

      out = HexOutputField(lines=3, save_name="signature")
      out.set_hex("3045...")          # or out.set_bytes(b"...")
      out.hex_value()                 # "3045..."

* ``HexField`` - the plain text box underneath; with ``read_only=False`` it is
  an input that validates what the user pastes.

      field = HexField()
      field.hex_value()               # cleaned-up digits, '' while empty or invalid

Long hex wraps over a few lines instead of scrolling sideways. Input may contain
spaces, colons or a leading 0x.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFontDatabase, QFontMetrics, QTextOption
from PySide6.QtWidgets import QApplication, QFileDialog, QHBoxLayout, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

__all__ = ["HexOutputField", "HexField", "normalize_hex"]

_HEX = set("0123456789abcdef")


def normalize_hex(text: str) -> str:
    """Strip spaces / colons / 0x and lowercase. Raises ValueError if not whole bytes of hex."""
    t = "".join(text.split()).replace(":", "").lower()
    if t.startswith("0x"):
        t = t[2:]
    if any(ch not in _HEX for ch in t):
        raise ValueError("only hex digits 0-9 and a-f are allowed")
    if len(t) % 2:
        raise ValueError("odd number of hex digits (each byte needs two)")
    return t


class HexField(QPlainTextEdit):
    """Wrapping, monospace hex editor/display with live validation."""

    valueChanged = Signal(str)  # normalised hex, '' while empty or invalid

    def __init__(self, parent: QWidget | None = None, *, read_only: bool = False, lines: int = 2) -> None:
        super().__init__(parent)
        self._hex = ""
        self._error = ""
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.setFont(font)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)
        self.setTabChangesFocus(True)
        self.setReadOnly(read_only)
        if not read_only:
            self.setPlaceholderText("hex, e.g. 02a1b2c3...")
        # Fixed height of `lines` text lines.
        line_height = QFontMetrics(font).lineSpacing()
        self.setFixedHeight(lines * line_height + 30)  # + frame, padding, document margin
        self.textChanged.connect(self._revalidate)

    # ---------------------------------------------------------------- API
    def hex_value(self) -> str:
        """Clean lowercase hex without separators ('' if empty or invalid)."""
        return self._hex

    def bytes_value(self) -> bytes | None:
        """The content as bytes, or None if empty or invalid."""
        return bytes.fromhex(self._hex) if self._hex else None

    def is_valid(self) -> bool:
        return bool(self._hex)

    def error(self) -> str:
        return self._error

    def set_hex(self, text: str) -> None:
        self.setPlainText(text)

    # ----------------------------------------------------------- internals
    def _revalidate(self) -> None:
        value, error = "", ""
        raw = self.toPlainText()
        if raw.strip():
            try:
                value = normalize_hex(raw)
            except ValueError as exc:
                error = str(exc)
        self._error = error
        self.setToolTip(error)
        if self.property("invalid") != bool(error):
            self.setProperty("invalid", bool(error))
            self.style().unpolish(self)
            self.style().polish(self)
        if value != self._hex:
            self._hex = value
            self.valueChanged.emit(value)


class HexOutputField(QWidget):
    """Read-only monospace hex display with Copy and Save buttons."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        lines: int = 2,
        save_name: str = "output",
        show_save: bool = True,
    ) -> None:
        super().__init__(parent)
        self._save_name = save_name
        self.text_field = HexField(read_only=True, lines=lines)
        self.copy_button = QPushButton("Copy")
        self.copy_button.setToolTip("Copy the hex string to the clipboard")
        self.save_button = QPushButton("Save…")
        self.save_button.setToolTip("Save as a text file (hex) or as raw bytes")
        self.save_button.setVisible(show_save)

        buttons = QVBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addWidget(self.copy_button)
        buttons.addWidget(self.save_button)
        buttons.addStretch(1)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.text_field, 1)
        layout.addLayout(buttons)

        self.copy_button.clicked.connect(self.copy)
        self.save_button.clicked.connect(self.save_dialog)
        self.text_field.valueChanged.connect(self._update_buttons)
        self._update_buttons()

    # ---------------------------------------------------------------- API
    def set_hex(self, text: str) -> None:
        """Show a hex string ('' clears the field)."""
        self.text_field.set_hex(text)

    def set_bytes(self, data: bytes) -> None:
        self.text_field.set_hex(data.hex())

    def clear(self) -> None:
        self.text_field.set_hex("")

    def hex_value(self) -> str:
        """The displayed hex, lowercase and without separators ('' if empty)."""
        return self.text_field.hex_value()

    def bytes_value(self) -> bytes | None:
        return self.text_field.bytes_value()

    def setAccessibleName(self, name: str) -> None:  # noqa: N802 (Qt naming)
        self.text_field.setAccessibleName(name)

    def copy(self) -> None:
        """Copy the hex string to the clipboard and confirm on the button."""
        if not self.hex_value():
            return
        QApplication.clipboard().setText(self.hex_value())
        self.copy_button.setText("Copied ✓")
        QTimer.singleShot(1200, self, lambda: self.copy_button.setText("Copy"))

    def save_dialog(self) -> None:
        """Ask for a file name and save the value there."""
        if not self.hex_value():
            return
        path, chosen = QFileDialog.getSaveFileName(
            self, "Save", f"{self._save_name}.txt", "Hex text (*.txt);;Raw bytes (*.bin)"
        )
        if not path:
            return
        try:
            self.save_to(path, raw=chosen.startswith("Raw") or path.lower().endswith(".bin"))
        except OSError as exc:
            QMessageBox.warning(self, "Could not save the file", exc.strerror or str(exc))

    def save_to(self, path, *, raw: bool = False) -> None:
        """Write the value to ``path``: hex text by default, the bytes themselves if ``raw``."""
        if raw:
            Path(path).write_bytes(self.bytes_value() or b"")
        else:
            Path(path).write_text(self.hex_value() + "\n", encoding="utf-8")

    # ----------------------------------------------------------- internals
    def _update_buttons(self) -> None:
        has_value = bool(self.hex_value())
        self.copy_button.setEnabled(has_value)
        self.save_button.setEnabled(has_value)
