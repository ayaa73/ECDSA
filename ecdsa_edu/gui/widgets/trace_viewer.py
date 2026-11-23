"""Display core calculation traces as readable, interactive steps (owner: P3).

Every core module records its mathematics as ``TraceStep`` objects. Pages hand
that list to ``TraceViewer`` instead of rebuilding formulas in the GUI. The
widget supports a full overview and a one-step-at-a-time teaching mode.

Run ``python -m ecdsa_edu.gui.widgets.trace_viewer`` for a fake-trace demo.
"""
from __future__ import annotations

import re
import sys

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from ecdsa_edu.core.trace import Trace, TraceStep

__all__ = ["TraceViewer"]


_DECIMAL_WITH_OPTIONAL_HEX = re.compile(r"^(-?\d+)(?:\s+\(0x[0-9a-fA-F]+\))?$")

_TEACHING_NAMES = {
    "digest": "Hash output",
    "digest_bits": "Hash output size (bits)",
    "order_bits": "Curve order size (bits)",
    "removed_bits": "Bits removed",
    "hash": "Hash function",
    "rx": "R x-coordinate",
    "ry": "R y-coordinate",
    "k_inverse": "Inverse of k",
}


def _integer_value(text: str) -> int | None:
    """Return an integer only when a trace value clearly represents one."""
    stripped = text.strip()
    match = _DECIMAL_WITH_OPTIONAL_HEX.fullmatch(stripped)
    if match:
        return int(match.group(1))
    if re.fullmatch(r"-?0x[0-9a-fA-F]+", stripped):
        return int(stripped, 16)
    return None


def _format_value(text: str, use_hex: bool) -> str:
    """Switch plain integer values between bases without changing other text."""
    value = _integer_value(text)
    if value is None:
        return text
    return hex(value) if use_hex else str(value)


def _soft_wrap(text: str, width: int = 16) -> str:
    """Add invisible break points to a long value that has no spaces."""
    if len(text) <= width * 2 or any(character.isspace() for character in text):
        return text
    return "\u200b".join(text[index:index + width] for index in range(0, len(text), width))


def _safe_values(step: TraceStep) -> list[tuple[str, str]]:
    """Prepare values for display while keeping the private key out of traces."""
    rows: list[tuple[str, str]] = []
    for name, value in step.values.items():
        raw_name = str(name)
        # Several pages share this widget. Redacting d here protects the key
        # even if an older core function accidentally leaves it in a trace.
        shown = "(hidden)" if raw_name.strip().lower() == "d" else str(value)
        key = raw_name.strip().lower()
        friendly_name = _TEACHING_NAMES.get(key, raw_name.replace("_", " "))
        rows.append((friendly_name, shown))
    return rows


def _teaching_text(text: str) -> str:
    """Replace internal cryptography wording with a clearer screen label."""
    return re.sub(r"\bdigest\b", "hash output", text, flags=re.IGNORECASE)


