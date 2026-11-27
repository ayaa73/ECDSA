"""Learn ECDSA tab (P4): a step-by-step walkthrough of one full ECDSA run.

Teammates add steps by writing gui/learn/pages_<topic>.py with
``PAGES: list[type[LearnPage]]``. The wizard imports pages_curve, pages_keys,
pages_sign and pages_verify in that order; a missing module shows a
"coming soon" page instead of crashing.

How to write a page (copy ExamplePage at the bottom of this file):

    class KeysPage(LearnPage):
        title = "Step 2: pick d and compute Q = d*G"

        def enter(self, st: LearnState) -> None:
            trace = []
            priv, pub = generate_keypair(st.curve, trace=trace)   # core call, no math here
            st.d, st.Q = priv.d, pub.Q                           # hand results to later steps
            self.set_text("Alice picks a secret number d ...")
            self.set_formula("Q = d * G")
            self.set_values({"d": st.d, "Q": st.Q})

    PAGES = [KeysPage]

enter() runs every time the page is shown, and again for all earlier pages
when the student switches between the toy curve and secp256k1 (or jumps ahead
with the stepper), so each page should (re)compute from the state it is given.

A page can also set ``short_title`` (its name in the stepper at the top) and
``reading`` (an HTML file in gui/learn/reading/ shown under the step as
"Go deeper"; ``reading_open = True`` shows it straight away).
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from ecdsa_edu.gui.learn.model import (
    LEARN_KEYS,
    LearnState,
    PageModule,
    load_page_modules,
    step_count,
)
from ecdsa_edu.gui.learn.reading import ReadingView
from ecdsa_edu.gui.learn.stepper import StepperBar

__all__ = ["LearnState", "LearnPage", "LearnTab", "LearnWizard", "ExamplePage", "LEARN_KEYS"]

TOY_CURVE = "toy-17"
REAL_CURVE = "secp256k1"


def _get_curve(name: str) -> Any:
    """P1's registry, or None if it isn't merged yet (pages must cope with None)."""
    try:
        from ecdsa_edu.core.curves_registry import get_curve
        return get_curve(name)
    except Exception:  # noqa: BLE001
        return None


def _fmt_value(v: Any) -> str:
    """Show small ints in decimal, big ints in hex, points as (x, y)."""
    if v is None:
        return "O (point at infinity)"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, int):
        return str(v) if v.bit_length() <= 64 else hex(v)
    if isinstance(v, tuple) and len(v) == 2:
        return f"({_fmt_value(v[0])}, {_fmt_value(v[1])})"
    if isinstance(v, (bytes, bytearray)):
        return bytes(v).decode("utf-8", errors="replace")
    return str(v)


class LearnPage(QWidget):
    """Base class for one walkthrough step.

    Layout: title, plain-English explanation, one big formula, then a table
    of the values involved. Subclasses set ``title`` and override ``enter``.
    """

    title: str = "Untitled step"
    short_title: str = ""    # name in the stepper; defaults to the title
    reading: str = ""        # "Go deeper" HTML file in gui/learn/reading/, if any
    reading_title: str = "Go deeper"
    reading_open: bool = False

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title_label = QLabel(self.title)
        f = QFont()
        f.setPointSize(16)
        f.setBold(True)
        self.title_label.setFont(f)

        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setTextFormat(Qt.TextFormat.RichText)
        self.text_label.setOpenExternalLinks(True)

        self.formula_label = QLabel()
        self.formula_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.formula_label.setWordWrap(True)
        self.formula_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.formula_label.setProperty("formula", True)
        self.formula_label.setProperty("mono", True)

        self.values_table = QTableWidget(0, 2)
        self.values_table.setObjectName("learnValuesTable")
        self.values_table.setHorizontalHeaderLabels(["Name", "Value"])
        self.values_table.verticalHeader().setVisible(False)
        self.values_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.values_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.values_table.setAlternatingRowColors(True)
        self.values_table.setShowGrid(False)
        self.values_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Keep the teaching values compact instead of stretching an almost-empty
        # item view over the rest of the page. Long values use the full second
        # column and retain a horizontal scrollbar when necessary.
        self.values_table.setMinimumHeight(180)
        self.values_table.setMaximumHeight(360)
        self.values_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.values_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.values_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.values_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.values_table.setWordWrap(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title_label)
        layout.addWidget(self.text_label)
        layout.addWidget(self.formula_label)
        layout.addWidget(self.values_table)

    # --- helpers for subclasses -------------------------------------------
    def set_text(self, html: str) -> None:
        """Plain-English explanation (simple HTML allowed: <b>, <i>, <br>)."""
        self.text_label.setText(html)

    def set_formula(self, text: str) -> None:
        """The one formula this step is about, e.g. "r = x1 mod n"."""
        self.formula_label.setText(text)
        self.formula_label.setVisible(bool(text))

    def set_values(self, values: dict[str, Any]) -> None:
        """Fill the values table. Ints, points, bytes and bools are formatted for you."""
        self.values_table.setRowCount(len(values))
        for row, (name, v) in enumerate(values.items()):
            self.values_table.setItem(row, 0, QTableWidgetItem(str(name)))
            item = QTableWidgetItem(_fmt_value(v))
            item.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
            item.setToolTip(_fmt_value(v))
            self.values_table.setItem(row, 1, item)
        self.values_table.resizeRowsToContents()
        header = self.values_table.horizontalHeader().height()
        rows = sum(self.values_table.rowHeight(row) for row in range(self.values_table.rowCount()))
        self.values_table.setFixedHeight(max(180, min(360, header + rows + 12)))

    def add_reading_section(self) -> None:
        """Append the page's "Go deeper" reading (the wizard calls this once, after building the page)."""
        if not self.reading or getattr(self, "reading_view", None) is not None:
            return
        self.reading_view = ReadingView(self.reading)
        layout = self.layout()
        if self.reading_open:
            layout.addWidget(self.reading_view)
            return
        self.reading_toggle = QToolButton()
        self.reading_toggle.setObjectName("readingToggle")
        self.reading_toggle.setCheckable(True)
        self.reading_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.reading_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.reading_toggle.setText(self.reading_title)
        self.reading_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reading_toggle.toggled.connect(self._show_reading)
        self.reading_view.hide()
        layout.addWidget(self.reading_toggle, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.reading_view)

    def _show_reading(self, visible: bool) -> None:
        self.reading_toggle.setArrowType(Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow)
        self.reading_view.setVisible(visible)

    # --- override ---------------------------------------------------------
    def enter(self, st: LearnState) -> None:
        """Called when the page is shown. Read earlier values from st, call core
        functions (never do math here), write results back into st, then fill
        the widgets with set_text / set_formula / set_values."""


