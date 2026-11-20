"""A line edit for (very) large integers (owner: P2).

Accepts decimal ("1234") or hexadecimal ("0x4d2") input, validates it while
the user types, and can re-display its value in either base.

    field = BigIntField(minimum=1, maximum=n - 1)
    field.valueChanged.connect(...)     # int, or None while the text is not valid
    d = field.value()                   # int | None
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QLineEdit, QWidget

__all__ = ["BigIntField", "parse_bigint", "format_bigint"]

_DEC = set("0123456789")
_HEX = set("0123456789abcdefABCDEF")


def parse_bigint(text: str) -> int:
    """Parse decimal or 0x-prefixed hex text. Spaces and '_' are ignored.

    Raises ValueError with a message that can be shown to the user.
    """
    t = "".join(text.split()).replace("_", "")
    if not t:
        raise ValueError("enter a number")
    sign = 1
    if t[0] in "+-":
        sign = -1 if t[0] == "-" else 1
        t = t[1:]
    if t[:2].lower() == "0x":
        digits, base, allowed = t[2:], 16, _HEX
    else:
        digits, base, allowed = t, 10, _DEC
    if not digits or any(ch not in allowed for ch in digits):
        raise ValueError("not a number - use decimal digits, or hex starting with 0x")
    try:
        return sign * int(digits, base)
    except ValueError:  # Python refuses absurdly long decimal strings
        raise ValueError("number is too long") from None


def format_bigint(value: int, use_hex: bool) -> str:
    """Render ``value`` in decimal or as 0x-hex."""
    return hex(value) if use_hex else str(value)


class BigIntField(QLineEdit):
    """QLineEdit specialised for big integers with live validation."""

    valueChanged = Signal(object)  # int | None

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
        read_only: bool = False,
    ) -> None:
        super().__init__(parent)
        self._min, self._max = minimum, maximum
        self._value: int | None = None
        self._error = ""
        self._use_hex = False
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.setMaxLength(1400)  # enough for a 521-bit number in any base, with room to spare
        self.setReadOnly(read_only)
        if not read_only:
            self.setPlaceholderText("decimal, or hex starting with 0x")
            self.setClearButtonEnabled(True)
        self.textChanged.connect(self._revalidate)

    # ---------------------------------------------------------------- API
    def value(self) -> int | None:
        """The current number, or None if the field is empty or invalid."""
        return self._value

    def is_valid(self) -> bool:
        return self._value is not None

    def error(self) -> str:
        """Why the current text is rejected ('' if valid or empty)."""
        return self._error

    def set_value(self, value: int | None) -> None:
        """Show ``value`` (None clears the field) in the current display base."""
        self.setText("" if value is None else format_bigint(value, self._use_hex))
        self.setCursorPosition(0)

    def set_range(self, minimum: int | None, maximum: int | None) -> None:
        self._min, self._max = minimum, maximum
        self._revalidate()

    def set_display_hex(self, use_hex: bool) -> None:
        """Choose the base used by set_value(); re-renders the current value."""
        self._use_hex = use_hex
        if self._value is not None:
            self.set_value(self._value)

    # ----------------------------------------------------------- internals
    def _revalidate(self) -> None:
        text = self.text()
        value: int | None = None
        error = ""
        if text.strip():
            try:
                value = parse_bigint(text)
                if self._min is not None and value < self._min:
                    raise ValueError(f"must be at least {self._min}")
                if self._max is not None and value > self._max:
                    raise ValueError(f"must be at most {format_bigint(self._max, self._max > 10**12)}")
            except ValueError as exc:
                value, error = None, str(exc)
        self._error = error
        self.setToolTip(error)
        self._set_invalid_style(bool(error))
        if value != self._value:
            self._value = value
            self.valueChanged.emit(value)

    def _set_invalid_style(self, invalid: bool) -> None:
        """Toggle the ``invalid`` property used by the app stylesheet (red border)."""
        if self.property("invalid") != invalid:
            self.setProperty("invalid", invalid)
            self.style().unpolish(self)
            self.style().polish(self)
