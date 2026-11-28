"""Demo of the shared widgets with fake data (owner: P2).

    python -m ecdsa_edu.gui.widgets.demo

Opens one window that shows BigIntField, HexField, HexOutputField and
run_in_background, so teammates can see how each one looks and behaves before
using it. Nothing here touches the core: all values are made up.
"""
from __future__ import annotations

import sys
import time

from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ecdsa_edu.gui.app import apply_theme, current_theme
from ecdsa_edu.gui.widgets.bigint_field import BigIntField
from ecdsa_edu.gui.widgets.hex_field import HexField, HexOutputField
from ecdsa_edu.gui.widgets.worker import busy_tracker, run_in_background

# ---- fake data -------------------------------------------------------------
FAKE_N = 19  # order of the toy curve's base point
FAKE_BIG_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
FAKE_PUBLIC_KEY = "04" + "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798" \
                         "483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8"
FAKE_SIGNATURE = "3044022012ab" + "5c" * 28 + "0220" + "7e" * 32


# ---- fake "core" jobs (they only sleep) -------------------------------------
def slow_square(x: int, seconds: float) -> int:
    time.sleep(seconds)
    return x * x


def slow_bad_input(seconds: float) -> int:
    time.sleep(seconds)
    raise ValueError("the private key d must satisfy 1 <= d <= n - 1")


def slow_bug(seconds: float) -> int:
    time.sleep(seconds)
    return 1 // 0  # a programming error, not a user error


def _note(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setProperty("note", True)
    return label


class WidgetsDemo(QWidget):
    """One group box per widget."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ECDSA Lab - shared widgets demo")
        self.resize(760, 780)
        layout = QVBoxLayout(self)
        layout.addWidget(self._bigint_box())
        layout.addWidget(self._hex_box())
        layout.addWidget(self._worker_box())
        self.theme_button = QPushButton("Switch to dark theme")
        self.theme_button.clicked.connect(self._toggle_theme)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.theme_button)
        layout.addLayout(row)
        layout.addStretch(1)

    # --------------------------------------------------------- BigIntField
    def _bigint_box(self) -> QGroupBox:
        box = QGroupBox("BigIntField - decimal or 0x-hex, red border + tooltip when invalid")
        self.small = BigIntField(minimum=1, maximum=FAKE_N - 1)
        self.small.set_value(7)
        self.big = BigIntField(minimum=1, maximum=FAKE_BIG_N - 1)
        self.big.set_display_hex(True)
        self.big.set_value(0x1E99423A4ED27608A15A2616A2B0E9E52CED330AC530EDCC32C8FFC6A526AEDD)
        self.invalid = BigIntField(minimum=1, maximum=FAKE_N - 1)
        self.invalid.setText("19")  # out of range on purpose
        self.free = BigIntField()  # no range check
        self.value_label = QLabel()
        self.value_label.setProperty("mono", True)

        form = QFormLayout(box)
        form.addRow("Range [1, 18]", self.small)
        form.addRow("Range [1, n-1], 256-bit", self.big)
        form.addRow("Invalid on purpose", self.invalid)
        form.addRow("No range check", self.free)
        form.addRow(".value() of the first field", self.value_label)
        form.addRow("", _note("Try 0, 19, 0x12 or abc in the first field. Hover a red field to see why it is rejected."))
        self.small.valueChanged.connect(self._show_value)
        self._show_value(self.small.value())
        return box

    def _show_value(self, value: int | None) -> None:
        self.value_label.setText(repr(value))

    # ------------------------------------------------------------ hex fields
    def _hex_box(self) -> QGroupBox:
        box = QGroupBox("HexOutputField - read-only, monospace, Copy and Save   ·   HexField - input")
        self.public_key = HexOutputField(lines=4, save_name="public_key")
        self.public_key.set_hex(FAKE_PUBLIC_KEY)
        self.signature = HexOutputField(lines=3, save_name="signature")
        self.signature.set_hex(FAKE_SIGNATURE)
        self.empty = HexOutputField(lines=1)  # buttons are disabled while empty
        self.hex_input = HexField(lines=2)
        self.hex_input.set_hex("02 79 be 66 7e")

        form = QFormLayout(box)
        form.addRow("Public key (fake)", self.public_key)
        form.addRow("Signature (fake)", self.signature)
        form.addRow("Empty", self.empty)
        form.addRow("HexField (input)", self.hex_input)
        form.addRow("", _note("The input accepts spaces, colons and 0x. Type an odd number of digits to see the error state."))
        return box

    # ---------------------------------------------------------------- worker
    def _worker_box(self) -> QGroupBox:
        box = QGroupBox("run_in_background - the window stays responsive while a job runs")
        self.btn_ok = QPushButton("Slow job (2 s)")
        self.btn_ok.setProperty("primary", True)
        self.btn_value_error = QPushButton("Job with bad input (ValueError)")
        self.btn_bug = QPushButton("Job with a bug")
        self.btn_inline = QPushButton("Bad input, shown inline")
        self.result_label = QLabel("Press a button.")
        self.result_label.setWordWrap(True)
        self.busy_bar = QProgressBar()
        self.busy_bar.setRange(0, 0)  # "endless" animation
        self.busy_bar.setTextVisible(False)
        self.busy_bar.setFixedHeight(12)
        self.busy_bar.setVisible(False)
        busy_tracker().busyChanged.connect(self.busy_bar.setVisible)

        row = QHBoxLayout()
        for button in (self.btn_ok, self.btn_value_error, self.btn_bug, self.btn_inline):
            row.addWidget(button)
        layout = QVBoxLayout(box)
        layout.addLayout(row)
        layout.addWidget(self.busy_bar)
        layout.addWidget(self.result_label)
        layout.addWidget(_note(
            "While a job runs the cursor turns busy and the bar is shown. A ValueError opens a friendly "
            "message box; a page can also show the error itself by returning True from on_error."
        ))

        self.btn_ok.clicked.connect(lambda: self._start(slow_square, 12, 2.0))
        self.btn_value_error.clicked.connect(lambda: self._start(slow_bad_input, 1.0))
        self.btn_bug.clicked.connect(lambda: self._start(slow_bug, 1.0))
        self.btn_inline.clicked.connect(lambda: self._start(slow_bad_input, 1.0, inline=True))
        return box

    def _start(self, fn, *args, inline: bool = False) -> None:
        self._say("Working…", "info")

        def done(result) -> None:
            self._say(f"on_done received: {result!r}", "ok")

        def failed(exc: Exception):
            self._say(f"on_error received: {type(exc).__name__}: {exc}", "error")
            return True if inline else None  # True = "I showed it myself, no message box"

        run_in_background(fn, *args, on_done=done, on_error=failed)

    def _say(self, text: str, kind: str) -> None:
        self.result_label.setText(text)
        self.result_label.setProperty("kind", kind)
        self.result_label.style().unpolish(self.result_label)
        self.result_label.style().polish(self.result_label)

    # ----------------------------------------------------------------- theme
    def _toggle_theme(self) -> None:
        new = "light" if current_theme() == "dark" else "dark"
        apply_theme(QApplication.instance(), new)
        self.theme_button.setText("Switch to light theme" if new == "dark" else "Switch to dark theme")


def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(app, "light")
    window = WidgetsDemo()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
