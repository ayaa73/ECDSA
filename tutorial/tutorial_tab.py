"""Start here page (owner: P4): the first page students see.

A short, playful landing page instead of a wall of text:
  0. An animated hero (a real elliptic curve with a point gliding along it), a
     "did you know" fact you can shuffle, and buttons that scroll to each part.
  1. "ECDSA in 60 seconds": a 5-frame illustrated story (Alice signs, Bob
     verifies) with clickable step chips. Drawn with QPainter, no image files.
  2. "Try it live": type your own message, then Make keys -> Sign -> Verify, and
     "Change one letter" shows INVALID. Four badges light up as you go. It uses
     the real core functions on toy-17 and its own throw-away key, so it never
     replaces the student's key.
  3. "Pick your adventure": clickable cards that open every other page.
  4. A collapsed "How do I use this app?" help box.

Text lives in tutorial_content.py. No math here: values come from core calls.
"""
from __future__ import annotations

import html
import math
import random
from typing import Any

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPointF, QPropertyAnimation, QRectF, QSettings, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QToolButton,
    QVBoxLayout, QWidget,
)

from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.keys import generate_keypair
from ecdsa_edu.core.sign import sign
from ecdsa_edu.core.verify import verify
from ecdsa_edu.gui.tabs.p4_logic import fmt_number, fmt_point, tamper_text
from ecdsa_edu.gui.tabs.p4_widgets import ResultBanner, explanation, go_to
from ecdsa_edu.gui.tutorial.tutorial_content import (
    ANALOGY, FACTS, FRAMES, HOW_TO_USE, SETTINGS_KEY, STEP_CHIPS, SUGGESTED_ORDER, TRACKS, WELCOME,
)
from ecdsa_edu.gui.widgets.flow_layout import FlowLayout
from ecdsa_edu.gui.widgets.worker import run_in_background

__all__ = ["TutorialTab", "StoryCanvas", "HeroBanner", "QuestCard"]

DEMO_CURVE = "toy-17"  # small numbers that fit on screen
DEMO_MESSAGE = "Hello"
NAVY, GREEN, RED, GOLD, GREY = "#282027", "#347754", "#b33b47", "#c89c36", "#756873"
HERO_DARK, HERO_LIGHT, HERO_GOLD = "#33091a", "#7a1f35", "#ffd35c"


def settings() -> QSettings:
    """The app's own settings file (the same store as the rest of the app).

    QSettings("ECDSA Lab", "ECDSA Lab") would use the Windows registry instead,
    a second place the main window and the tests could not see.
    """
    from ecdsa_edu.gui.app_state import make_settings
    return make_settings()


