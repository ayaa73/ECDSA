"""Reusable dashboard cards and page headers."""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from PySide6.QtGui import QColor, QPainter, QPainterPath


def make_page_header(title: str, subtitle: str) -> QWidget:
    wrapper = QWidget()
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    title_label = QLabel(title)
    title_label.setProperty("heading", "hero")
    title_label.setWordWrap(True)
    sub = QLabel(subtitle)
    sub.setProperty("muted", True)
    sub.setMaximumWidth(640)
    sub.setWordWrap(True)
    layout.addWidget(title_label)
    layout.addWidget(sub)
    return wrapper


class Card(QFrame):
    """Flat, antialiased colour block with a clipped tone-on-tone motif."""
    def __init__(self, title: str, color: str = "white", step: str = "", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("card", color)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(20, 20, 20, 20)
        self.body.setSpacing(12)
        row = QHBoxLayout()
        icon = QLabel(step or "i")
        icon.setProperty("step", True)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(32, 32)
        label = QLabel(title)
        label.setProperty("cardHeader", True)
        row.addWidget(icon)
        row.addWidget(label, 1)
        self.body.addLayout(row)
    def paintEvent(self, event):  # noqa: N802
        from ecdsa_edu.gui.app import current_theme, theme_colors
        colors = theme_colors(current_theme())
        color = self.property("card") or "white"
        fill = QColor(colors.get(color, colors["panel"]))
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 18, 18)
        painter.fillPath(path, fill)
        if color != "white":
            painter.setClipPath(path)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill.darker(112))
            # An off-edge circle gives the card a subtle, flat decorative shape.
            painter.drawEllipse(QRectF(self.width() - 72, -55, 130, 130))