class _StepPanel(QFrame):
    """One expandable trace step with its formula and value table."""

    def __init__(self, number: int, step: TraceStep, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.number = number
        self.step = step
        self.display_title = _teaching_text(step.title)
        self.display_formula = _teaching_text(step.formula)
        self._rows = _safe_values(step)
        self._use_hex = False
        self.setObjectName("traceStepCard")
        self.setFrameShape(QFrame.Shape.NoFrame)

        self.number_badge = QLabel(str(number))
        self.number_badge.setObjectName("stepNumberBadge")
        self.number_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number_badge.setFixedSize(30, 30)

        self.title_label = QLabel(self.display_title)
        self.title_label.setObjectName("stepTitle")
        self.title_label.setWordWrap(True)

        self.toggle = QToolButton()
        self.toggle.setText("Hide details")
        self.toggle.setObjectName("stepDetailsButton")
        self.toggle.setCheckable(True)
        self.toggle.setChecked(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.toggle.setArrowType(Qt.ArrowType.NoArrow)
        self.toggle.setAccessibleName(f"Step {number}: {self.display_title}")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)
        header.addWidget(self.number_badge)
        header.addWidget(self.title_label, 1)
        header.addWidget(self.toggle)

        self.details = QWidget()
        self.details.setObjectName("stepDetails")
        details_layout = QVBoxLayout(self.details)
        details_layout.setContentsMargins(40, 6, 4, 4)
        details_layout.setSpacing(10)

        self.formula_label = QLabel(self.display_formula or "No formula was recorded for this step.")
        self.formula_label.setObjectName("traceFormula")
        self.formula_label.setWordWrap(True)
        self.formula_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.formula_label.setToolTip(
            f"Formula used in this step: {self.display_formula}"
            if self.display_formula else "No formula was recorded."
        )
        formula_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        formula_font.setPointSize(max(10, formula_font.pointSize()))
        self.formula_label.setFont(formula_font)
        details_layout.addWidget(self.formula_label)

        self.values_table = QTableWidget(len(self._rows), 2)
        self.values_table.setObjectName("traceValues")
        self.values_table.setHorizontalHeaderLabels(["Variable", "Value"])
        self.values_table.verticalHeader().setVisible(False)
        self.values_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.values_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.values_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.values_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.values_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.values_table.setWordWrap(True)
        self.values_table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.values_table.setAlternatingRowColors(True)
        self.values_table.setShowGrid(False)
        self.values_table.setVisible(bool(self._rows))
        details_layout.addWidget(self.values_table)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(7)
        layout.addLayout(header)
        layout.addWidget(self.details)

        self.toggle.toggled.connect(self.set_expanded)
        self._refresh_values()

    def set_expanded(self, expanded: bool) -> None:
        """Show or hide the details under the step title."""
        self.details.setVisible(expanded)
        self.toggle.setText("Hide details" if expanded else "Show details")
        self.toggle.setToolTip("Hide this calculation" if expanded else "Show this calculation")
        if self.toggle.isChecked() != expanded:
            self.toggle.setChecked(expanded)

    def set_use_hex(self, use_hex: bool) -> None:
        self._use_hex = use_hex
        self._refresh_values()

    def display_rows(self) -> list[tuple[str, str]]:
        return [(name, _format_value(value, self._use_hex)) for name, value in self._rows]

    def plain_text(self) -> str:
        """Return this step in the same order shown on screen."""
        lines = [
            f"Step {self.number}: {self.display_title}",
            f"Formula: {self.display_formula or '(none)'}",
        ]
        lines.extend(f"{name}: {value}" for name, value in self.display_rows())
        return "\n".join(lines)

    def _refresh_values(self) -> None:
        for row, (name, value) in enumerate(self.display_rows()):
            name_item = QTableWidgetItem(name)
            value_item = QTableWidgetItem(_soft_wrap(value))
            name_item.setToolTip(name)
            value_item.setToolTip(value)
            self.values_table.setItem(row, 0, name_item)
            self.values_table.setItem(row, 1, value_item)
        self._fit_table_height()

    def _fit_table_height(self) -> None:
        """Let wrapped rows grow, then keep the table just tall enough for them."""
        # Qt can delete a panel while a zero-delay resize is still waiting in
        # the event queue. In that case there is simply nothing left to resize.
        if not isValid(self) or not isValid(self.values_table):
            return
        self.values_table.resizeRowsToContents()
        if self._rows:
            header_height = self.values_table.horizontalHeader().height()
            rows_height = sum(self.values_table.rowHeight(row) for row in range(len(self._rows)))
            self.values_table.setFixedHeight(header_height + rows_height + 4)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        # The stretched value column receives its final width after this event.
        # Waiting one event-loop turn makes resizeRowsToContents use that width.
        QTimer.singleShot(0, self._fit_table_height)


class TraceViewer(QWidget):
    """Expandable and step-by-step display for a list of ``TraceStep`` objects."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("traceViewer")
        self._trace: Trace = []
        self._panels: list[_StepPanel] = []
        self._step_index: int | None = None

        self.step_through_button = QPushButton("Step through")
        self.step_through_button.setObjectName("tracePrimaryButton")
        self.previous_button = QPushButton("Previous")
        self.next_button = QPushButton("Next")
        self.show_all_button = QPushButton("Show all")
        self.copy_button = QPushButton("Copy as text")
        self.hex_toggle = QCheckBox("Show numbers in hex")
        self.step_label = QLabel("No steps")
        self.step_label.setObjectName("traceStepCount")

        self.step_through_button.setToolTip("Show one calculation step at a time")
        self.previous_button.setToolTip("Go to the previous calculation step")
        self.next_button.setToolTip("Go to the next calculation step")
        self.show_all_button.setToolTip("Show every calculation step")
        self.copy_button.setToolTip("Copy the complete trace as plain text")
        self.hex_toggle.setToolTip("Display integer values in hexadecimal")

        controls = QHBoxLayout()
        controls.addWidget(self.step_through_button)
        controls.addWidget(self.previous_button)
        controls.addWidget(self.next_button)
        controls.addWidget(self.show_all_button)
        controls.addWidget(self.copy_button)
        controls.addStretch(1)
        controls.addWidget(self.hex_toggle)
        controls.addWidget(self.step_label)

        self.empty_label = QLabel("No calculation steps yet.")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setProperty("note", True)

        self.content = QWidget()
        self.steps_layout = QVBoxLayout(self.content)
        self.steps_layout.setContentsMargins(0, 0, 0, 0)
        self.steps_layout.setSpacing(6)
        self.steps_layout.addStretch(1)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("traceScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidget(self.content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(controls)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.scroll, 1)

        self.step_through_button.clicked.connect(self.start_step_through)
        self.previous_button.clicked.connect(self.previous_step)
        self.next_button.clicked.connect(self.next_step)
        self.show_all_button.clicked.connect(self.show_all)
        self.copy_button.clicked.connect(self.copy_as_text)
        self.hex_toggle.toggled.connect(self._set_use_hex)
        self._apply_visual_style()
        self._update_controls()

    def _apply_visual_style(self) -> None:
        """Use the same calm blue cards as the rest of the teaching app."""
        # The widget's own palette changes while its stylesheet is applied.
        # The application palette is stable and represents the chosen theme.
        dark = QApplication.palette().window().color().lightness() < 128
        if getattr(self, "_visual_dark", None) == dark:
            return
        self._visual_dark = dark
        if dark:
            page, card, inner = "#14172b", "#1c2b43", "#17243a"
            text, muted, border = "#edf3fc", "#aabbd3", "#6689bc"
            accent, accent_soft, row = "#75a7e8", "#243d60", "#20334f"
        else:
            page, card, inner = "#f4f7fc", "#ffffff", "#f7faff"
            text, muted, border = "#102b56", "#4b6790", "#c3d5ee"
            accent, accent_soft, row = "#245c9f", "#e4efff", "#eef5ff"

        self.setStyleSheet(
            f"""
            QWidget#traceViewer {{ background: transparent; color: {text}; font-family: Georgia; }}
            QScrollArea#traceScroll, QScrollArea#traceScroll > QWidget > QWidget {{
                background: transparent; border: 0;
            }}
            QFrame#traceStepCard {{
                background: {card}; border: 1px solid {border}; border-radius: 13px;
            }}
            QLabel#stepNumberBadge {{
                background: {accent}; color: white; border: 0; border-radius: 15px;
                font-family: Georgia; font-size: 11pt; font-weight: 700;
            }}
            QLabel#stepTitle {{
                color: {text}; font-family: Georgia; font-size: 11pt; font-weight: 600;
            }}
            QToolButton#stepDetailsButton {{
                color: {accent}; background: transparent; border: 0; padding: 6px 8px;
                font-family: Georgia; font-weight: 600;
            }}
            QToolButton#stepDetailsButton:hover {{ background: {accent_soft}; border-radius: 8px; }}
            QLabel#traceFormula {{
                color: {text}; background: {inner}; border: 1px solid {border};
                border-radius: 9px; padding: 11px 13px;
            }}
            QTableWidget#traceValues {{
                color: {text}; background: {card}; alternate-background-color: {row};
                border: 1px solid {border}; border-radius: 9px; padding: 3px;
                selection-background-color: transparent;
            }}
            QTableWidget#traceValues::item {{ border: 0; padding: 5px 7px; }}
            QHeaderView::section {{
                color: {muted}; background: {inner}; border: 0;
                border-bottom: 1px solid {border}; padding: 7px;
                font-family: Georgia; font-weight: 600;
            }}
            QPushButton {{
                color: {text}; background: {card}; border: 1px solid {border};
                border-radius: 9px; padding: 7px 13px; font-family: Georgia;
            }}
            QPushButton:hover {{ color: {accent}; border-color: {accent}; background: {accent_soft}; }}
            QPushButton#tracePrimaryButton {{ background: {accent}; color: white; border-color: {accent}; }}
            QPushButton:disabled {{ color: {muted}; background: {inner}; }}
            QCheckBox, QLabel#traceStepCount {{ color: {muted}; font-family: Georgia; }}
            QScrollBar:vertical {{ background: transparent; width: 10px; margin: 3px; }}
            QScrollBar::handle:vertical {{ background: {border}; min-height: 34px; border-radius: 4px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            """
        )

    def changeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Refresh the trace colours when the whole app changes theme."""
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange):
            self._apply_visual_style()

    def set_trace(self, trace: Trace) -> None:
        """Replace the displayed calculation with ``trace`` and show all steps."""
        self._trace = list(trace)
        self._step_index = None
        self._clear_panels()
        for number, step in enumerate(self._trace, start=1):
            panel = _StepPanel(number, step, self.content)
            panel.set_use_hex(self.hex_toggle.isChecked())
            self._panels.append(panel)
            self.steps_layout.insertWidget(self.steps_layout.count() - 1, panel)
        self.empty_label.setVisible(not self._panels)
        self.scroll.setVisible(bool(self._panels))
        self._show_all_panels()
        self._update_controls()

    def start_step_through(self) -> None:
        """Enter teaching mode at the first step."""
        if not self._panels:
            return
        self._step_index = 0
        self._show_current_step()

    def previous_step(self) -> None:
        if self._step_index is None or self._step_index <= 0:
            return
        self._step_index -= 1
        self._show_current_step()

    def next_step(self) -> None:
        if self._step_index is None or self._step_index >= len(self._panels) - 1:
            return
        self._step_index += 1
        self._show_current_step()

    def show_all(self) -> None:
        """Leave teaching mode and expand the complete trace."""
        self._step_index = None
        self._show_all_panels()
        self._update_controls()

    def as_text(self) -> str:
        """Return the complete trace as readable plain text."""
        return "\n\n".join(panel.plain_text() for panel in self._panels)

    def copy_as_text(self) -> None:
        """Copy the complete trace and briefly confirm the action."""
        text = self.as_text()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.copy_button.setText("Copied ✓")
        QTimer.singleShot(1200, self, lambda: self.copy_button.setText("Copy as text"))

    def _clear_panels(self) -> None:
        for panel in self._panels:
            self.steps_layout.removeWidget(panel)
            panel.deleteLater()
        self._panels.clear()

    def _show_current_step(self) -> None:
        if self._step_index is None:
            return
        for index, panel in enumerate(self._panels):
            current = index == self._step_index
            panel.setVisible(current)
            panel.set_expanded(current)
        self.scroll.ensureWidgetVisible(self._panels[self._step_index])
        self._update_controls()

    def _show_all_panels(self) -> None:
        for panel in self._panels:
            panel.setVisible(True)
            panel.set_expanded(True)

    def _set_use_hex(self, use_hex: bool) -> None:
        for panel in self._panels:
            panel.set_use_hex(use_hex)

    def _update_controls(self) -> None:
        has_steps = bool(self._panels)
        in_step_mode = self._step_index is not None
        self.step_through_button.setEnabled(has_steps)
        self.show_all_button.setEnabled(has_steps and in_step_mode)
        self.copy_button.setEnabled(has_steps)
        self.previous_button.setEnabled(in_step_mode and self._step_index > 0)
        self.next_button.setEnabled(
            in_step_mode and self._step_index is not None and self._step_index < len(self._panels) - 1
        )
        if not has_steps:
            self.step_label.setText("No steps")
        elif in_step_mode:
            self.step_label.setText(f"Step {self._step_index + 1} of {len(self._panels)}")
        else:
            self.step_label.setText(f"{len(self._panels)} steps")

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        if self._step_index is None:
            # Expanded tables finish measuring themselves after the widget is
            # shown. Resetting afterward keeps a new trace at Step 1.
            QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(0))


def _demo_trace() -> Trace:
    """Small made-up trace used only by the standalone widget demo."""
    return [
        TraceStep(
            "Hash the message",
            "e = leftmost bit_length(n) bits of SHA-256(message)",
            {"hash": "sha256", "digest_bits": "256", "order_bits": "5", "e": "26"},
        ),
        TraceStep(
            "Compute R = kG",
            "R = 10 × (5, 1) = (7, 11)",
            {"k": "10", "R": "(7, 11)", "r": "7"},
        ),
        TraceStep(
            "Compute s",
            "s = k^-1 × (e + r × d) mod n",
            {
                "d": "7",
                "s": "17",
                "large_example": "115792089237316195423570985008687907852837564279074904382605163141518161494337",
            },
        ),
    ]


def main() -> int:
    app = QApplication(sys.argv)
    viewer = TraceViewer()
    viewer.setWindowTitle("ECDSA Lab - TraceViewer demo")
    viewer.resize(850, 620)
    viewer.set_trace(_demo_trace())
    viewer.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
