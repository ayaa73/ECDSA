"""Overview page: one interactive picture of the whole ECDSA process.

The page draws the flow "curve -> keys -> message -> hash -> nonce -> signature
-> verify -> valid / invalid" as rounded boxes joined by curved arrows. Hovering
(or arrow-keying to) a box lifts its formulas up from behind it; clicking it
(or pressing Enter) calls ``state.go_to(page_title)`` to open the page that
explains that step. Nothing here does cryptography: the text is documentation,
and the colours come from the current Qt palette, so light and dark mode both work.

Used by: main_window.py (needs a PAGE_SPECS row, see ``PAGE_TITLE`` below).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import (
    QEasingCurve, QEvent, QPointF, QRectF, Qt, QVariantAnimation, Signal,
)
from PySide6.QtGui import (
    QColor, QFont, QFontDatabase, QFontMetricsF, QPainter, QPainterPath, QPalette, QPen,
)
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

__all__ = ["OverviewTab", "NODES", "EDGES", "PAGE_TITLE"]

PAGE_TITLE = "Overview"  # title P2 adds to PAGE_SPECS and to the go_to() list

# Everything is laid out on a fixed "logical" canvas and scaled to fit the window.
LOGICAL_W, LOGICAL_H = 1100.0, 570.0
NODE_W, NODE_H = 180.0, 68.0
RADIUS = 16.0


@dataclass(frozen=True)
class Node:
    key: str
    title: str
    role: str        # "alice" | "bob" | "shared" | "danger"
    x: float
    y: float
    page: str        # page title for state.go_to()
    blurb: str       # one plain-English line
    formulas: tuple[str, ...]  # at most 3 lines

    @property
    def rect(self) -> QRectF:
        return QRectF(self.x, self.y, NODE_W, NODE_H)


ROLE_CAPTION = {"alice": "Alice", "bob": "Bob", "shared": "Alice and Bob", "danger": "Attacker"}

# Reading order (rows left to right, then down) also drives keyboard navigation.
NODES: tuple[Node, ...] = (
    Node("curve", "Curve and G", "shared", 30, 160, "Curve Explorer",
         "Everyone agrees on one curve and a start point G.",
         ("y\u00b2 = x\u00b3 + a\u00b7x + b  (mod p)", "n\u00b7G = O   (n is prime)")),
    Node("priv", "Private key d", "alice", 250, 160, "Keys",
         "A secret number only Alice knows.",
         ("d is random in [1, n\u22121]",)),
    Node("pub", "Public key Q", "shared", 470, 160, "Keys",
         "Alice's public stamp. Anyone may see it.",
         ("Q = d\u00b7G", "Going back from Q to d is the ECDLP: too hard")),
    Node("msg", "Message", "alice", 30, 320, "Sign",
         "The text or file Alice wants to sign.",
         ("m = any bytes",)),
    Node("hash", "Hash  e", "alice", 250, 320, "Sign",
         "A short fingerprint of the message.",
         ("e = H(m), cut to the bit size of n",)),
    Node("nonce", "Nonce k and R", "alice", 470, 320, "Sign",
         "A one-time secret number, turned into a point.",
         ("k = RFC 6979(d, e)", "R = k\u00b7G")),
    Node("sig", "Signature (r, s)", "alice", 690, 320, "Sign",
         "Two numbers that only Alice could make.",
         ("r = x(R) mod n", "s = k\u207b\u00b9 \u00b7 (e + r\u00b7d) mod n")),
    Node("verify", "Verify", "bob", 910, 320, "Verify",
         "Bob checks the signature with Q alone.",
         ("w = s\u207b\u00b9 mod n,  u1 = e\u00b7w,  u2 = r\u00b7w", "P = u1\u00b7G + u2\u00b7Q")),
    Node("result", "Valid or invalid", "bob", 910, 470, "Verify",
         "Match means nothing changed.",
         ("valid  \u21d4  x(P) mod n = r",)),
    Node("attack", "Reused k breaks it", "danger", 690, 470, "Attack Demo",
         "Two signatures with the same k reveal d.",
         ("k = (e1 \u2212 e2) / (s1 \u2212 s2)", "d = (s1\u00b7k \u2212 e1) / r")),
)
NODE_BY_KEY = {node.key: node for node in NODES}


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    src_side: str  # "l" "r" "t" "b"
    dst_side: str
    dashed: bool = False
    label: str = ""


EDGES: tuple[Edge, ...] = (
    Edge("curve", "priv", "r", "l"),
    Edge("priv", "pub", "r", "l"),
    Edge("priv", "nonce", "b", "t"),
    Edge("msg", "hash", "r", "l"),
    Edge("hash", "nonce", "r", "l"),
    Edge("nonce", "sig", "r", "l"),
    Edge("sig", "verify", "r", "l"),
    Edge("pub", "verify", "r", "t"),
    Edge("verify", "result", "b", "t"),
    Edge("sig", "attack", "b", "t", dashed=True, label="if k repeats"),
)


def _theme(palette: QPalette) -> dict[str, QColor]:
    """Pick light or dark colours from the palette so the page follows the app theme."""
    dark = palette.window().color().lightness() < 128
    if dark:
        raw = {
            "alice": ("#1c2b43", "#6689bc"), "bob": ("#1c2b43", "#6689bc"),
            "shared": ("#1c2b43", "#6689bc"), "danger": ("#1c2b43", "#6689bc"),
            "text": "#edf3fc", "muted": "#aabbd3", "edge": "#667b9d", "accent": "#6286b8",
            "popup": "#17243a", "shadow": "#000000",
        }
    else:
        raw = {
            "alice": ("#dce9ff", "#2f63ad"), "bob": ("#dce9ff", "#2f63ad"),
            "shared": ("#dce9ff", "#2f63ad"), "danger": ("#dce9ff", "#2f63ad"),
            "text": "#102b56", "muted": "#365f99", "edge": "#426b9f", "accent": "#194f91",
            "popup": "#eaf2ff", "shadow": "#173e73",
        }
    theme: dict[str, QColor] = {}
    for role in ("alice", "bob", "shared", "danger"):
        fill, border = raw[role]
        theme[f"{role}_fill"], theme[f"{role}_border"] = QColor(fill), QColor(border)
    for name in ("text", "muted", "edge", "accent", "popup", "shadow"):
        theme[name] = QColor(raw[name])
    theme["is_dark"] = QColor("#000000") if dark else QColor("#ffffff")
    return theme


def _is_dark(theme: dict[str, QColor]) -> bool:
    return theme["is_dark"].lightness() < 128


_NORMALS = {"r": (1.0, 0.0), "l": (-1.0, 0.0), "t": (0.0, -1.0), "b": (0.0, 1.0)}


def _anchor(node: Node, side: str) -> QPointF:
    rect = node.rect
    return {"r": QPointF(rect.right(), rect.center().y()), "l": QPointF(rect.left(), rect.center().y()),
            "t": QPointF(rect.center().x(), rect.top()), "b": QPointF(rect.center().x(), rect.bottom())}[side]


class _OverviewCanvas(QWidget):
    """Paints the diagram and handles hover, focus, keyboard and clicks."""

    nodeActivated = Signal(str)  # page title

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(1040, 560)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName("ECDSA overview diagram")
        self.setAccessibleDescription(
            "Boxes for each ECDSA step. Use the arrow keys to move between boxes.")
        self.navigation_enabled = False
        self._mouse_key: str | None = None
        self._focus_key: str | None = None
        self._pressed_key: str | None = None
        self._keyboard_mode = False
        self._target: str | None = None        # box currently highlighted
        self._popup_key: str | None = None     # box whose formulas are showing (stays while fading out)
        self._progress = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.valueChanged.connect(self._on_progress)
        self._anim.finished.connect(self._on_finished)

    # ---- geometry ---------------------------------------------------------
    def _scale_and_offset(self) -> tuple[float, float, float]:
        scale = min(self.width() / LOGICAL_W, self.height() / LOGICAL_H)
        return scale, (self.width() - LOGICAL_W * scale) / 2, (self.height() - LOGICAL_H * scale) / 2

    def _to_logical(self, pos: QPointF) -> QPointF:
        scale, ox, oy = self._scale_and_offset()
        return QPointF((pos.x() - ox) / scale, (pos.y() - oy) / scale)

    def node_center(self, key: str) -> QPointF:
        """Centre of a box in widget pixels (used by tests)."""
        scale, ox, oy = self._scale_and_offset()
        center = NODE_BY_KEY[key].rect.center()
        return QPointF(ox + center.x() * scale, oy + center.y() * scale)

    def _node_at(self, pos: QPointF) -> str | None:
        point = self._to_logical(pos)
        for node in NODES:
            if node.rect.contains(point):
                return node.key
        return None

    # ---- hover / focus state ------------------------------------------------
    @property
    def highlighted(self) -> str | None:
        return self._target

    @property
    def popup_progress(self) -> float:
        return self._progress

    def set_navigation_enabled(self, enabled: bool) -> None:
        """Enable click-through only when the host provides a navigation callback."""
        self.navigation_enabled = enabled
        suffix = " Press Enter to open that page." if enabled else " Page navigation is coming soon."
        self.setAccessibleDescription("Boxes for each ECDSA step. Use the arrow keys to move between boxes." + suffix)

    def _refresh_target(self) -> None:
        active = self._mouse_key or (
            self._focus_key if self.hasFocus() and self._keyboard_mode else None
        )
        if active == self._target:
            return
        self._target = active
        self._anim.stop()
        if active is not None:
            if self._popup_key != active:
                self._popup_key, self._progress = active, 0.0
            curve = QEasingCurve(QEasingCurve.Type.OutBack)
            curve.setOvershoot(1.3)
            self._anim.setEasingCurve(curve)
            self._anim.setDuration(320)
            self._anim.setStartValue(self._progress)
            self._anim.setEndValue(1.0)
        else:
            self._anim.setEasingCurve(QEasingCurve.Type.InCubic)
            self._anim.setDuration(180)
            self._anim.setStartValue(self._progress)
            self._anim.setEndValue(0.0)
        self._anim.start()
        self.update()

    def _on_progress(self, value) -> None:
        self._progress = float(value)
        self.update()

    def _on_finished(self) -> None:
        if self._target is None:
            self._popup_key, self._progress = None, 0.0
        else:
            self._progress = 1.0
        self.update()

    # ---- events -------------------------------------------------------------
    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        key = self._node_at(event.position())
        clickable = key is not None and self.navigation_enabled
        self.setCursor(Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor)
        if key != self._mouse_key:
            self._mouse_key = key
            self._refresh_target()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._mouse_key = None
        self._refresh_target()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._pressed_key = self._node_at(event.position())
        # A modal navigation dialog temporarily removes and restores focus. Keep
        # that restoration from activating the first keyboard node afterward.
        self._keyboard_mode = False
        self._focus_key = None
        self.setFocus(Qt.FocusReason.MouseFocusReason)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        key = self._node_at(event.position())
        if self.navigation_enabled and key is not None and key == self._pressed_key:
            self.nodeActivated.emit(NODE_BY_KEY[key].page)
        self._pressed_key = None

    def focusInEvent(self, event) -> None:  # noqa: N802
        super().focusInEvent(event)
        if event.reason() in (
            Qt.FocusReason.TabFocusReason,
            Qt.FocusReason.BacktabFocusReason,
            Qt.FocusReason.ShortcutFocusReason,
        ):
            self._keyboard_mode = True
        if self._keyboard_mode and self._focus_key is None:
            self._focus_key = NODES[0].key
        self._refresh_target()

    def focusOutEvent(self, event) -> None:  # noqa: N802
        super().focusOutEvent(event)
        self._refresh_target()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        order = [node.key for node in NODES]
        current = order.index(self._focus_key) if self._focus_key in order else -1
        key = event.key()
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self._keyboard_mode = True
            self._focus_key = order[(current + 1) % len(order)]
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self._keyboard_mode = True
            self._focus_key = order[(current - 1) % len(order)]
        elif key == Qt.Key.Key_Home:
            self._keyboard_mode = True
            self._focus_key = order[0]
        elif key == Qt.Key.Key_End:
            self._keyboard_mode = True
            self._focus_key = order[-1]
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if self.navigation_enabled and self._focus_key is not None:
                self.nodeActivated.emit(NODE_BY_KEY[self._focus_key].page)
            return
        else:
            super().keyPressEvent(event)
            return
        self._refresh_target()
        self.update()

    def changeEvent(self, event) -> None:  # noqa: N802
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange):
            self.update()  # colours are re-read from the palette on every paint
        super().changeEvent(event)

    # ---- painting -----------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        theme = _theme(self.palette())
        scale, ox, oy = self._scale_and_offset()
        painter.translate(ox, oy)
        painter.scale(scale, scale)

        for edge in EDGES:
            self._draw_edge(painter, theme, edge)
        for node in NODES:
            if node.key != self._popup_key:
                self._draw_node(painter, theme, node)
        if self._popup_key is not None:
            node = NODE_BY_KEY[self._popup_key]
            self._draw_popup(painter, theme, node)
            self._draw_node(painter, theme, node)  # the box sits in front, so the popup rises from behind it
        painter.end()

    def _draw_edge(self, painter: QPainter, theme: dict[str, QColor], edge: Edge) -> None:
        src, dst = NODE_BY_KEY[edge.src], NODE_BY_KEY[edge.dst]
        hot = self._target in (edge.src, edge.dst)
        faded = self._target is not None and not hot
        color = QColor(theme["accent"] if hot else theme["edge"])
        color.setAlphaF(0.3 if faded else 1.0)
        n1, n2 = _NORMALS[edge.src_side], _NORMALS[edge.dst_side]
        start, end = _anchor(src, edge.src_side), _anchor(dst, edge.dst_side)
        start = QPointF(start.x() + n1[0] * 4, start.y() + n1[1] * 4)
        end = QPointF(end.x() + n2[0] * 4, end.y() + n2[1] * 4)
        reach = max(40.0, math.hypot(end.x() - start.x(), end.y() - start.y()) * 0.42)
        c1 = QPointF(start.x() + n1[0] * reach, start.y() + n1[1] * reach)
        c2 = QPointF(end.x() + n2[0] * reach, end.y() + n2[1] * reach)
        tx, ty = end.x() - c2.x(), end.y() - c2.y()
        length = math.hypot(tx, ty) or 1.0
        tx, ty = tx / length, ty / length
        head = 12.0
        base = QPointF(end.x() - tx * head * 0.7, end.y() - ty * head * 0.7)

        width = 3.4 if hot else 2.4
        pen = QPen(color, width, Qt.PenStyle.DashLine if edge.dashed else Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath(start)
        path.cubicTo(c1, c2, base)
        painter.drawPath(path)

        # Rounded arrowhead: a small filled triangle whose corners are softened by a round pen.
        px, py = -ty, tx
        arrow = QPainterPath(end)
        arrow.lineTo(end.x() - tx * head + px * head * 0.5, end.y() - ty * head + py * head * 0.5)
        arrow.lineTo(end.x() - tx * head - px * head * 0.5, end.y() - ty * head - py * head * 0.5)
        arrow.closeSubpath()
        painter.setPen(QPen(color, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(color)
        painter.drawPath(arrow)

        if edge.label:
            mid = path.pointAtPercent(0.5)
            font = QFont(self.font())
            font.setPixelSize(14)
            font.setItalic(True)
            painter.setFont(font)
            metrics = QFontMetricsF(font)
            box = QRectF(mid.x() + 10, mid.y() - 11, metrics.horizontalAdvance(edge.label) + 16, 22)
            painter.setPen(Qt.PenStyle.NoPen)
            fill = QColor(theme["popup"])
            fill.setAlphaF(0.3 if faded else 0.95)
            painter.setBrush(fill)
            painter.drawRoundedRect(box, 11, 11)
            painter.setPen(color)
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, edge.label)

    def _draw_node(self, painter: QPainter, theme: dict[str, QColor], node: Node) -> None:
        hot = node.key == self._target
        keyboard = node.key == self._focus_key and self.hasFocus()
        dimmed = self._target is not None and not hot and not self._connected(node.key)
        rect = node.rect.translated(0, -3 if hot else 0)
        painter.save()
        painter.setOpacity(0.55 if dimmed else 1.0)

        shadow = QColor(theme["shadow"])
        shadow.setAlphaF(0.35 if _is_dark(theme) else 0.16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow)
        painter.drawRoundedRect(rect.translated(0, 4 if hot else 2), RADIUS, RADIUS)
        if hot:  # soft halo, so the highlight is a shape change and not only a colour change
            for grow, alpha in ((9, 0.10), (6, 0.16), (3, 0.24)):
                halo = QColor(theme[f"{node.role}_border"])
                halo.setAlphaF(alpha)
                painter.setBrush(halo)
                painter.drawRoundedRect(rect.adjusted(-grow, -grow, grow, grow), RADIUS + grow, RADIUS + grow)

        painter.setPen(QPen(theme[f"{node.role}_border"], 3.6 if hot else 2.0))
        painter.setBrush(theme[f"{node.role}_fill"])
        painter.drawRoundedRect(rect, RADIUS, RADIUS)

        title_font = QFont("Georgia")
        title_font.setPixelSize(18)
        title_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(title_font)
        painter.setPen(theme["text"])
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 8, rect.width() - 16, 28),
                         Qt.AlignmentFlag.AlignCenter, node.title)
        caption_font = QFont("Georgia")
        caption_font.setPixelSize(14)
        caption_font.setWeight(QFont.Weight.DemiBold)
        caption = f"{ROLE_CAPTION[node.role]}  \u00b7  {node.page}"
        available = rect.width() - 16
        while caption_font.pixelSize() > 10 and QFontMetricsF(caption_font).horizontalAdvance(caption) > available:
            caption_font.setPixelSize(caption_font.pixelSize() - 1)
        painter.setFont(caption_font)
        painter.setPen(theme["muted"])
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 36, rect.width() - 16, 22),
                         Qt.AlignmentFlag.AlignCenter, caption)
        if keyboard:  # keyboard focus ring
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(theme["text"], 2, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(rect.adjusted(-8, -8, 8, 8), RADIUS + 8, RADIUS + 8)
        painter.restore()

    @staticmethod
    def _connected_keys(key: str) -> set[str]:
        return {key} | {e.dst for e in EDGES if e.src == key} | {e.src for e in EDGES if e.dst == key}

    def _connected(self, key: str) -> bool:
        return self._target is not None and key in self._connected_keys(self._target)

    def _draw_popup(self, painter: QPainter, theme: dict[str, QColor], node: Node) -> None:
        title_font = QFont("Georgia"); title_font.setPixelSize(17); title_font.setWeight(QFont.Weight.DemiBold)
        blurb_font = QFont("Georgia"); blurb_font.setPixelSize(14); blurb_font.setWeight(QFont.Weight.Medium)
        formula_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont); formula_font.setPixelSize(15)
        hint_font = QFont("Georgia"); hint_font.setPixelSize(13); hint_font.setItalic(True)
        hint = (f"Click to open \u201c{node.page}\u201d" if self.navigation_enabled
                else f"{node.page} page \u00b7 navigation coming soon")

        widths = [QFontMetricsF(title_font).horizontalAdvance(node.title),
                  QFontMetricsF(blurb_font).horizontalAdvance(node.blurb),
                  QFontMetricsF(hint_font).horizontalAdvance(hint)]
        widths += [QFontMetricsF(formula_font).horizontalAdvance(line) for line in node.formulas]
        width = min(LOGICAL_W - 16, max(300.0, max(widths) + 36))
        height = 14 + 24 + 22 + 8 + 24 * len(node.formulas) + 6 + 22 + 8

        rect = node.rect
        left = min(max(8.0, rect.center().x() - width / 2), LOGICAL_W - width - 8)
        final_top = max(4.0, rect.top() - 10 - height)
        hidden_top = rect.top() + NODE_H * 0.45 - height  # bottom edge tucked behind the box
        top = hidden_top + (final_top - hidden_top) * self._progress
        box = QRectF(left, top, width, height)

        painter.save()
        painter.setOpacity(max(0.0, min(1.0, self._progress * 2.2)))
        shadow = QColor(theme["shadow"])
        shadow.setAlphaF(0.4 if _is_dark(theme) else 0.2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow)
        painter.drawRoundedRect(box.translated(0, 5), RADIUS, RADIUS)
        painter.setPen(QPen(theme[f"{node.role}_border"], 2.4))
        painter.setBrush(theme["popup"])
        painter.drawRoundedRect(box, RADIUS, RADIUS)

        y = box.top() + 14
        painter.setFont(title_font); painter.setPen(theme["text"])
        painter.drawText(QRectF(box.left() + 18, y, width - 36, 24), Qt.AlignmentFlag.AlignVCenter, node.title)
        y += 24
        painter.setFont(blurb_font); painter.setPen(theme["muted"])
        painter.drawText(QRectF(box.left() + 18, y, width - 36, 22), Qt.AlignmentFlag.AlignVCenter, node.blurb)
        y += 30
        painter.setFont(formula_font); painter.setPen(theme["text"])
        for line in node.formulas:
            painter.drawText(QRectF(box.left() + 18, y, width - 36, 24), Qt.AlignmentFlag.AlignVCenter, line)
            y += 24
        y += 6
        painter.setFont(hint_font); painter.setPen(theme["accent"])
        painter.drawText(QRectF(box.left() + 18, y, width - 36, 22), Qt.AlignmentFlag.AlignVCenter, hint)
        painter.restore()


class OverviewTab(QWidget):
    """The "Overview" page: ECDSA at a glance, with links to every other page."""

    HELP = ("This picture shows the whole ECDSA story from start to finish. "
            "Move the mouse over a box to see its formulas pop up. "
            "Click a box to open the page that explains it. "
            "You can also use the arrow keys and Enter.")

    def __init__(self, state, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state

        heading = QLabel("ECDSA at a glance")
        font = QFont("Georgia")
        font.setWeight(QFont.Weight.DemiBold)
        font.setPointSize(18)
        heading.setFont(font)
        navigation_enabled = callable(getattr(state, "go_to", None))
        hint_text = ("Hover over a box to see its formulas. Click it to open that page."
                     if navigation_enabled
                     else "Hover over a box to see its formulas. Page navigation is coming soon.")
        hint = QLabel(hint_text)
        hint.setFont(QFont("Georgia", 10))
        hint.setWordWrap(True)

        self.canvas = _OverviewCanvas()
        self.canvas.set_navigation_enabled(navigation_enabled)
        self.canvas.nodeActivated.connect(self._open_page)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidget(self.canvas)

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(hint)
        layout.addWidget(self.scroll, 1)

    def set_curve(self, curve) -> None:
        """The overview is the same for every curve."""

    def _open_page(self, page_title: str) -> None:
        """Send the user to the page for the clicked step (does nothing without go_to)."""
        go_to = getattr(self._state, "go_to", None)
        if callable(go_to):
            go_to(page_title)
