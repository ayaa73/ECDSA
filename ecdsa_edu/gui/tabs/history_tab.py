"""History page (owner: P4): where ECDSA came from, on a clickable timeline.

A horizontal timeline shows one dot per milestone, colored by category and
labelled with the year (color is never the only signal). Filter chips hide or
show categories. Clicking a dot, or using the Left/Right arrow keys, shows the
story, why it matters for ECDSA, the source link, and a "See it in the app"
button for milestones that match one of our pages.

The milestones and their sources live in history_data.py.
"""
from __future__ import annotations

import html
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from ecdsa_edu.gui.tabs.history_data import CATEGORIES, MILESTONES, Milestone, filter_milestones
from ecdsa_edu.gui.tabs.p4_widgets import explanation, go_to, heading
from ecdsa_edu.gui.widgets.cards import Card

__all__ = ["HistoryTab", "TimelineStrip"]

SPACING = 92  # pixels between milestones
MARGIN_X = 50


class TimelineStrip(QWidget):
    """The painted timeline. Emits clicked(index into self.items)."""

    clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.items: list[Milestone] = []
        self.selected = -1
        self.setMinimumHeight(130)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Timeline of ECDSA milestones")

    def set_items(self, items: list[Milestone], selected: int) -> None:
        self.items = items
        self.selected = selected
        self.setFixedSize(max(600, 2 * MARGIN_X + SPACING * max(len(items) - 1, 0)), 130)
        self.update()

    def _x(self, i: int) -> float:
        return MARGIN_X + i * SPACING

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802 (Qt name)
        x = event.position().x()
        for i in range(len(self.items)):
            if abs(x - self._x(i)) <= SPACING / 2:
                self.clicked.emit(i)
                return

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        y = 55.0
        if self.items:
            p.setPen(QPen(QColor("#9aa7b8"), 3))
            p.drawLine(QPointF(self._x(0) - 20, y), QPointF(self._x(len(self.items) - 1) + 20, y))
        small = QFont(self.font())
        small.setPointSizeF(max(8.0, small.pointSizeF() - 1))
        bold = QFont(self.font())
        bold.setBold(True)
        for i, m in enumerate(self.items):
            x = self._x(i)
            cat = CATEGORIES[m.category]
            radius = 11
            p.setPen(QPen(QColor("#141414"), 3 if i == self.selected else 2))
            p.setBrush(QColor(cat.color))
            p.drawEllipse(QPointF(x, y), radius, radius)
            p.setPen(QColor("#1f2a44"))
            p.setFont(bold)
            p.drawText(QRectF(x - 40, 15, 80, 20), Qt.AlignmentFlag.AlignCenter, str(m.year))
            p.setFont(small)
            p.setPen(QColor("#141414"))
            p.drawText(QRectF(x - SPACING / 2, 72, SPACING, 40),
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                       cat.label)
        p.end()