# ====================================================================== story
class StoryCanvas(QWidget):
    """Draws one frame of the Alice -> Bob story. frame is 0..4."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.frame = 0
        self.phase = 0
        self._anim = QTimer(self)
        self._anim.timeout.connect(self._advance)
        self.setMinimumSize(600, 250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName("Illustration of the current story step")

    def _advance(self) -> None:
        self.phase = (self.phase + 1) % 90
        if self.frame in (3, 4):
            self.update()

    def showEvent(self, event: Any) -> None:  # noqa: N802 (Qt name)
        self._anim.start(40)
        super().showEvent(event)

    def hideEvent(self, event: Any) -> None:  # noqa: N802 (Qt name)
        self._anim.stop()
        super().hideEvent(event)

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
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#fdf6f0"))  # light card, so the drawing reads in light and dark themes
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 14, 14)
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
            frac = (self.phase % 60) / 60.0  # a little packet flies from Alice to Bob
            px = ax + 45 + (bx - ax - 90) * frac
            p.setPen(QPen(QColor(NAVY), 1.5))
            p.setBrush(QColor(GOLD))
            p.drawRoundedRect(QRectF(px - 11, 108, 22, 15), 3, 3)
        else:  # verify
            self._box(p, QRectF(bx - 260, 30, 170, 36), "message + (r, s)", NAVY)
            self._box(p, QRectF(bx - 260, 80, 170, 36), "Alice's public key Q", GREEN, "#e8f3e8")
            self._arrow(p, QPointF(bx - 85, 72), QPointF(bx - 45, 72))
            self._box(p, QRectF(ax + 50, 130, 150, 44), "✔ VALID\nnothing changed", GREEN, "#e8f3e8", True)
            self._box(p, QRectF(ax + 215, 130, 150, 44), "✘ INVALID\none letter changed", RED, "#fff0f0", True)
            pulse = (self.phase % 45) / 45.0  # a ring ripples out of the VALID box
            ring = QColor(GREEN)
            ring.setAlphaF(max(0.0, 0.7 * (1 - pulse)))
            p.setPen(QPen(ring, 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(ax + 50, 130, 150, 44).adjusted(-pulse * 12, -pulse * 12, pulse * 12, pulse * 12), 10, 10)
        p.end()


# ====================================================================== hero
class HeroBanner(QWidget):
    """Animated header. Text and buttons are real child widgets laid over a painted background:
    an elliptic curve y^2 = x^3 - 3x + 3 with a bright point gliding along it."""

    A, B = -3.0, 3.0
    X0 = -2.1038  # the curve's leftmost point, where x^3 - 3x + 3 = 0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(230)
        self.t = 0.0
        self._curve = self._build_curve()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def _build_curve(self) -> list[tuple[float, float]]:
        """One continuous polyline: bottom arm -> left tip -> top arm."""
        xs = [self.X0 + (3.3 - self.X0) * (i / 160) ** 1.7 for i in range(161)]
        top = [(x, math.sqrt(max(0.0, x ** 3 + self.A * x + self.B))) for x in xs]
        return [(x, -y) for x, y in reversed(top)] + top[1:]

    def showEvent(self, event: Any) -> None:  # noqa: N802 (Qt name)
        self._timer.start(40)
        super().showEvent(event)

    def hideEvent(self, event: Any) -> None:  # noqa: N802 (Qt name)
        self._timer.stop()
        super().hideEvent(event)

    def _tick(self) -> None:
        self.t += 0.0045
        self.update()

    def _to_px(self, x: float, y: float, area: QRectF) -> QPointF:
        return QPointF(area.left() + (x + 2.4) / 5.9 * area.width(), area.center().y() - y / 4.6 * area.height() / 1.0)

    def paintEvent(self, event: Any) -> None:  # noqa: N802 (Qt name)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, w, h), 22, 22)
        p.setClipPath(clip)
        g = QLinearGradient(0, 0, w, h)
        g.setColorAt(0, QColor(HERO_DARK))
        g.setColorAt(1, QColor(HERO_LIGHT))
        p.fillRect(QRectF(0, 0, w, h), g)

        # the curve, on the right
        p.setOpacity(1.0 if w >= 980 else 0.3)  # narrow window: let the text and buttons win
        area = QRectF(w * 0.62, h * 0.10, w * 0.35, h * 0.80)
        pts = [self._to_px(x, y, area) for x, y in self._curve]
        path = QPainterPath(pts[0])
        for pt in pts[1:]:
            path.lineTo(pt)
        for width, alpha in ((7, 22), (2.2, 215)):  # a faint glow, then the crisp line
            c = QColor(HERO_GOLD)
            c.setAlpha(alpha)
            p.setPen(QPen(c, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

        # a glowing point with a fading trail
        n = len(pts)
        head = (self.t % 1.0) * (n - 1)
        for k in range(8, -1, -1):
            idx = max(0, int(head - k * 2))
            c = QColor("#ffffff")
            c.setAlphaF(max(0.0, 0.85 - k * 0.09))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            r = 2.5 + (8 - k) * 0.35
            p.drawEllipse(pts[idx], r, r)
        tip = pts[int(head)]
        halo = QColor(HERO_GOLD)
        halo.setAlpha(60)
        p.setBrush(halo)
        p.drawEllipse(tip, 11, 11)
        # fixed landmarks: G and a public key Q
        f = QFont(self.font())
        f.setBold(True)
        f.setPointSizeF(10.5)
        p.setFont(f)
        for label, frac in (("G", 0.30), ("Q = d·G", 0.80)):
            pt = pts[int(frac * (n - 1))]
            p.setPen(QPen(QColor("#ffffff"), 2))
            p.setBrush(QColor(HERO_DARK))
            p.drawEllipse(pt, 6, 6)
            p.setPen(QColor("#ffffff"))
            p.drawText(QRectF(pt.x() + 10, pt.y() - 14, 80, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
        p.end()


# ====================================================================== cards
class QuestCard(QPushButton):
    """A big clickable card that opens one page of the app."""

    def __init__(self, page: str, title: str, blurb: str, badge: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.page = page
        self.setObjectName("questCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(212, 92)
        self.setAccessibleName(f"{title}: {blurb}")
        self.setToolTip(f"Open {page}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(2)
        top = QHBoxLayout()
        name = QLabel(title)
        name.setObjectName("cardTitle")
        top.addWidget(name)
        top.addStretch(1)
        if badge:
            tag = QLabel(badge)
            tag.setObjectName("cardBadge")
            tag.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            top.addWidget(tag)
        lay.addLayout(top)
        text = QLabel(blurb)
        text.setObjectName("cardBlurb")
        text.setWordWrap(True)
        lay.addWidget(text)
        lay.addStretch(1)
        for child in (name, text):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


# ====================================================================== page
def _restyle(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


PAGE_STYLE = """
QLabel#heroEyebrow { color: #ffd35c; font-weight: 800; letter-spacing: 3px; font-size: 9pt; background: transparent; }
QLabel#heroTitle { color: #ffffff; font-size: 30pt; font-weight: 800; background: transparent; }
QLabel#heroSub { color: #f6e3e9; font-size: 13pt; background: transparent; }
QPushButton#heroPrimary { background: #ffd35c; color: #33091a; border: 0; border-radius: 14px; padding: 11px 22px;
    font-weight: 800; font-size: 12pt; }