class ComingSoonPage(LearnPage):
    """Placeholder for a teammate's step that isn't merged yet."""

    def __init__(self, spec: PageModule, reason: str, part: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = spec.topic + (f" (part {part})" if spec.expected_steps > 1 else "")
        self.short_title = self.title
        self.title_label.setText(self.title)
        self.set_text(
            f"<i>Coming soon.</i> This step is written by <b>{spec.owner}</b> in "
            f"<code>gui/learn/{spec.module}.py</code> ({reason}).")
        self.set_formula("")
        self.values_table.hide()


class ErrorPage(LearnPage):
    """Shown in place of a page whose enter() raised, so one bug doesn't kill the tab."""

    def show_error(self, page_title: str, exc: Exception) -> None:
        self.title_label.setText(page_title)
        self.set_text(f"<span style='color:#b00020'><b>This step hit an error:</b> "
                      f"{type(exc).__name__}: {exc}</span><br>Tell the page's owner.")
        self.set_formula("")
        self.values_table.hide()


class ExamplePage(LearnPage):
    """Copy this pattern for your own steps. Not part of the walkthrough."""

    title = "Example: the curve we are using"

    def enter(self, st: LearnState) -> None:
        c = st.curve
        self.set_text(
            "Every step reads what earlier steps put in the shared state and adds its own "
            "results. This example only reads <b>st.curve</b>.")
        self.set_formula("y^2 = x^3 + a*x + b  (mod p)")
        if c is None:
            self.set_values({"curve": "not available yet (P1's registry isn't merged)"})
        else:
            self.set_values({"curve": c.name, "p": c.p, "a": c.a, "b": c.b, "G": c.G, "n": c.n})


class LearnTab(QWidget):
    """The Learn ECDSA tab: Back / Next through every teammate's steps."""

    HELP = ("A step-by-step walkthrough of one complete ECDSA run with small numbers: the curve, the keys, "
            "hashing, the nonce k, the signature (r, s), verification, the classic pitfalls, a short quiz and a "
            "glossary. Click a step in the row at the top, or use Previous and Next (or the arrow keys). "
            "\"Go deeper\" under a step opens the longer explanation and worked examples. Tick \"Show real-size "
            "numbers\" to repeat the same steps on secp256k1, the curve Bitcoin uses.")

    def __init__(self, state: Any = None) -> None:
        super().__init__()
        self.app_state = state
        self.loaded = load_page_modules()
        self.total = step_count(self.loaded)
        self.st = LearnState(_get_curve(TOY_CURVE))
        self.index = 0

        # Header: step indicator + real-size toggle
        self.step_label = QLabel()
        self.step_label.setProperty("muted", True)
        self.real_size = QCheckBox(f"Show real-size numbers ({REAL_CURVE})")
        self.real_size.setToolTip(f"Repeat the walkthrough on {REAL_CURVE} instead of the toy curve {TOY_CURVE}")
        self.real_size.toggled.connect(self._toggle_curve)
        header = QHBoxLayout()
        header.addWidget(self.step_label)
        header.addStretch(1)
        header.addWidget(self.real_size)

        # Pages
        self.stack = QStackedWidget()
        self.pages: list[LearnPage] = []
        for m in self.loaded:
            if m.pages:
                for cls in m.pages:
                    self.pages.append(self._make_page(cls, m.spec))
            else:
                for part in range(1, m.spec.expected_steps + 1):
                    self.pages.append(ComingSoonPage(m.spec, m.error, part))
        # Each step scrolls independently, rather than squeezing tables to fit
        # alongside plots, explanations and traces in the available height.
        self._page_scrolls: dict[LearnPage, QScrollArea] = {}
        for p in self.pages:
            p.add_reading_section()
            scroll = QScrollArea()
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidgetResizable(True)
            scroll.setWidget(p)
            trace_view = getattr(p, "trace_view", None)
            if callable(getattr(trace_view, "use_page_scrolling", None)):
                trace_view.use_page_scrolling(scroll)
            self._page_scrolls[p] = scroll
            self.stack.addWidget(scroll)
        self.error_page = ErrorPage()
        self.stack.addWidget(self.error_page)

        # Stepper: the reading order, every step clickable
        self.stepper = StepperBar([p.short_title or p.title for p in self.pages])
        self.stepper.stepClicked.connect(self.jump_to)

        # Footer: Previous / Next
        self.back_btn = QPushButton("◀  Previous")
        self.next_btn = QPushButton("Next  ▶")
        self.back_btn.clicked.connect(self.back)
        self.next_btn.clicked.connect(self.next)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, activated=self.back)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, activated=self.next)
        footer = QHBoxLayout()
        footer.addWidget(self.back_btn)
        footer.addStretch(1)
        footer.addWidget(self.next_btn)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self.stepper)
        layout.addWidget(line)
        layout.addWidget(self.stack, stretch=1)
        layout.addLayout(footer)

        self.go(0)

    @staticmethod
    def _make_page(cls: type, spec: PageModule) -> LearnPage:
        try:
            page = cls()
            if not isinstance(page, LearnPage):
                raise TypeError(f"{cls.__name__} is not a LearnPage")
            return page
        except Exception as exc:  # noqa: BLE001
            return ComingSoonPage(spec, f"{cls.__name__} failed to build: {exc}", 1)

    # --- navigation ---------------------------------------------------------
    def go(self, i: int) -> None:
        if not self.pages:
            return
        self.index = max(0, min(i, len(self.pages) - 1))
        page = self.pages[self.index]
        try:
            page.enter(self.st)
            self.stack.setCurrentWidget(self._page_scrolls[page])
        except Exception as exc:  # noqa: BLE001 - show it, don't crash the app
            self.error_page.show_error(page.title, exc)
            self.stack.setCurrentWidget(self.error_page)
        self.step_label.setText(f"Step {self.index + 1} of {self.total}  ·  {page.title}")
        self.stepper.set_current(self.index)
        self.back_btn.setEnabled(self.index > 0)
        self.next_btn.setEnabled(self.index < len(self.pages) - 1)

    def next(self) -> None:
        if self.index < len(self.pages) - 1:
            self.go(self.index + 1)

    def back(self) -> None:
        if self.index > 0:
            self.go(self.index - 1)

    def jump_to(self, i: int) -> None:
        """Go straight to step ``i``. Steps that were skipped are run first,
        so the values a later step needs (key, hash, k, ...) exist."""
        for skipped in range(self.index + 1, min(i, len(self.pages))):
            try:
                self.pages[skipped].enter(self.st)
            except Exception:  # noqa: BLE001 - the error shows when that page is visited
                pass
        self.go(i)

    def _toggle_curve(self, real: bool) -> None:
        """Restart on the other curve and replay the steps up to the current one,
        so every value on screen comes from the new curve."""
        self.st.reset(_get_curve(REAL_CURVE if real else TOY_CURVE))
        target = self.index
        for i in range(target):
            try:
                self.pages[i].enter(self.st)
            except Exception:  # noqa: BLE001 - the error shows when that page is visited
                pass
        self.go(target)

    # --- tab contract -------------------------------------------------------
    def set_curve(self, curve: Any) -> None:
        """Part of the tab contract. The walkthrough uses its own teaching curves
        (toy-17 or secp256k1 via the checkbox), so the app's curve is ignored."""


# The main window (P2) loads this tab by the name LearnWizard.
LearnWizard = LearnTab
