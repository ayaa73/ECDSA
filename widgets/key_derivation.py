"""The private-key illustration and the d · G → Q diagram."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QLayout, QPushButton, QVBoxLayout, QWidget

from ecdsa_edu.core.curve import Curve, enumerate_points
from ecdsa_edu.gui.app import current_theme
from ecdsa_edu.gui.widgets.bigint_field import BigIntField, format_bigint
from ecdsa_edu.gui.widgets.cards import Card

MANUAL_KEY_NOTE = (
    "Choose d by hand for learning only. In real ECDSA, software selects d at random "
    "using cryptographically secure randomness."
)

class _KeyPicture(QWidget):
    """Paint a single key, with no numbers or labels inside the artwork."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(87, 104)
        self.setAccessibleName("Illustration of a gold key representing the private key d")

    def paintEvent(self, event) -> None:
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            # Draw the key in its own coordinate system so it scales cleanly.
            scale = min(self.width() / 135, self.height() / 250)
            painter.translate(self.width() / 2, self.height() / 2)
            painter.scale(scale, scale)
            painter.rotate(76)
            painter.translate(-111, -49)

            bow = QPainterPath()
            bow.addEllipse(QRectF(3, 5, 87, 87))
            blade = QPainterPath(QPointF(67, 37))
            for x, y in ((201, 37), (218, 48), (205, 62), (189, 62), (189, 78),
                         (171, 78), (171, 62), (154, 62), (154, 73), (138, 73),
                         (138, 62), (67, 62)):
                blade.lineTo(x, y)
            blade.closeSubpath()
            hole = QPainterPath()
            hole.addEllipse(QRectF(25, 27, 43, 43))
            key = bow.united(blade).subtracted(hole)

            painter.save()
            painter.translate(0, 6)
            painter.fillPath(key, QColor("#D17A88"))
            painter.restore()
            rosewood = QLinearGradient(26, 3, 120, 111)
            rosewood.setColorAt(0, QColor("#D17A88"))
            rosewood.setColorAt(0.5, QColor("#A63A50"))
            rosewood.setColorAt(1, QColor("#7A1F35"))
            painter.setPen(QPen(QColor("#4A1220"), 1.25))
            painter.setBrush(rosewood)
            painter.drawPath(key)


def _label(text: str, *, wrap: bool = False, style: str = "") -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    if style:
        label.setStyleSheet(style)
    label.setWordWrap(wrap)
    return label


class _BasePointPicture(QWidget):
    """Draw the selected finite curve, or a point symbol for large fields."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(89, 71)
        self._curve: Curve | None = None
        self._points: list[tuple[int, int]] = []

    def set_curve(self, curve: Curve) -> None:
        if self._curve != curve:
            self._curve = curve
            self._points = (
                [point for point in enumerate_points(curve) if point is not None]
                if curve.p <= 127 else []
            )
            self.setAccessibleName("Base point G on the selected curve")
            self.update()

    def paintEvent(self, event) -> None:
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor("#D17A88"), 1))
            painter.setBrush(QColor("#F8E6E9"))
            painter.drawRoundedRect(QRectF(0.5, 0.5, 88, 70), 8, 8)
            for x in (17, 35, 53, 71):
                painter.drawLine(x, 9, x, 62)
            for y in (13, 28, 43, 58):
                painter.drawLine(9, y, 80, y)
            if self._curve is None:
                return
            end = self._curve.p - 1
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#D17A88"))
            for x, y in self._points:
                painter.drawEllipse(QPointF(10 + 69 * x / end, 61 - 51 * y / end), 1.7, 1.7)
            x, y = self._curve.G
            center = QPointF(10 + 69 * x / end, 61 - 51 * y / end) if self._points else QPointF(44, 34)
            painter.setBrush(QColor("#D17A88"))
            painter.drawEllipse(center, 7, 7)
            painter.setBrush(QColor("#7A1F35"))
            painter.drawEllipse(center, 3.6, 3.6)


class _PublicKeyPicture(QWidget):
    """A megaphone marks the key that can be shared."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(52, 40)

    def paintEvent(self, event) -> None:
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor("#D17A88" if current_theme() == "dark" else "#7A1F35"), 1.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(QColor("#F8E6E9"))
            horn = QPainterPath(QPointF(11, 16))
            horn.lineTo(31, 8)
            horn.lineTo(31, 29)
            horn.lineTo(11, 23)
            horn.closeSubpath()
            painter.drawPath(horn)
            painter.drawRoundedRect(QRectF(5.5, 16, 6, 7), 2, 2)
            painter.drawLine(13, 24, 17, 33)
            painter.drawLine(37, 12, 43, 8)
            painter.drawLine(38, 19, 46, 19)
            painter.drawLine(37, 26, 43, 30)


