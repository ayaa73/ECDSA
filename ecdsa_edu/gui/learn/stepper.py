"""Horizontal stepper for the Learn ECDSA walkthrough (P4).

Shows the reading order as numbered steps joined by arrows
(1 The curve -> 2 Key pair -> 3 Hash -> ...). Every step is a button: clicking
it jumps there. The current step is highlighted, and the row scrolls
sideways when the window is too narrow to show all of it.
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QWidget,
)

__all__ = ["StepperBar"]


class StepperBar(QScrollArea):
    """A row of clickable steps; emits ``stepClicked(index)``."""

    stepClicked = Signal(int)

    def __init__(self, labels: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("learnStepper")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)

        row = QWidget()
        self._row = row
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 4, 16, 10)  # keep rounded ends clear of the viewport edges
        layout.setSpacing(4)
        self.buttons: list[QPushButton] = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for index, label in enumerate(labels):
            if index:
                arrow = QLabel("→")
                arrow.setProperty("muted", True)
                arrow.setAccessibleName("then")
                layout.addWidget(arrow)
            button = QPushButton(f"{index + 1}  {label}")
            button.setObjectName("learnStepButton")
            button.setCheckable(True)
            button.setProperty("stepChip", True)
            button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(f"Go to step {index + 1}: {label}")
            button.clicked.connect(lambda _checked=False, i=index: self.stepClicked.emit(i))
            self._group.addButton(button, index)
            layout.addWidget(button)
            self.buttons.append(button)
        layout.addStretch(1)
        self.setWidget(row)
        self.setFixedHeight(row.sizeHint().height() + self.horizontalScrollBar().sizeHint().height())

    def set_current(self, index: int) -> None:
        """Highlight step ``index`` and scroll it into view."""
        if 0 <= index < len(self.buttons):
            self.buttons[index].setChecked(True)
            self._fit_button_widths()
            button = self.buttons[index]
            bar = self.horizontalScrollBar()
            left, right = button.x() - 16, button.geometry().right() + 16
            if left < bar.value():
                bar.setValue(max(0, left))
            elif right > bar.value() + self.viewport().width():
                bar.setValue(right - self.viewport().width())

    def _fit_button_widths(self) -> None:
        """Do not let the scrolling layout squeeze labels under rounded ends."""
        for button in self.buttons:
            text_width = button.fontMetrics().horizontalAdvance(button.text())
            button.setMinimumWidth(text_width + 44)

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self._fit_button_widths()  # fonts are final only after the page enters the window
        super().showEvent(event)

    def current(self) -> int:
        return self._group.checkedId()

    def minimumSizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        """The chips scroll horizontally, so they must not widen the whole page."""
        return QSize(0, super().minimumSizeHint().height())

    def wheelEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        event.ignore()  # a vertical wheel scrolls the page, not this row
