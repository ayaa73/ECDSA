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

Help for beginners:
  - "Start from" buttons fill in the numbers of a built-in toy curve;
  - "Suggest values for me": type only p, and P1's suggest_small_curves(p)
    finds a few working curves (a, b and G); one click fills them in. The
    button is disabled until P1's function exists in curves_registry.py;
  - while the student types, a plain hint under p and under G says whether
    the value is fine and, if not, what to change. These hints call core
    functions (is_probable_prime, is_on_curve); the dialog does no math itself.
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

from ecdsa_edu.core.curve import Curve, is_on_curve, make_custom_curve
from ecdsa_edu.core import curves_registry
from ecdsa_edu.core.curves_registry import CURVES
from ecdsa_edu.core.field import is_probable_prime
from ecdsa_edu.gui.app_state import AppState
from ecdsa_edu.gui.tabs.keys_tab import set_message
from ecdsa_edu.gui.widgets.bigint_field import BigIntField
from ecdsa_edu.gui.widgets.worker import run_in_background

__all__ = ["CustomCurveDialog"]

_EXAMPLE = "toy-97"  # fill_example() copies this built-in curve
PRESETS = ("toy-17", "toy-97")  # the "Start from" buttons
MAX_P = 5000  # P1's make_custom_curve only accepts p below this
MIN_P = 5
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

        # One plain hint under p and one under G, updated while the student types.
        self.p_hint = QLabel()
        self.p_hint.setWordWrap(True)
        self.g_hint = QLabel()
        self.g_hint.setWordWrap(True)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        for label, field in zip(("Prime p", "a", "b", "Base point Gx", "Base point Gy"), self._fields):
            field.setAccessibleName(label)
            form.addRow(label, field)
            if field is self.p_field:
                form.addRow("", self.p_hint)
        form.addRow("", self.g_hint)

        self.equation_label = QLabel()
        self.equation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.equation_label.setProperty("mono", True)
        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setMinimumHeight(34)

        # "Start from" buttons: one per preset curve that exists in P1's registry.
        row = QHBoxLayout()
        row.addWidget(QLabel("Start from:"))
        self.preset_buttons: dict[str, QPushButton] = {}
        for name in PRESETS:
            if name not in CURVES:
                continue
            button = QPushButton(name)
            button.setToolTip("Fill in the numbers of the built-in curve " + name + ", then change them")
            button.setAutoDefault(False)
            button.clicked.connect(lambda _checked=False, preset=name: self.fill_preset(preset))
            row.addWidget(button)
            self.preset_buttons[name] = button
        row.addStretch(1)
        # "Suggest values for me": the core finds curves for the typed p.
        self.btn_suggest = QPushButton("Suggest values for me")
        self.btn_suggest.setAutoDefault(False)
        self.suggest_row = QVBoxLayout()  # one button per suggestion, under each other
        self.suggestion_buttons: list[QPushButton] = []
        self.btn_suggest.clicked.connect(self.suggest_values)
        # Kept for older code and tests: the toy-97 button.
        self.btn_example = self.preset_buttons[_EXAMPLE]

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
        suggest_line = QHBoxLayout()
        suggest_line.addWidget(self.btn_suggest)
        suggest_line.addStretch(1)
        lay.addLayout(suggest_line)
        lay.addLayout(self.suggest_row)
        lay.addWidget(self.hint_label)
        lay.addWidget(self.buttons)

        for field in self._fields:
            field.textChanged.connect(self._on_edited)
        self.buttons.accepted.connect(self.create_curve)  # OK validates first; see create_curve
        self.buttons.rejected.connect(self.reject)
        self._on_edited()

    # ---------------------------------------------------------------- API
    def curve(self) -> Curve | None:
        """The curve that was created, or None (dialog cancelled / nothing valid yet)."""
        return self._curve

    def fill_preset(self, name: str) -> None:
        """Fill in p, a, b, Gx, Gy from the built-in curve `name` (e.g. "toy-17")."""
        preset = CURVES.get(name)
        if preset is None:
            return
        values = (preset.p, preset.a, preset.b, preset.G[0], preset.G[1])
        for field, value in zip(self._fields, values):
            field.set_value(value)

    def fill_example(self) -> None:
        """Fill in the parameters of the built-in curve toy-97."""
        self.fill_preset(_EXAMPLE)

    def suggest_values(self) -> None:
        """Ask the core for working curves with the typed p and show them as buttons."""
        suggest = getattr(curves_registry, "suggest_small_curves", None)
        if suggest is None or not self._p_is_fine():
            return
        p = self.p_field.value()
        self._clear_suggestions()
        self._suggest_job = getattr(self, "_suggest_job", 0) + 1
        job = self._suggest_job
        self.btn_suggest.setEnabled(False)
        set_message(self.hint_label, "Looking for good curves with p = " + str(p) + "…", "info")

        def done(curves) -> None:
            if not isValid(self) or job != self._suggest_job:
                return
            self.btn_suggest.setEnabled(True)
            if not curves:
                set_message(self.hint_label, "No curve found for this p. Try another prime.", "error")
                return
            set_message(self.hint_label, "Click a suggestion to fill in the fields.", "ok")
            for curve in curves:
                text = ("a = " + str(curve.a) + ",  b = " + str(curve.b) + ",  G = (" + str(curve.G[0]) + ", "
                        + str(curve.G[1]) + ")      →  n = " + str(curve.n) + " points")
                button = QPushButton(text)
                button.setAutoDefault(False)
                button.setToolTip("Fill the fields with this suggestion, then press Create curve.")
                button.clicked.connect(lambda _checked=False, c=curve: self._use_suggestion(c))
                self.suggest_row.addWidget(button)
                self.suggestion_buttons.append(button)

        def failed(exc: Exception) -> bool:
            if isValid(self) and job == self._suggest_job:
                self.btn_suggest.setEnabled(True)
                set_message(self.hint_label, str(exc), "error")
            return True

        run_in_background(suggest, p, on_done=done, on_error=failed)

    def _use_suggestion(self, curve: Curve) -> None:
        """Fill the fields with a suggested curve (p stays the same)."""
        for field, value in zip(self._fields, (curve.p, curve.a, curve.b, curve.G[0], curve.G[1])):
            field.set_value(value)

    def _clear_suggestions(self) -> None:
        for button in self.suggestion_buttons:
            self.suggest_row.removeWidget(button)
            button.deleteLater()
        self.suggestion_buttons = []

    def _update_suggest_button(self) -> None:
        if getattr(curves_registry, "suggest_small_curves", None) is None:
            self.btn_suggest.setEnabled(False)
            self.btn_suggest.setToolTip("Coming soon: needs suggest_small_curves() from P1's curves_registry.py")
        elif not self._p_is_fine():
            self.btn_suggest.setEnabled(False)
            self.btn_suggest.setToolTip("Type a prime p (5 to 4999) first")
        else:
            self.btn_suggest.setEnabled(True)
            self.btn_suggest.setToolTip("Find a, b and G that make a good curve for this p")

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
        self._update_field_hints()
        self._update_suggest_button()

    # ------------------------------------------------------ live hints
    def _update_field_hints(self) -> None:
        """Refresh the plain hints under p and G."""
        p_text, p_kind = self._p_hint()
        set_message(self.p_hint, p_text, p_kind)
        g_text, g_kind = self._g_hint()
        set_message(self.g_hint, g_text, g_kind)

    def _p_is_fine(self) -> bool:
        p = self.p_field.value()
        return p is not None and MIN_P <= p < MAX_P and is_probable_prime(p)

    def _p_hint(self) -> tuple[str, str]:
        """(text, kind) for the hint under p."""
        p = self.p_field.value()
        if p is None:
            if self.p_field.error():
                return "p must be a whole number.", "error"
            return "A prime number from 5 to 4999, for example 17 or 97.", "info"
        if p < MIN_P:
            return "p must be at least 5.", "error"
        if p >= MAX_P:
            return "p must be below 5000, so the app can count all the points.", "error"
        if not is_probable_prime(p):
            return str(p) + " is not a prime number. Try 17, 97 or 251.", "error"
        return "✓ p is a prime below 5000.", "ok"

    def _g_hint(self) -> tuple[str, str]:
        """(text, kind) for the hint under G."""
        p, a, b, gx, gy = (field.value() for field in self._fields)
        if None in (a, b, gx, gy) or not self._p_is_fine():
            return "Pick a point G = (Gx, Gy) on the curve, or press a “Start from” button.", "info"
        if not (0 <= gx < p and 0 <= gy < p):
            return "Gx and Gy must be between 0 and p - 1 (here 0 to " + str(p - 1) + ").", "error"
        tip = "try a suggestion" if getattr(curves_registry, "suggest_small_curves", None) else "try a “Start from” button"
        # Ask the core whether G satisfies y^2 = x^3 + a*x + b (mod p).
        # n and h are not known yet; is_on_curve does not use them.
        test_curve = Curve(name="check", p=p, a=a % p, b=b % p, G=(gx, gy), n=1, h=1)
        if is_on_curve(test_curve, (gx, gy)):
            return "✓ G lies on this curve.", "ok"
        return "G is not on this curve: " + tip + ", or another point.", "error"