class _InputArrows(QWidget):
    """Join the private scalar and the base point at multiplication."""

    def __init__(self) -> None:
        super().__init__()
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(1600)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.valueChanged.connect(lambda _: self.update())
        self.setMinimumWidth(48)
        self.setAccessibleName("d and G feed into scalar multiplication")

    def paintEvent(self, event) -> None:
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor("#D17A88" if current_theme() == "dark" else "#7A1F35"), 1.65)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            x, y = self.width() - 4, self.height() / 2
            progress = self.animation.currentValue()
            moving = self.animation.state() == QVariantAnimation.State.Running
            join = x * 0.70
            for offset in (-6, 6):
                start_y = y + (self.height() * (-0.26 if offset < 0 else 0.28))
                end_y = y
                path = QPainterPath(QPointF(2, start_y))
                path.cubicTo(x * 0.53, start_y, join * 0.5, end_y, join, end_y)
                painter.drawPath(path)
                if moving and progress < 0.70:
                    dot = path.pointAtPercent(progress / 0.70)
                    painter.save()
                    painter.setBrush(QColor("#FFA75D" if offset < 0 else "#65BDCB"))
                    painter.drawEllipse(dot, 5, 5)
                    painter.restore()
            painter.drawLine(QPointF(join, y), QPointF(x, y))
            for offset in (-3, 3):
                painter.drawLine(QPointF(x - 5, y + offset), QPointF(x, y))
            if moving and progress >= 0.70:
                center = QPointF(join + (x - join) * (progress - 0.70) / 0.30, y)
                painter.setBrush(QColor("#E9AB57"))
                painter.drawEllipse(center, 6, 6)