QPushButton#heroPrimary:hover { background: #ffe38f; }
QPushButton#heroGhost { background: rgba(255,255,255,26); color: #ffffff; border: 1px solid rgba(255,255,255,120);
    border-radius: 14px; padding: 10px 18px; font-weight: 700; font-size: 11pt; }
QPushButton#heroGhost:hover { background: rgba(255,255,255,80); }
QLabel#sectionTitle { font-size: 15pt; font-weight: 800; }
QLabel#sectionHint { font-size: 10.5pt; }
QFrame#panel { background: @BOX@; border: 1px solid @EDGE@; border-radius: 18px; }
QFrame#factStrip { background: @BOX@; border: 1px solid @EDGE@; border-radius: 14px; }
QLabel#factIcon { font-size: 8.5pt; font-weight: 800; letter-spacing: 2px; background: transparent; }
QLabel#factText { font-size: 11pt; background: transparent; }
QPushButton#stepChip { background: @CHIP@; border: 1px solid @EDGE@; border-radius: 14px;
    padding: 6px 14px; font-weight: 700; }
QPushButton#stepChip:hover { border-color: palette(highlight); }
QPushButton#stepChip:checked { background: palette(highlight); color: palette(highlighted-text); border-color: palette(highlight); }
QLabel#frameTitle { font-size: 14pt; font-weight: 800; }
QLabel#frameText { font-size: 12pt; }
QPushButton#demoStep { background: @CHIP@; border: 1px solid @EDGE@; border-radius: 12px; padding: 10px 18px; font-weight: 700; font-size: 11pt; }
QPushButton#demoStep:hover:enabled { border-color: palette(highlight); }
QPushButton#demoStep[next="true"] { background: palette(highlight); color: palette(highlighted-text); border-color: palette(highlight); }
QPushButton#demoStep[next="true"]:disabled { background: palette(highlight); color: palette(highlighted-text); }
QLabel#badge { border: 1px solid @EDGE@; border-radius: 12px; padding: 4px 12px; font-weight: 600; }
QLabel#badge[done="true"] { background: palette(highlight); color: palette(highlighted-text); border: 1px solid palette(highlight); }
QLabel#cheer { background: palette(window); border: 1px solid palette(highlight); border-radius: 12px; padding: 10px 14px;
    font-size: 11pt; font-weight: 600; }
