"""The curve picker: choose a curve from cards instead of a dropdown (owner: P2).

The cards are grouped for beginners:
    Start here  - the small toy curves (toy-17 is marked "Recommended")
    Real-world  - secp256k1 and P-256
    Your curves - custom curves the user created in this session
A last card, "+ Make your own curve", asks the main window to open the
custom-curve dialog.

Each card shows the curve's label, a one-sentence summary, where it is used,
the key size in bits and whether it is small enough to draw. The text comes
from P1's describe_curve() in core/curves_registry.py. Until P1 has added it,
a small fallback table below is used, so the picker already works today.

    picker = CurvePicker(state, parent)
    if picker.exec():
        if picker.wants_custom():   # "+ Make your own curve" was clicked
            ...open the custom-curve dialog...
        else:
            state.set_curve(picker.chosen())

Keyboard: arrow keys move between cards, Enter or Space chooses, Esc cancels.
This file does no math: it only reads numbers that are stored in the curves.
"""
import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ecdsa_edu.core import curves_registry

__all__ = ["CurvePicker", "curve_description"]

RECOMMENDED = "toy-17"   # gets the "Recommended for your first time" badge
COLUMNS = 2              # cards per row
DRAWABLE_LIMIT = 1000    # a curve with p below this is small enough to plot every point

# Used only while P1's describe_curve() is missing from curves_registry.py.
_FALLBACK = {
    "toy-17": {"label": "Toy curve (p = 17)",
               "summary": "Tiny curve with 19 points: every step can be checked by hand.",
               "used_in": "Learning and classroom examples"},
    "toy-97": {"label": "Small curve (p = 97)",
               "summary": "A bit bigger (79 points), still small enough to draw and attack.",
               "used_in": "Demos and the attack page"},
    "secp256k1": {"label": "secp256k1",
                  "summary": "The 256-bit curve that protects Bitcoin and Ethereum wallets.",
                  "used_in": "Bitcoin, Ethereum"},
    "P-256": {"label": "NIST P-256",
              "summary": "The 256-bit curve used by most HTTPS websites and government standards.",
              "used_in": "HTTPS (TLS), passports, smart cards"},
}


def curve_description(curve):
    """Text for one card: a dictionary with label, summary, used_in, key_bits and drawable."""
    info = {}
    describe = getattr(curves_registry, "describe_curve", None)  # P1's function, if it exists yet
    if describe is not None:
        try:
            found = describe(curve.name)
        except Exception:  # unknown name (custom curve) or a different signature
            found = None
        if isinstance(found, dict):
            info.update(found)
    if not info and curve.name in _FALLBACK:
        info.update(_FALLBACK[curve.name])

    # Whatever P1 provides, these fields always exist.
    info.setdefault("label", curve.name)
    info.setdefault("summary", "Your own curve: y² = x³ + " + str(curve.a) + "x + " + str(curve.b)
                    + " (mod " + str(curve.p) + "), with " + str(curve.n) + " points in G's group.")
    info.setdefault("used_in", "")
    info.setdefault("key_bits", curve.n.bit_length())        # private keys are numbers below n
    info.setdefault("drawable", curve.p < DRAWABLE_LIMIT)
    return info