class KeyDerivation(QWidget):
    """Organize the lesson as a simulator, derivation diagram, and takeaways."""

    def __init__(self, field: BigIntField, actions: QLayout, *feedback: QLabel,
                 beside: QWidget | None = None, below: QWidget | None = None) -> None:
        """``beside`` sits to the right of the d field (e.g. a Copy button) and
        ``below`` directly under it (e.g. a note about keeping d safe)."""
        super().__init__()
        simulator = Card("Simulate key generation", "yellow", "d")
        entry = simulator.body
        entry_label = _label("Private key d", style="font-weight: 600;")
        entry_label.setBuddy(field)
        entry.addWidget(entry_label)
        field_row = QHBoxLayout()
        field_row.addWidget(field, 1)
        if beside is not None:
            field_row.addWidget(beside)
        entry.addLayout(field_row)
        if below is not None:
            entry.addWidget(below)
        entry.addLayout(actions)
        for label in feedback:
            entry.addWidget(label)
        entry.addStretch()

        diagram = Card("From secret to public key", "periwinkle", "Q")
        picture = diagram.body
        source = QVBoxLayout()
        source.setSpacing(3)
        self.secret = _label("", style="font-weight: 600;")
        self.secret_value = self.secret
        policy = self.secret.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        self.secret.setSizePolicy(policy)
        source.addWidget(self.secret, alignment=Qt.AlignmentFlag.AlignHCenter)
        source.addWidget(_KeyPicture(), alignment=Qt.AlignmentFlag.AlignHCenter)
        source.addWidget(_label("Psst… it’s a secret", style="font-size: 9pt; font-style: italic;"),
                         alignment=Qt.AlignmentFlag.AlignHCenter)
        source.addSpacing(13)
        self._base_picture = _BasePointPicture()
        source.addWidget(self._base_picture, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.base_value = _label("G = —", style="font-weight: 600;")
        source.addWidget(self.base_value, alignment=Qt.AlignmentFlag.AlignHCenter)
        source.addWidget(_label("Fixed base point"), alignment=Qt.AlignmentFlag.AlignHCenter)

        output = QWidget()
        result = QVBoxLayout(output)
        result.setContentsMargins(0, 0, 0, 0)
        result.setSpacing(3)
        self.public_value = _label("Q = —", style="font-size: 13pt; font-weight: 600;")
        result.addWidget(_PublicKeyPicture(), alignment=Qt.AlignmentFlag.AlignHCenter)
        result.addWidget(self.public_value, alignment=Qt.AlignmentFlag.AlignHCenter)
        result.addWidget(_label("Public key"), alignment=Qt.AlignmentFlag.AlignHCenter)

        flow = QHBoxLayout()
        flow.setSpacing(6)
        flow.addLayout(source)
        self.arrows = _InputArrows()
        flow.addWidget(self.arrows, 1)
        flow.addWidget(_label("d · G", style="font-size: 18pt; font-weight: 650;"))
        flow.addWidget(_label("⟶"))
        flow.addWidget(output, alignment=Qt.AlignmentFlag.AlignVCenter)
        picture.addLayout(flow, 1)
        self.replay = QPushButton("Replay animation")
        self.replay.clicked.connect(self.play_merge)
        self.replay.hide()
        picture.addWidget(self.replay, alignment=Qt.AlignmentFlag.AlignRight)
        self.arrows.animation.finished.connect(lambda: self.public_value.setStyleSheet(
            "font-size: 13pt; font-weight: 700; border-bottom: 2px solid #D17A88;"))

        takeaways = Card("Why this range?", "lilac")
        for text in (
            "<b>n</b> is the order of G. After n steps of G, you return to the point at infinity.",
            "<b>0 and n</b> both give that point, which cannot serve as an ECDSA public key.",
            "<b>1 through n − 1</b> give distinct public keys. Beyond n, the points repeat: "
            "(n + 1)G gives the same point as 1G.",
        ):
            label = QLabel(text)
            label.setWordWrap(True)
            takeaways.body.addWidget(label)
        takeaways.body.addStretch()

        goal = Card("Why the key stays secret", "pink")
        table = QGridLayout()
        table.setHorizontalSpacing(14)
        table.setVerticalSpacing(9)
        table.setColumnStretch(1, 1)
        rows = (
            ("Given", "What you can find"),
            ("d and G", "Compute the public key Q = d · G efficiently."),
            ("Q and G", "Finding the private number d is infeasible on a secure curve when d is chosen at random."),
            ("Toy curve", "There are so few possible values of d that you can try them one by one."),
        )
        for row, (given, result) in enumerate(rows):
            table.addWidget(_label(given, style="font-weight: 600;"), row, 0, Qt.AlignmentFlag.AlignTop)
            table.addWidget(_label(result, wrap=True, style="font-weight: 600;" if row == 0 else ""),
                            row, 1, Qt.AlignmentFlag.AlignTop)
        goal.body.addLayout(table)
        goal.body.addStretch()

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(simulator, 0, 0)
        layout.addWidget(diagram, 0, 1)
        layout.addWidget(takeaways, 1, 0)
        layout.addWidget(goal, 1, 1)
        for card in (simulator, diagram, takeaways, goal):
            card.body.setContentsMargins(14, 13, 14, 13)
            card.body.setSpacing(7)
        self.cards = (simulator, diagram, takeaways, goal)
        self.compact = False
        layout.setColumnStretch(0, 4)
        layout.setColumnStretch(1, 6)

    def set_compact(self, compact: bool) -> None:
        if self.compact == compact:
            return
        self.compact = compact
        layout = self.layout()
        for index, card in enumerate(self.cards):
            layout.removeWidget(card)
            row, column = (index, 0) if compact else divmod(index, 2)
            layout.addWidget(card, row, column)
        layout.setColumnStretch(1, 0 if compact else 6)

    def play_merge(self) -> None:
        self.arrows.animation.stop()
        self.public_value.setStyleSheet("font-size: 13pt; font-weight: 600;")
        self.arrows.animation.start()

    def update_values(
        self,
        d: int | None,
        curve: Curve,
        Q: tuple[int, int] | None,
        *,
        hidden: bool = False,
        use_hex: bool = False,
    ) -> None:
        self.secret.setVisible(d is not None)
        secret = "hidden" if hidden or d is None else self._short(d, use_hex, 14)
        self.secret_value.setText(f"d = {secret}" if d is not None else "")
        self._base_picture.set_curve(curve)
        self._set_point(self.base_value, "G", curve.G, use_hex)
        self.replay.setVisible(Q is not None and d is not None)
        if Q is None:
            self.arrows.animation.stop()
            self.public_value.setStyleSheet("font-size: 13pt; font-weight: 600;")
            self.public_value.setText("Q = …" if d is not None else "Q = —")
            self.public_value.setToolTip("Compute the public key to see Q." if d is not None else "")
        else:
            self._set_point(self.public_value, "Q", Q, use_hex)

    @staticmethod
    def _short(value: int, use_hex: bool, limit: int) -> str:
        text = format_bigint(value, use_hex)
        return text if len(text) <= limit else f"{text[:limit - 1]}…"

    @classmethod
    def _set_point(cls, label: QLabel, name: str, point: tuple[int, int], use_hex: bool) -> None:
        x, y = (cls._short(coord, use_hex, 6) for coord in point)
        label.setText(f"{name} = ({x}, {y})")
        label.setToolTip(f"{name} = ({format_bigint(point[0], use_hex)}, {format_bigint(point[1], use_hex)})")
