"""Dialog for defining a small custom curve (owner: P2).

The student types p, a, b and a base point G = (Gx, Gy). Pressing OK hands the
numbers to P1's ``make_custom_curve`` on a background thread; it validates them
and computes the order n of G and the cofactor h. If it raises ValueError, its
message is shown in a message box and the dialog stays open. On success the
dialog closes and ``curve()`` returns the new curve.

    dialog = CustomCurveDialog(state, parent)
    if dialog.exec():
        curve = dialog.curve()

The main window opens this dialog from the "Custom curve…" entry of the curve
selector, adds the curve to the selector and selects it.
"""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from ecdsa_edu.core.curve import Curve, make_custom_curve
from ecdsa_edu.core.curves_registry import CURVES
from ecdsa_edu.core.field import is_probable_prime
from ecdsa_edu.gui.app_state import AppState
from ecdsa_edu.gui.tabs.keys_tab import set_message
from ecdsa_edu.gui.widgets.bigint_field import BigIntField
from ecdsa_edu.gui.widgets.worker import run_in_background

__all__ = ["CustomCurveDialog"]

_EXAMPLE = "toy-97"  # the "Try toy-97 values" button copies this built-in curve
_MIN_ORDER = 5  # with a smaller n there are hardly any keys to choose from


def _build_curve(p: int, a: int, b: int, G: tuple[int, int]) -> tuple[Curve, bool]:
    """Background job: let the core validate the curve, and ask it whether n is prime."""
    curve = make_custom_curve(p, a, b, G)
    return curve, is_probable_prime(curve.n)


class CustomCurveDialog(QDialog):
    """Create a custom curve  y^2 = x^3 + a*x + b (mod p)  with base point G."""

    def __init__(self, state: AppState | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Custom curve")
        self.setMinimumWidth(460)
        self._state = state
        self._curve: Curve | None = None
        self._job = 0  # newest creation job; answers of older ones are ignored
        self._busy = False

        intro = QLabel(
            "Define your own small curve <b>y² = x³ + a·x + b (mod p)</b> with a base point G."
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        help_text = QLabel("p must be prime and < 5000, G must lie on the curve.")
        help_text.setWordWrap(True)
        help_text.setProperty("note", True)
        self.help_label = help_text

        self.p_field = BigIntField(minimum=2)
        self.a_field = BigIntField()
        self.b_field = BigIntField()
        self.gx_field = BigIntField(minimum=0)
        self.gy_field = BigIntField(minimum=0)
        self._fields = (self.p_field, self.a_field, self.b_field, self.gx_field, self.gy_field)
        self._labels = ("p", "a", "b", "Gx", "Gy")

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        for label, field in zip(("Prime p", "a", "b", "Base point Gx", "Base point Gy"), self._fields):
            field.setAccessibleName(label)
            form.addRow(label, field)

        self.equation_label = QLabel()
        self.equation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.equation_label.setProperty("mono", True)
        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setMinimumHeight(34)

        self.btn_example = QPushButton("Try toy-97 values")
        self.btn_example.setToolTip("Fill in the parameters of the built-in curve toy-97")
        self.btn_example.setAutoDefault(False)
        self.btn_example.setVisible(_EXAMPLE in CURVES)
        row = QHBoxLayout()
        row.addWidget(self.btn_example)
        row.addStretch(1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.btn_ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.btn_ok.setText("Create curve")
        self.btn_ok.setDefault(True)

        lay = QVBoxLayout(self)
        lay.addWidget(intro)
        lay.addWidget(help_text)
        lay.addLayout(form)
        lay.addWidget(self.equation_label)
        lay.addLayout(row)
        lay.addWidget(self.hint_label)
        lay.addWidget(self.buttons)

        for field in self._fields:
            field.textChanged.connect(self._on_edited)
        self.btn_example.clicked.connect(self.fill_example)
        self.buttons.accepted.connect(self.create_curve)  # OK validates first; see create_curve
        self.buttons.rejected.connect(self.reject)
        self._on_edited()

    # ---------------------------------------------------------------- API
    def curve(self) -> Curve | None:
        """The curve that was created, or None (dialog cancelled / nothing valid yet)."""
        return self._curve

    def fill_example(self) -> None:
        """Fill in the parameters of the built-in curve toy-97."""
        example = CURVES.get(_EXAMPLE)
        if example is None:
            return
        for field, value in zip(self._fields, (example.p, example.a, example.b, *example.G)):
            field.set_value(value)

    def create_curve(self) -> None:
        """OK was pressed: build the curve with the core; close the dialog if it is valid."""
        if self._busy:
            return
        problem = self._input_problem()
        if problem:
            set_message(self.hint_label, problem, "error")
            return
        p, a, b, gx, gy = (field.value() for field in self._fields)
        self._job += 1
        job = self._job
        self._set_busy(True)
        set_message(self.hint_label, "Checking the curve and finding the order of G…", "info")

        def done(result: tuple[Curve, bool]) -> None:
            if not isValid(self) or job != self._job:
                return
            self._set_busy(False)
            curve, n_is_prime = result
            if curve.n < _MIN_ORDER:
                self._reject_curve(
                    f"G only has order n = {curve.n}, so there are hardly any keys. "
                    "Pick a base point with a larger order."
                )
            elif not n_is_prime:
                self._reject_curve(
                    f"G has order n = {curve.n}, which is not prime. ECDSA needs a base point "
                    "of prime order - try another point G."
                )
            else:
                self._curve = self._with_free_name(curve)
                self.accept()

        def failed(exc: Exception) -> bool:
            if isValid(self) and job == self._job:
                self._set_busy(False)
                self._reject_curve(str(exc))  # P1's own message
            return True  # shown here; the worker need not open a second message box

        run_in_background(_build_curve, p, a, b, (gx, gy), on_done=done, on_error=failed)

    # ----------------------------------------------------------- internals
    def _reject_curve(self, message: str) -> None:
        set_message(self.hint_label, "", "info")
        QMessageBox.warning(self, "Not a usable curve", message)

    def _with_free_name(self, curve: Curve) -> Curve:
        """Keep the core's name unless another, different curve already uses it."""
        taken = dict(CURVES)
        if self._state is not None:
            taken.update(self._state.available_curves())
        base = curve.name or "custom"
        candidate, number = replace(curve, name=base), 1
        while candidate.name in taken and taken[candidate.name] != candidate:
            number += 1
            candidate = replace(curve, name=f"{base}-{number}")
        return candidate

    def _input_problem(self) -> str:
        """What is missing or mistyped, or '' if the core can be asked."""
        for label, field in zip(self._labels, self._fields):
            if field.error():
                return f"{label}: {field.error()}."
            if field.value() is None:
                return f"Please fill in {label}."
        return ""

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.btn_ok.setEnabled(not busy and not self._input_problem())
        self.btn_example.setEnabled(not busy)

    def _on_edited(self) -> None:
        """Any edit cancels a running check and updates the equation and the hint."""
        self._job += 1
        self._busy = False
        self._curve = None
        self.btn_example.setEnabled(True)
        p, a, b = self.p_field.value(), self.a_field.value(), self.b_field.value()
        if None in (p, a, b):
            self.equation_label.setText("y² = x³ + a·x + b  (mod p)")
        else:
            self.equation_label.setText(f"y² = x³ + {a}·x + {b}  (mod {p})")
        problem = self._input_problem()
        self.btn_ok.setEnabled(not problem)
        mistyped = any(field.error() for field in self._fields)
        set_message(self.hint_label, problem if mistyped else "", "error")