class HistoryTab(QWidget):
    """Where ECDSA came from: 1976 to today."""

    HELP = ("A short history of ECDSA, from the invention of public-key cryptography to today's standards. Click a "
            "dot on the timeline (or use the Left and Right arrow keys) to read what happened and why it matters. "
            "Use the boxes to show only some kinds of events. \"See it in the app\" opens the page that shows "
            "that idea.")

    def __init__(self, state: Any = None) -> None:
        super().__init__()
        self.state = state
        self.active: set[str] = set(CATEGORIES)
        self.items: list[Milestone] = list(MILESTONES)
        self.index = 0

        # ---- filter chips (checkboxes with the category color as a swatch + label)
        chips = QHBoxLayout()
        chips.addWidget(QLabel("<b>Show:</b>"))
        self.chips: dict[str, QCheckBox] = {}
        for key, cat in CATEGORIES.items():
            box = QPushButton(cat.label)
            box.setCheckable(True)
            box.setChecked(True)
            box.setProperty("chip", True)
            box.toggled.connect(lambda on, k=key: self.set_category(k, on))
            chips.addWidget(box)
            self.chips[key] = box
        chips.addStretch(1)

        # ---- timeline
        self.strip = TimelineStrip()
        self.strip.clicked.connect(self.select)
        strip_scroll = QScrollArea()
        strip_scroll.setWidget(self.strip)
        strip_scroll.setFixedHeight(160)
        strip_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.strip_scroll = strip_scroll

        self.prev_button = QPushButton("◀ Earlier")
        self.next_button = QPushButton("Later ▶")
        self.prev_button.clicked.connect(lambda *_: self.select(self.index - 1))
        self.next_button.clicked.connect(lambda *_: self.select(self.index + 1))
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, activated=lambda: self.select(self.index - 1))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, activated=lambda: self.select(self.index + 1))
        nav = QHBoxLayout()
        nav.addWidget(self.prev_button)
        nav.addWidget(self.next_button)
        nav.addStretch(1)

        # ---- details
        self.detail_title = QLabel()
        self.detail_title.setWordWrap(True)
        self.detail_title.setProperty("heading", "section")
        self.detail_category = QLabel()
        self.story = explanation("")
        self.why = explanation("")
        self.source = QLabel()
        self.source.setOpenExternalLinks(True)
        self.source.setWordWrap(True)
        self.source.setTextFormat(Qt.TextFormat.RichText)
        self.see_button = QPushButton()
        self.see_button.clicked.connect(self.open_page)
        self.empty_note = QLabel("No events match. Tick at least one box above.")
        details = Card("What happened", "periwinkle")
        self.details = details
        dl = details.body
        for w in (self.detail_title, self.detail_category, self.story, self.why, self.source):
            dl.addWidget(w)
        dl.addWidget(self.see_button, alignment=Qt.AlignmentFlag.AlignLeft)
        dl.addWidget(self.empty_note)
        dl.addStretch(1)

        content = QWidget()
        page = QVBoxLayout(content)
        page.addWidget(heading("History: where ECDSA came from"))
        page.addWidget(explanation(
            "ECDSA did not appear overnight. It grew out of 1970s public-key ideas, 1980s elliptic-curve math and "
            "1990s standards, and it has been shaped by real attacks ever since."))
        page.addLayout(chips)
        page.addWidget(strip_scroll)
        page.addLayout(nav)
        page.addWidget(details, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._refresh()

    # ------------------------------------------------------------ tab contract
    def set_curve(self, curve: Any) -> None:
        """History does not depend on the selected curve."""

    # ------------------------------------------------------------ behaviour
    def set_category(self, key: str, on: bool) -> None:
        current = self.items[self.index] if 0 <= self.index < len(self.items) else None
        if on:
            self.active.add(key)
        else:
            self.active.discard(key)
        self.items = filter_milestones(self.active)
        # keep the same milestone selected if it is still visible
        self.index = self.items.index(current) if current in self.items else 0
        self._refresh()

    def select(self, i: int) -> None:
        if not self.items:
            return
        self.index = max(0, min(i, len(self.items) - 1))
        self._refresh()
        self.strip_scroll.ensureVisible(int(MARGIN_X + self.index * SPACING), 50, SPACING, 0)

    def current(self) -> Milestone | None:
        return self.items[self.index] if 0 <= self.index < len(self.items) else None

    def open_page(self, *_: Any) -> None:
        m = self.current()
        if m is not None and m.page:
            go_to(self, self.state, m.page)

    def _refresh(self) -> None:
        self.strip.set_items(self.items, self.index if self.items else -1)
        m = self.current()
        has = m is not None
        for w in (self.detail_title, self.detail_category, self.story, self.why, self.source):
            w.setVisible(has)
        self.empty_note.setVisible(not has)
        self.prev_button.setEnabled(has and self.index > 0)
        self.next_button.setEnabled(has and self.index < len(self.items) - 1)
        self.see_button.setVisible(bool(has and m.page))
        if not has:
            return
        cat = CATEGORIES[m.category]
        self.details.setProperty("card", {"math": "periwinkle", "standard": "olive", "real-world": "yellow", "attack": "pink"}[m.category])
        self.details.update()
        self.detail_title.setText(f"{m.year}: {html.escape(m.title)}")
        self.detail_category.setText(cat.label)
        self.story.setText(html.escape(m.story))
        self.why.setText(f"<b>Why it matters for ECDSA:</b> {html.escape(m.why_it_matters)}")
        self.source.setText(f"Source: <a href='{html.escape(m.source_url)}'>{html.escape(m.source_title)}</a>")
        if m.page:
            self.see_button.setText(f"See it in the app: {m.page}")