QLabel#trackPill { color: palette(text); border: 1px solid @EDGE@; border-radius: 10px; padding: 2px 12px; font-weight: 800; letter-spacing: 2px; font-size: 8.5pt; }
QPushButton#questCard { background: @BOX@; border: 1px solid @EDGE@; border-radius: 14px; text-align: left; }
QPushButton#questCard:hover, QPushButton#questCard:focus { border: 2px solid palette(highlight); }
QPushButton#questCard QLabel { background: transparent; }
QLabel#cardTitle { font-size: 12pt; font-weight: 800; }
QLabel#cardBlurb { font-size: 9.5pt; }
QPushButton#questCard QLabel#cardBadge { background: palette(highlight); color: palette(highlighted-text); border-radius: 8px; padding: 1px 8px; font-weight: 800; font-size: 7.5pt; letter-spacing: 1px; }
QLineEdit#messageEdit { background: @CHIP@; border: 1px solid @EDGE@; border-radius: 10px; padding: 4px 12px; font-size: 12pt; }
QLineEdit#messageEdit:focus { border-color: palette(highlight); }
QToolButton#helpToggle { border: 0; font-weight: 700; font-size: 11pt; padding: 6px 2px; }
"""


def _section(title: str, hint: str = "") -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(2, 0, 2, 0)
    lay.setSpacing(0)
    t = QLabel(title)
    t.setObjectName("sectionTitle")
    lay.addWidget(t)
    if hint:
        h = QLabel(hint)
        h.setObjectName("sectionHint")
        h.setWordWrap(True)
        lay.addWidget(h)
    return box


class TutorialTab(QWidget):
    """Start here: an animated welcome, the 60-second story, a live demo and a map of every page."""

    HELP = ("Start here if ECDSA is new to you. Watch the 60-second story, type your own message and sign it in "
            "the live demo, then pick an adventure card to jump to any other page. The sidebar is always on "
            "the left too.")

    def __init__(self, state: Any = None) -> None:
        super().__init__()
        self.state = state
        self._demo_keys: tuple[Any, Any] | None = None
        self._demo_sig: Any = None
        self._demo_msg = DEMO_MESSAGE
        self._done = {"keys": False, "signed": False, "verified": False, "caught": False}
        self.curve = get_curve(DEMO_CURVE)
        self._style_key: tuple[str, ...] | None = None
        self._apply_style()

        # ---- hero
        self.hero = HeroBanner()
        hero_row = QHBoxLayout(self.hero)
        hero_row.setContentsMargins(34, 26, 34, 26)
        left = QVBoxLayout()
        left.setSpacing(8)
        eyebrow = QLabel("DIGITAL SIGNATURES · HANDS-ON")
        eyebrow.setObjectName("heroEyebrow")
        self.welcome_heading = QLabel("Welcome to ECDSA Lab")
        self.welcome_heading.setObjectName("heroTitle")
        self.welcome_heading.setWordWrap(True)
        sub = QLabel(WELCOME)
        sub.setObjectName("heroSub")
        sub.setWordWrap(True)
        cta = QHBoxLayout()
        cta.setSpacing(10)
        self.story_cta = QPushButton("Watch the 60-second story")
        self.story_cta.setObjectName("heroPrimary")
        self.try_cta = QPushButton("Try it live")
        self.try_cta.setObjectName("heroGhost")
        for b in (self.story_cta, self.try_cta):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            cta.addWidget(b)
        cta.addStretch(1)
        left.addStretch(1)
        left.addWidget(eyebrow)
        left.addWidget(self.welcome_heading)
        left.addWidget(sub)
        left.addSpacing(8)
        left.addLayout(cta)
        left.addStretch(1)
        hero_row.addLayout(left, 11)
        hero_row.addStretch(9)

        # ---- did you know
        self._fact_i = random.randrange(len(FACTS))
        self.fact_strip = QFrame()
        self.fact_strip.setObjectName("factStrip")
        fact_row = QHBoxLayout(self.fact_strip)
        fact_row.setContentsMargins(16, 10, 14, 10)
        icon = QLabel("DID YOU KNOW")
        icon.setObjectName("factIcon")
        self.fact_label = QLabel(FACTS[self._fact_i])
        self.fact_label.setObjectName("factText")
        self.fact_label.setWordWrap(True)
        self.fact_button = QPushButton("Another fact")
        self.fact_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fact_button.clicked.connect(lambda *_: self.next_fact())
        fact_row.addWidget(icon)
        fact_row.addWidget(self.fact_label, 1)
        fact_row.addWidget(self.fact_button)

        # ---- part 1: story
        self.canvas = StoryCanvas()
        self.chips: list[QPushButton] = []
        chip_row = QHBoxLayout()
        chip_row.setSpacing(8)
        for i, label in enumerate(STEP_CHIPS):
            chip = QPushButton(f"{i + 1}  {label}")
            chip.setObjectName("stepChip")
            chip.setCheckable(True)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda checked=False, k=i: self.show_frame(k))
            chip_row.addWidget(chip)
            self.chips.append(chip)
        chip_row.addStretch(1)
        self.frame_title = QLabel()
        self.frame_title.setObjectName("frameTitle")
        self.frame_text = QLabel()
        self.frame_text.setObjectName("frameText")
        self.frame_text.setWordWrap(True)
        self.frame_text.setMinimumHeight(44)
        self.prev_button = QPushButton("◀ Previous")
        self.next_button = QPushButton("Next ▶")
        self.prev_button.clicked.connect(lambda *_: self.show_frame(self.canvas.frame - 1))
        self.next_button.clicked.connect(lambda *_: self.show_frame(self.canvas.frame + 1))
        nav = QHBoxLayout()
        nav.addWidget(self.prev_button)
        nav.addWidget(self.next_button)
        nav.addStretch(1)
        self.story = QFrame()
        self.story.setObjectName("panel")
        story_layout = QVBoxLayout(self.story)
        story_layout.setContentsMargins(18, 16, 18, 16)
        story_layout.setSpacing(10)
        story_layout.addLayout(chip_row)
        story_layout.addWidget(self.canvas)
        story_layout.addWidget(self.frame_title)
        story_layout.addWidget(self.frame_text)
        story_layout.addLayout(nav)

        # ---- part 2: try it live
        self.message_edit = QLineEdit(DEMO_MESSAGE)
        self.message_edit.setPlaceholderText("Type any message…")
        self.message_edit.setMaxLength(60)
        self.message_edit.setObjectName("messageEdit")
        self.message_edit.setMinimumHeight(38)
        self.message_edit.textEdited.connect(self._message_changed)
        msg_row = QHBoxLayout()
        msg_label = QLabel("<b>Your message:</b>")
        msg_row.addWidget(msg_label)
        msg_row.addWidget(self.message_edit, 1)
        self.keys_button = QPushButton("1. Make keys")
        self.sign_button = QPushButton("2. Sign it")
        self.verify_button = QPushButton("3. Verify")
        self.tamper_button = QPushButton("Change one letter")
        for b in (self.keys_button, self.sign_button, self.verify_button, self.tamper_button):
            b.setObjectName("demoStep")
            b.setMinimumHeight(40)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.keys_button.clicked.connect(self.make_keys)
        self.sign_button.clicked.connect(self.sign_message)
        self.verify_button.clicked.connect(self.verify_message)
        self.tamper_button.clicked.connect(self.tamper_message)
        steps = QHBoxLayout()
        steps.setSpacing(10)
        for b in (self.keys_button, self.sign_button, self.verify_button, self.tamper_button):
            steps.addWidget(b)
        self.badges: dict[str, QLabel] = {}
        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        self._badge_text = {"keys": "Keys made", "signed": "Signed", "verified": "Verified", "caught": "Forgery caught"}
        for key, text in self._badge_text.items():
            badge = QLabel(text)
            badge.setObjectName("badge")
            badge.setProperty("done", False)
            badge_row.addWidget(badge)
            self.badges[key] = badge
        badge_row.addStretch(1)
        self.keys_card, self.sign_card = QLabel(), QLabel()
        for card in (self.keys_card, self.sign_card):
            card.setWordWrap(True)
            card.setTextFormat(Qt.TextFormat.RichText)
            card.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.banner = ResultBanner()
        self.cheer = QLabel("Quest complete! You just did what ECDSA does billions of times a day. "
                            "Now pick an adventure below.")
        self.cheer.setObjectName("cheer")
        self.cheer.setWordWrap(True)
        self.cheer.hide()
        for hidden in (self.keys_card, self.sign_card, self.banner):
            hidden.hide()
        self.try_box = QFrame()
        self.try_box.setObjectName("panel")
        try_layout = QVBoxLayout(self.try_box)
        try_layout.setContentsMargins(18, 16, 18, 16)
        try_layout.setSpacing(10)
        try_layout.addLayout(msg_row)
        try_layout.addLayout(steps)
        try_layout.addLayout(badge_row)
        try_layout.addWidget(self.keys_card)
        try_layout.addWidget(self.sign_card)
        try_layout.addWidget(self.banner)
        try_layout.addWidget(self.cheer)

        # ---- part 3: pick your adventure
        self.cards: list[QuestCard] = []
        self.adventures = QWidget()
        adv = QVBoxLayout(self.adventures)
        adv.setContentsMargins(0, 0, 0, 0)
        adv.setSpacing(12)
        adv.addWidget(_section("Pick your adventure", "Every card opens a page. New here? Start with the first one."))
        for track in TRACKS:
            pill_row = QHBoxLayout()
            pill = QLabel(track.name)
            pill.setObjectName("trackPill")
            hint = QLabel(track.tagline)
            hint.setObjectName("sectionHint")
            pill_row.addWidget(pill)
            pill_row.addWidget(hint)
            pill_row.addStretch(1)
            adv.addLayout(pill_row)
            row_cards = []
            for c in track.cards:
                card = QuestCard(c.page, c.title, c.blurb, c.badge)
                card.clicked.connect(lambda checked=False, page=c.page: go_to(self, self.state, page))
                self.cards.append(card)
                row_cards.append(card)
            holder = QWidget()
            flow = FlowLayout(holder, 14)
            for card in row_cards:
                flow.addWidget(card)
            policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            policy.setHeightForWidth(True)
            holder.setSizePolicy(policy)
            adv.addWidget(holder)

        # ---- collapsible help
        self.help_toggle = QToolButton()
        self.help_toggle.setObjectName("helpToggle")
        self.help_toggle.setText("How do I use this app?")
        self.help_toggle.setCheckable(True)
        self.help_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.help_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.help_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.help_box = QFrame()
        self.help_box.setObjectName("panel")
        help_layout = QVBoxLayout(self.help_box)
        help_layout.setContentsMargins(18, 14, 18, 14)
        self.how_label = explanation(html.escape(HOW_TO_USE))
        steps_html = "".join(f"<li><b>{html.escape(stop.page)}</b>: {html.escape(stop.what)}</li>"
                             for stop in SUGGESTED_ORDER)
        self.order_label = explanation(f"Suggested order:<ol style='margin-top:4px'>{steps_html}</ol>")
        help_layout.addWidget(self.how_label)
        help_layout.addWidget(self.order_label)
        self.help_box.hide()
        self.help_toggle.toggled.connect(self._toggle_help)

        # ---- startup checkbox
        self.startup_box = QCheckBox("Show this page when the app starts")
        self.startup_box.setChecked(self.show_at_startup())
        self.startup_box.toggled.connect(lambda on: settings().setValue(SETTINGS_KEY, bool(on)))

        # ---- assemble
        self.story_section = QWidget()
        sl = QVBoxLayout(self.story_section)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(10)
        sl.addWidget(_section("ECDSA in 60 seconds", ANALOGY))
        sl.addWidget(self.story)
        self.try_section = QWidget()
        tl = QVBoxLayout(self.try_section)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(10)
        tl.addWidget(_section("Try it live", "Type a message, then click the glowing button. It uses a tiny practice "
                                              "curve and its own key, so nothing else in the app changes."))
        tl.addWidget(self.try_box)

        content = QWidget()
        page = QVBoxLayout(content)
        page.setContentsMargins(4, 4, 12, 16)
        page.setSpacing(22)
        page.addWidget(self.hero)
        page.addWidget(self.fact_strip)
        page.addWidget(self.story_section)
        page.addWidget(self.try_section)
        page.addWidget(self.adventures)
        page.addWidget(self.help_toggle)
        page.addWidget(self.help_box)
        page.addWidget(self.startup_box)
        page.addStretch(1)
        self.content = content
        content.setObjectName("startContent")
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.scroll)

        self.story_cta.clicked.connect(lambda *_: self.scroll_to(self.story_section))
        self.try_cta.clicked.connect(lambda *_: self.scroll_to(self.try_section))

        self._apply_style()
        self.show_frame(0)
        self._update_demo_buttons()

    # ------------------------------------------------------------ look
    def _apply_style(self) -> None:
        """Boxes stand out from the (unchanged) page in both themes: bright white with an edge and soft shadow in
        light mode, a clearly lighter panel colour in dark mode."""
        pal = self.palette()
        window, panel = pal.window().color(), pal.button().color()
        if window.lightness() > 128:  # light theme: bright white boxes on a slightly deeper tinted page
            box, chip, edge, shadow = QColor("#ffffff"), window, window.darker(128), True
        else:  # dark theme: a clearly lighter panel on a deeper page
            box, chip, edge, shadow = panel.lighter(150), window, panel.lighter(210), False
        key = (box.name(), chip.name(), edge.name())
        if key != self._style_key:
            self._style_key = key
            self.setStyleSheet(PAGE_STYLE.replace("@BOX@", box.name()).replace("@CHIP@", chip.name())
                               .replace("@EDGE@", edge.name()))
        lifted = list(getattr(self, "cards", [])) + [getattr(self, n) for n in ("fact_strip", "story", "try_box")
                                                     if hasattr(self, n)]
        for w in lifted:
            if shadow and w.graphicsEffect() is None:
                fx = QGraphicsDropShadowEffect(w)
                fx.setBlurRadius(24)
                fx.setOffset(0, 4)
                fx.setColor(QColor(60, 20, 30, 80))
                w.setGraphicsEffect(fx)
            elif not shadow and w.graphicsEffect() is not None:
                w.setGraphicsEffect(None)

    def changeEvent(self, event: Any) -> None:  # noqa: N802 (Qt name)
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange and hasattr(self, "cards"):
            self._apply_style()

    # ------------------------------------------------------------ tab contract
    def set_curve(self, curve: Any) -> None:
        """The tutorial always uses toy-17 so the numbers stay small."""

    @staticmethod
    def show_at_startup() -> bool:
        value = settings().value(SETTINGS_KEY, True)
        return value not in (False, "false", "0", 0)

    # ------------------------------------------------------------ small interactions
    def scroll_to(self, widget: QWidget) -> None:
        """Glide the page down to a section."""
        bar = self.scroll.verticalScrollBar()
        target = max(0, widget.mapTo(self.content, QPoint(0, 0)).y() - 8)
        self._glide = QPropertyAnimation(bar, b"value", self)
        self._glide.setDuration(450)
        self._glide.setStartValue(bar.value())
        self._glide.setEndValue(min(target, bar.maximum()) if bar.maximum() else target)
        self._glide.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._glide.start()

    def next_fact(self) -> None:
        self._fact_i = (self._fact_i + random.randrange(1, len(FACTS))) % len(FACTS)
        self.fact_label.setText(FACTS[self._fact_i])

    def _toggle_help(self, on: bool) -> None:
        self.help_box.setVisible(on)
        self.help_toggle.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)

    # ------------------------------------------------------------ story
    def show_frame(self, i: int) -> None:
        self.canvas.set_frame(i)
        frame = FRAMES[self.canvas.frame]
        self.frame_title.setText(frame.title)
        self.frame_text.setText(frame.text)
        self.prev_button.setEnabled(self.canvas.frame > 0)
        self.next_button.setEnabled(self.canvas.frame < len(FRAMES) - 1)
        for k, chip in enumerate(self.chips):
            chip.setChecked(k == self.canvas.frame)

    # ------------------------------------------------------------ live demo
    def _message(self) -> str:
        return self.message_edit.text().strip() or DEMO_MESSAGE

    def _message_changed(self, _text: str = "") -> None:
        """Editing the message makes the old signature stale, like in real life."""
        if self._demo_sig is not None:
            self._demo_sig = None
            self._set_card(self.sign_card, "")
            self._show_banner("info", "", "")
            self._done.update(signed=False, verified=False, caught=False)
            self._refresh_badges()
        self._update_demo_buttons()

    def _show_banner(self, kind: str, headline: str, detail: str) -> None:
        self.banner.show_message(kind, headline, detail)
        self.banner.setVisible(bool(headline))

    def _set_card(self, card: QLabel, text: str) -> None:
        card.setText(text)
        card.setVisible(bool(text))

    def _refresh_badges(self) -> None:
        for key, badge in self.badges.items():
            badge.setProperty("done", bool(self._done[key]))
            badge.setText(("✓  " if self._done[key] else "") + self._badge_text[key])
            _restyle(badge)
        self.cheer.setVisible(all(self._done.values()))

    def _update_demo_buttons(self, busy: bool = False) -> None:
        self.keys_button.setEnabled(not busy)
        self.sign_button.setEnabled(not busy and self._demo_keys is not None)
        self.verify_button.setEnabled(not busy and self._demo_sig is not None)
        self.tamper_button.setEnabled(not busy and self._demo_sig is not None)
        # the next thing to click glows, so a beginner always knows where to go
        if self._demo_keys is None:
            nxt = self.keys_button
        elif self._demo_sig is None:
            nxt = self.sign_button
        elif not self._done["verified"]:
            nxt = self.verify_button
        else:
            nxt = self.tamper_button
        for b in (self.keys_button, self.sign_button, self.verify_button, self.tamper_button):
            b.setProperty("next", b is nxt and not self._done["caught"])
            _restyle(b)

    def make_keys(self, *_: Any) -> None:
        self._demo_sig = None
        self._demo_msg = self._message()
        self._set_card(self.sign_card, "")
        self._show_banner("info", "", "")
        self._done.update(keys=False, signed=False, verified=False, caught=False)
        self._refresh_badges()
        self._update_demo_buttons(busy=True)
        run_in_background(generate_keypair, self.curve, on_done=self._keys_done, on_error=self._failed)

    def _keys_done(self, keys: tuple[Any, Any]) -> None:
        self._demo_keys = keys
        priv, pub = keys
        self._set_card(self.keys_card, (
            f"<b>Private key</b> d = {fmt_number(priv.d, self.curve)} <i>(secret: in real life never shown)</i><br>"
            f"<b>Public key</b> Q = {fmt_point(pub.Q, self.curve)} <i>(shared with everyone)</i>"))
        self._done["keys"] = True
        self._refresh_badges()
        self._update_demo_buttons()

    def sign_message(self, *_: Any) -> None:
        if self._demo_keys is None:
            return
        self._demo_msg = self._message()
        self._update_demo_buttons(busy=True)
        run_in_background(sign, self._demo_keys[0], self._demo_msg.encode(), on_done=self._sign_done,
                          on_error=self._failed)

    def _sign_done(self, sig: Any) -> None:
        self._demo_sig = sig
        self._set_card(self.sign_card, f"<b>Signature</b> on \"{html.escape(self._demo_msg)}\": "
                               f"r = {fmt_number(sig.r, self.curve)}, s = {fmt_number(sig.s, self.curve)}")
        self._show_banner("info", "Signed", "Now press Verify to check it as Bob would.")
        self._done["signed"] = True
        self._refresh_badges()
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
            self._show_banner("good", "VALID", f"\"{text}\" was signed with Alice's private key.")
            self._done["verified"] = True
        else:
            self._show_banner("bad", "INVALID", f"{note} The message is now \"{text}\", which is not what "
                                                       "Alice signed, so the same signature no longer fits.")
            self._done["caught"] = True
        self.banner.setToolTip(shown)
        self._refresh_badges()
        self._update_demo_buttons()

    def _tamper_that_fails(self, text: str) -> tuple[str, str]:
        """Like tamper_text, but guaranteed to break the signature. The practice curve is so small (about 19
        values) that a wrong signature verifies by luck roughly 1 time in 19, which would ruin the demo. So
        try changes outward from the middle of the message until one really fails to verify."""
        changed, what = tamper_text(text)
        if not text or self._demo_keys is None or self._demo_sig is None:
            return changed, what
        pub, sig = self._demo_keys[1], self._demo_sig
        try:
            if not verify(pub, changed.encode(), sig):
                return changed, what
            for i in sorted(range(len(text)), key=lambda k: abs(k - len(text) // 2)):
                c = text[i]
                for new in ((c.swapcase(),) if c.isalpha() and c.swapcase() != c else ()) + ("!", "?", "#", "x", "7"):
                    if new == c:
                        continue
                    cand = text[:i] + new + text[i + 1:]
                    if not verify(pub, cand.encode(), sig):
                        return cand, f"changed character {i + 1} from {c!r} to {new!r}"
        except Exception:  # never let a demo nicety break the page
            pass
        return changed, what

    def tamper_message(self, *_: Any) -> None:
        changed, what = self._tamper_that_fails(self._demo_msg)
        self.verify_message(changed, note=f"We {what}.")

    def _failed(self, exc: Exception) -> bool:
        self._update_demo_buttons()
        self._show_banner("bad", "Something went wrong", str(exc))
        return True
