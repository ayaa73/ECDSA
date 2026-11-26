"""Start here page (owner: P4): "How ECDSA works", the first page students see.

One scrollable page:
  0. A welcome, what the app is for, and how to use it (the sidebar, and a
     suggested order for the pages).
  1. "ECDSA in 60 seconds": a 5-frame illustrated story (Alice signs, Bob
     verifies), drawn with QPainter so no image files are needed. Move through
     it with Previous and Next; it never advances on its own.
  2. "Try it in 3 clicks": Make keys -> Sign "Hello" -> Verify, using the real
     core functions on toy-17, then "Change one letter" shows INVALID.
     It uses its own throw-away key, so it never replaces the student's key.

Text lives in tutorial_content.py. No math here: values come from core calls.
"""
from __future__ import annotations

import html
from typing import Any

from PySide6.QtCore import QPointF, QRectF, QSettings, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout,
    QWidget,
)

from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.keys import generate_keypair
from ecdsa_edu.core.sign import sign
from ecdsa_edu.core.verify import verify
from ecdsa_edu.gui.tabs.p4_logic import fmt_number, fmt_point, tamper_text
from ecdsa_edu.gui.tabs.p4_widgets import ResultBanner, explanation, heading
from ecdsa_edu.gui.tutorial.tutorial_content import (
    ABOUT, ANALOGY, FRAMES, HOW_TO_USE, SETTINGS_KEY, SUGGESTED_ORDER, WELCOME,
)
from ecdsa_edu.gui.widgets.worker import run_in_background

__all__ = ["TutorialTab", "StoryCanvas"]

DEMO_CURVE = "toy-17"  # small numbers that fit on screen
DEMO_MESSAGE = "Hello"
NAVY, GREEN, RED, GOLD, GREY = "#282027", "#347754", "#b33b47", "#c89c36", "#756873"


def settings() -> QSettings:
    """App-wide settings (same names P2 uses for the rest of the app)."""
    return QSettings("ECDSA Lab", "ECDSA Lab")