class _Card(QPushButton):
    """One clickable card. A QPushButton, so focus, Enter and Space work for free."""

    def __init__(self, title, lines, badge="", current=False, parent=None):
        super().__init__(parent)
        self.setProperty("card", True)
        self.setProperty("current", current)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoDefault(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        if badge:
            badge_label = QLabel(badge)
            badge_label.setProperty("badge", True)
            layout.addWidget(badge_label, 0, Qt.AlignmentFlag.AlignLeft)
        title_label = QLabel("<b>" + html.escape(title) + "</b>" + ("  ✓ in use" if current else ""))
        title_label.setProperty("cardTitle", True)
        layout.addWidget(title_label)
        for line in lines:
            label = QLabel(line)
            label.setWordWrap(True)
            label.setProperty("note", True)
            layout.addWidget(label)
        # Clicks on the labels must reach the button underneath.
        for child in self.findChildren(QLabel):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setMinimumHeight(layout.sizeHint().height())
        self.setMinimumWidth(280)
        self.setAccessibleName(title)


class CurvePicker(QDialog):
    """Dialog with one card per curve. After exec(): chosen() or wants_custom()."""

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose a curve")
        self.setMinimumSize(680, 640)
        self._state = state
        self._chosen = None
        self._wants_custom = False
        self.cards = {}        # curve name -> card button
        self._order = []       # all card buttons, in reading order (for the arrow keys)

        intro = QLabel("Pick the session curve. <b>New to ECDSA?</b> Start with toy-17: "
                       "its numbers are small enough to check by hand.")
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)

        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        builtin = curves_registry.CURVES
        small = [c for c in builtin.values() if c.p.bit_length() <= 32]
        real = [c for c in builtin.values() if c.p.bit_length() > 32]
        custom = list(state.custom_curves.values()) if state is not None else []
        self._add_group("Start here", "Small curves for learning: fast, and every number fits on screen.", small)
        self._add_group("Real-world", "The curves real software uses. Same math, 256-bit numbers.", real)
        self._add_group("Your curves", "Curves you made yourself in this session.", custom, with_custom_card=True)
        self._content_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)

        cancel = QPushButton("Cancel")
        cancel.setAutoDefault(False)
        cancel.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(scroll, 1)
        layout.addWidget(cancel, 0, Qt.AlignmentFlag.AlignRight)

        # Start with the keyboard focus on the curve that is in use.
        current = state.curve if state is not None else None
        start = self.cards.get(current.name) if current is not None else None
        if start is None and self._order:
            start = self._order[0]
        if start is not None:
            start.setFocus()

    # -------------------------------------------------------------- building
    def _add_group(self, title, subtitle, curves, with_custom_card=False):
        heading = QLabel(html.escape(title))
        heading.setProperty("groupTitle", True)
        self._content_layout.addWidget(heading)
        self._content_layout.addWidget(_small_note(subtitle))

        grid = QGridLayout()
        grid.setSpacing(10)
        position = 0
        current = self._state.curve if self._state is not None else None
        for curve in curves:
            info = curve_description(curve)
            card = _Card(info["label"], self._card_lines(curve, info),
                         badge="Recommended for your first time" if curve.name == RECOMMENDED else "",
                         current=(current is not None and current.name == curve.name))
            card.setToolTip(f"Select {curve.name} as the session curve")
            card.clicked.connect(lambda _checked=False, c=curve: self._choose(c))
            self.cards[curve.name] = card
            self._order.append(card)
            grid.addWidget(card, position // COLUMNS, position % COLUMNS)
            position += 1

        if with_custom_card:
            self.custom_card = _Card("+ Make your own curve",
                                     ["Type p, a, b and a base point G. Hints tell you what to fix."])
            self.custom_card.setToolTip("Open the custom-curve dialog")
            self.custom_card.clicked.connect(self._choose_custom)
            self._order.append(self.custom_card)
            grid.addWidget(self.custom_card, position // COLUMNS, position % COLUMNS)
        self._content_layout.addLayout(grid)

    @staticmethod
    def _card_lines(curve, info):
        lines = [info["summary"]]
        if info["used_in"]:
            lines.append("Used in: " + info["used_in"])
        details = "Key size: " + str(info["key_bits"]) + " bits"
        if info["drawable"]:
            details += "  ·  Can be drawn"
        lines.append(details)
        return lines

    # -------------------------------------------------------------- choosing
    def _choose(self, curve):
        self._chosen = curve
        self._wants_custom = False
        self.accept()

    def _choose_custom(self):
        self._chosen = None
        self._wants_custom = True
        self.accept()

    def chosen(self):
        """The curve the user clicked, or None (cancelled, or "Make your own")."""
        return self._chosen

    def wants_custom(self):
        """True if the user clicked "+ Make your own curve"."""
        return self._wants_custom

    # -------------------------------------------------------------- keyboard
    def keyPressEvent(self, event):  # noqa: N802 (Qt naming)
        """Arrow keys move between cards; everything else works as usual."""
        steps = {Qt.Key.Key_Right: 1, Qt.Key.Key_Left: -1,
                 Qt.Key.Key_Down: COLUMNS, Qt.Key.Key_Up: -COLUMNS}
        step = steps.get(event.key())
        focused = self.focusWidget()
        if step is not None and focused in self._order:
            index = self._order.index(focused) + step
            index = max(0, min(index, len(self._order) - 1))
            self._order[index].setFocus()
            return
        super().keyPressEvent(event)


def _small_note(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setProperty("note", True)
    return label