# ====================================================================== story
class StoryCanvas(QWidget):
    """Draws one frame of the Alice -> Bob story. frame is 0..4."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.frame = 0
        self.setMinimumSize(600, 250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName("Illustration of the current story step")

    def set_frame(self, i: int) -> None:
        self.frame = max(0, min(i, len(FRAMES) - 1))
        self.setAccessibleDescription(FRAMES[self.frame].text)
        self.update()

    # ---------------------------------------------------------------- drawing helpers
    def _box(self, p: QPainter, rect: QRectF, text: str, color: str, fill: str = "#ffffff", bold=False) -> None:
        p.setPen(QPen(QColor(color), 2))
        p.setBrush(QColor(fill))
        p.drawRoundedRect(rect, 8, 8)
        f = QFont(self.font())
        f.setPointSizeF(max(9.0, f.pointSizeF()))
        f.setBold(bold)
        p.setFont(f)
        p.setPen(QColor(color))
        p.drawText(rect.adjusted(4, 2, -4, -2), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)

    def _person(self, p: QPainter, x: float, name: str) -> None:
        p.setPen(QPen(QColor(NAVY), 2))
        p.setBrush(QColor("#f8e6f0"))
        p.drawEllipse(QPointF(x, 70), 22, 22)  # head
        path = QPainterPath()
        path.moveTo(x - 34, 140)
        path.quadTo(x, 82, x + 34, 140)
        p.drawPath(path)  # shoulders
        f = QFont(self.font())
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(x - 50, 145, 100, 20), Qt.AlignmentFlag.AlignCenter, name)

    def _arrow(self, p: QPainter, a: QPointF, b: QPointF, color: str = NAVY) -> None:
        p.setPen(QPen(QColor(color), 2.5))
        p.drawLine(a, b)
        v = b - a
        length = max((v.x() ** 2 + v.y() ** 2) ** 0.5, 1)
        ux, uy = v.x() / length, v.y() / length
        left = QPointF(b.x() - 10 * ux + 5 * uy, b.y() - 10 * uy - 5 * ux)
        right = QPointF(b.x() - 10 * ux - 5 * uy, b.y() - 10 * uy + 5 * ux)
        p.setBrush(QColor(color))
        p.drawPolygon(QPolygonF([b, left, right]))

    def paintEvent(self, event: Any) -> None:  # noqa: N802 (Qt name)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        ax, bx = 70.0, w - 70.0  # Alice left, Bob right
        mid = w / 2
        self._person(p, ax, "Alice")
        self._person(p, bx, "Bob")
        f = self.frame

        if f == 0:  # two keys
            self._box(p, QRectF(ax + 50, 40, 150, 40), "private key d\n(secret)", RED, "#fff0f0", True)
            self._box(p, QRectF(ax + 50, 100, 150, 40), "public key Q\n(shared)", GREEN, "#e8f3e8", True)
            self._arrow(p, QPointF(ax + 205, 120), QPointF(bx - 45, 110), GREEN)
            p.setPen(QColor(GREY))
            p.drawText(QRectF(mid - 60, 125, 200, 20), Qt.AlignmentFlag.AlignCenter, "everyone gets Q")
        elif f == 1:  # hash
            self._box(p, QRectF(ax + 50, 50, 130, 60), "message\n\"Hello Bob\"", NAVY)
            self._arrow(p, QPointF(ax + 185, 80), QPointF(mid + 20, 80))
            p.setPen(QColor(GREY))
            p.drawText(QRectF(ax + 185, 55, mid - ax - 165, 20), Qt.AlignmentFlag.AlignCenter, "SHA-256")
            self._box(p, QRectF(mid + 25, 55, 150, 50), "fingerprint e\n3f9a…c21", NAVY, "#eef4fb", True)
        elif f == 2:  # sign
            self._box(p, QRectF(ax + 50, 30, 120, 40), "fingerprint e", NAVY)
            self._box(p, QRectF(ax + 50, 100, 120, 40), "private key d", RED, "#fff0f0")
            self._box(p, QRectF(ax + 50, 160, 120, 34), "fresh secret k", RED, "#fff0f0")
            for y in (50, 120, 177):
                self._arrow(p, QPointF(ax + 175, y), QPointF(mid + 10, 110))
            seal = QRectF(mid + 15, 75, 130, 70)
            p.setPen(QPen(QColor(GOLD), 3))
            p.setBrush(QColor("#fff1bf"))
            p.drawEllipse(seal)
            p.setPen(QColor(NAVY))
            bold = QFont(self.font())
            bold.setBold(True)
            p.setFont(bold)
            p.drawText(seal, Qt.AlignmentFlag.AlignCenter, "signature\n(r, s)")
        elif f == 3:  # send
            self._box(p, QRectF(mid - 110, 40, 120, 50), "message\n\"Hello Bob\"", NAVY)
            seal = QRectF(mid + 20, 40, 100, 50)
            p.setPen(QPen(QColor(GOLD), 3))
            p.setBrush(QColor("#fff1bf"))
            p.drawEllipse(seal)
            p.setPen(QColor(NAVY))
            p.drawText(seal, Qt.AlignmentFlag.AlignCenter, "(r, s)")
            self._arrow(p, QPointF(ax + 45, 120), QPointF(bx - 45, 120))
            p.setPen(QColor(GREY))
            p.drawText(QRectF(mid - 120, 128, 240, 20), Qt.AlignmentFlag.AlignCenter,
                       "sent in the open: no secrets inside")
        else:  # verify
            self._box(p, QRectF(bx - 260, 30, 170, 36), "message + (r, s)", NAVY)
            self._box(p, QRectF(bx - 260, 80, 170, 36), "Alice's public key Q", GREEN, "#e8f3e8")
            self._arrow(p, QPointF(bx - 85, 72), QPointF(bx - 45, 72))
            self._box(p, QRectF(ax + 50, 130, 150, 44), "✔ VALID\nnothing changed", GREEN, "#e8f3e8", True)
            self._box(p, QRectF(ax + 215, 130, 150, 44), "✘ INVALID\none letter changed", RED, "#fff0f0", True)
        p.end()


# ====================================================================== page
class TutorialTab(QWidget):
    """Start here: a welcome, how to use the app, the big picture of ECDSA and a 3-click demo."""

    HELP = ("Start here if ECDSA is new to you. The top explains what the app is for and suggests an order for "
            "the pages in the sidebar. The story shows in five steps how Alice signs a message and how Bob checks "
            "it, and \"Try it in 3 clicks\" runs the real thing with small numbers.")

    def __init__(self, state: Any = None) -> None:
        super().__init__()
        self.state = state
        self._demo_keys: tuple[Any, Any] | None = None
        self._demo_sig: Any = None
        self._demo_msg = DEMO_MESSAGE
        self.curve = get_curve(DEMO_CURVE)

        # ---- part 1: story
        self.canvas = StoryCanvas()
        self.frame_title = QLabel()
        self.frame_title.setProperty("heading", "section")
        self.frame_text = QLabel()
        self.frame_text.setWordWrap(True)
        self.frame_text.setMinimumHeight(48)
        self.prev_button = QPushButton("◀ Previous")
        self.next_button = QPushButton("Next ▶")
        self.prev_button.clicked.connect(lambda *_: self.show_frame(self.canvas.frame - 1))
        self.next_button.clicked.connect(lambda *_: self.show_frame(self.canvas.frame + 1))
        nav = QHBoxLayout()
        nav.addWidget(self.prev_button)
        nav.addWidget(self.next_button)
        nav.addStretch(1)
        story = QGroupBox("ECDSA in 60 seconds")
        story_layout = QVBoxLayout(story)
        story_layout.addWidget(self.canvas)
        story_layout.addWidget(self.frame_title)
        story_layout.addWidget(self.frame_text)
        story_layout.addLayout(nav)
        story_layout.addWidget(explanation(f"<i>{html.escape(ANALOGY)}</i>"))

        # ---- part 2: try it
        self.keys_button = QPushButton("1. Make keys")
        self.sign_button = QPushButton(f"2. Sign \"{DEMO_MESSAGE}\"")
        self.verify_button = QPushButton("3. Verify")
        self.tamper_button = QPushButton("Change one letter")
        for b in (self.keys_button, self.sign_button, self.verify_button, self.tamper_button):
            b.setMinimumHeight(34)
        self.keys_button.clicked.connect(self.make_keys)
        self.sign_button.clicked.connect(self.sign_message)
        self.verify_button.clicked.connect(self.verify_message)
        self.tamper_button.clicked.connect(self.tamper_message)
        steps = QHBoxLayout()
        for b in (self.keys_button, self.sign_button, self.verify_button, self.tamper_button):
            steps.addWidget(b)
        self.keys_card, self.sign_card = QLabel(), QLabel()
        for card in (self.keys_card, self.sign_card):
            card.setWordWrap(True)
            card.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.banner = ResultBanner()
        try_box = QGroupBox("Try it in 3 clicks")
        try_layout = QVBoxLayout(try_box)
        try_layout.addWidget(explanation(
            f"This uses the tiny teaching curve {DEMO_CURVE} so the numbers fit on screen. It makes its own "
            "practice key, so it won't change the key on your Keys page."))
        try_layout.addLayout(steps)
        try_layout.addWidget(self.keys_card)
        try_layout.addWidget(self.sign_card)
        try_layout.addWidget(self.banner)

        # ---- startup checkbox
        self.startup_box = QCheckBox("Show this page when the app starts")
        self.startup_box.setChecked(self.show_at_startup())
        self.startup_box.toggled.connect(lambda on: settings().setValue(SETTINGS_KEY, bool(on)))

        content = QWidget()
        page = QVBoxLayout(content)
        self.welcome_heading = heading("Welcome to ECDSA Lab")
        page.addWidget(self.welcome_heading)
        page.addWidget(explanation(html.escape(WELCOME)))
        about = QGroupBox("What this app is for")
        about_layout = QVBoxLayout(about)
        about_layout.addWidget(explanation(html.escape(ABOUT)))
        page.addWidget(about)
        guide = QGroupBox("How to use it")
        guide_layout = QVBoxLayout(guide)
        self.how_label = explanation(html.escape(HOW_TO_USE))
        guide_layout.addWidget(self.how_label)
        steps_html = "".join(f"<li><b>{html.escape(stop.page)}</b>: {html.escape(stop.what)}</li>"
                             for stop in SUGGESTED_ORDER)
        self.order_label = explanation(f"Suggested order:<ol style='margin-top:4px'>{steps_html}</ol>")
        guide_layout.addWidget(self.order_label)
        page.addWidget(guide)
        page.addWidget(heading("How ECDSA works"))
        page.addWidget(story)
        page.addWidget(try_box)
        page.addWidget(self.startup_box)
        page.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self.show_frame(0)
        self._update_demo_buttons()

    # ------------------------------------------------------------ tab contract
    def set_curve(self, curve: Any) -> None:
        """The tutorial always uses toy-17 so the numbers stay small."""

    @staticmethod
    def show_at_startup() -> bool:
        value = settings().value(SETTINGS_KEY, True)
        return value not in (False, "false", "0", 0)

    # ------------------------------------------------------------ story
    def show_frame(self, i: int) -> None:
        self.canvas.set_frame(i)
        frame = FRAMES[self.canvas.frame]
        self.frame_title.setText(frame.title)
        self.frame_text.setText(frame.text)
        self.prev_button.setEnabled(self.canvas.frame > 0)
        self.next_button.setEnabled(self.canvas.frame < len(FRAMES) - 1)

    # ------------------------------------------------------------ 3-click demo
    def _update_demo_buttons(self, busy: bool = False) -> None:
        self.keys_button.setEnabled(not busy)
        self.sign_button.setEnabled(not busy and self._demo_keys is not None)
        self.verify_button.setEnabled(not busy and self._demo_sig is not None)
        self.tamper_button.setEnabled(not busy and self._demo_sig is not None)

    def make_keys(self, *_: Any) -> None:
        self._demo_sig = None
        self._demo_msg = DEMO_MESSAGE
        self.sign_card.setText("")
        self.banner.show_message("info", "", "")
        self._update_demo_buttons(busy=True)
        run_in_background(generate_keypair, self.curve, on_done=self._keys_done, on_error=self._failed)

    def _keys_done(self, keys: tuple[Any, Any]) -> None:
        self._demo_keys = keys
        priv, pub = keys
        self.keys_card.setText(
            f"<b>Private key</b> d = {fmt_number(priv.d, self.curve)} <i>(secret: in real life never shown)</i><br>"
            f"<b>Public key</b> Q = {fmt_point(pub.Q, self.curve)} <i>(shared with everyone)</i>")
        self._update_demo_buttons()

    def sign_message(self, *_: Any) -> None:
        if self._demo_keys is None:
            return
        self._demo_msg = DEMO_MESSAGE
        self._update_demo_buttons(busy=True)
        run_in_background(sign, self._demo_keys[0], DEMO_MESSAGE.encode(), on_done=self._sign_done,
                          on_error=self._failed)

    def _sign_done(self, sig: Any) -> None:
        self._demo_sig = sig
        self.sign_card.setText(f"<b>Signature</b> on \"{html.escape(DEMO_MESSAGE)}\": "
                               f"r = {fmt_number(sig.r, self.curve)}, s = {fmt_number(sig.s, self.curve)}")
        self.banner.show_message("info", "Signed", "Now press Verify to check it as Bob would.")
        self._update_demo_buttons()

    def verify_message(self, message: str | None = None, note: str = "") -> None:
        if self._demo_keys is None or self._demo_sig is None:
            return
        text = message if isinstance(message, str) else self._demo_msg
        self._update_demo_buttons(busy=True)
        run_in_background(verify, self._demo_keys[1], text.encode(), self._demo_sig,
                          on_done=lambda ok: self._verify_done(ok, text, note), on_error=self._failed)

    def _verify_done(self, ok: bool, text: str, note: str) -> None:
        shown = html.escape(text)
        if ok:
            self.banner.show_message("good", "VALID", f"\"{text}\" was signed with Alice's private key.")
        else:
            self.banner.show_message("bad", "INVALID", f"{note} The message is now \"{text}\", which is not what "
                                                       "Alice signed, so the same signature no longer fits.")
        self.banner.setToolTip(shown)
        self._update_demo_buttons()

    def tamper_message(self, *_: Any) -> None:
        changed, what = tamper_text(self._demo_msg)
        self._demo_msg = changed
        self.verify_message(changed, note=f"We {what}.")

    def _failed(self, exc: Exception) -> bool:
        self._update_demo_buttons()
        self.banner.show_message("bad", "Something went wrong", str(exc))
        return True
