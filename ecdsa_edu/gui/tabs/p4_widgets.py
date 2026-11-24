"""Small Qt helpers shared by P4's pages (Verify, Attack Demo, Start here).

* make_trace_view(): P3's TraceViewer when it exists, otherwise a simple list
  with the same set_trace() method, so the pages work before it is merged.
* ResultBanner: the big VALID / INVALID / MATCH box (color + mark + words).
* go_to(), current_mode(), on_mode_changed(): use P2's AppState additions when
  they exist, and fall back to what the current main window already offers.
"""
from __future__ import annotations

import html
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QTextBrowser, QWidget

__all__ = ["make_trace_view", "SimpleTraceView", "ResultBanner", "go_to", "current_mode", "on_mode_changed",
           "heading", "explanation"]


class SimpleTraceView(QTextBrowser):
    """Fallback trace display: numbered steps with their formula and values."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setOpenLinks(False)
        self.setMinimumHeight(160)
        self.setPlaceholderText("The steps of the calculation will appear here.")

    def set_trace(self, trace: list) -> None:
        parts = []
        for i, step in enumerate(trace or [], 1):
            rows = "".join(
                f"<tr><td style='padding-right:12px'><b>{html.escape(str(k))}</b></td>"
                f"<td style='font-family:monospace'>{html.escape(str(v))}</td></tr>"
                for k, v in step.values.items())
            parts.append(
                f"<p><b>{i}. {html.escape(step.title)}</b><br>"
                f"<span style='font-family:monospace'>{html.escape(step.formula)}</span></p>"
                + (f"<table>{rows}</table>" if rows else ""))
        self.setHtml("".join(parts))

    def clear_trace(self) -> None:
        self.clear()


def make_trace_view(parent: QWidget | None = None) -> QWidget:
    """P3's TraceViewer if it is merged and builds, else SimpleTraceView."""
    try:
        from ecdsa_edu.gui.widgets.trace_viewer import TraceViewer
        view = TraceViewer(parent) if parent is not None else TraceViewer()
        if callable(getattr(view, "set_trace", None)):
            return view
    except Exception:  # missing module, stub, or a bug in it: keep our page usable
        pass
    return SimpleTraceView(parent)


class ResultBanner(QLabel):
    """Big result box. Never color alone: always a mark and a word too."""

    STYLES = {
        "good": ("#1e7e34", "#e8f5ec", "✔"),
        "bad": ("#b00020", "#fdecea", "✘"),
        "info": ("#1f3a5f", "#eef4fb", "ℹ"),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(70)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.show_message("info", "", "")

    def show_message(self, kind: str, headline: str, detail: str) -> None:
        _, _, mark = self.STYLES[kind]
        self.kind = kind
        self.headline = headline
        if not headline and not detail:
            self.setText("")
            self.setProperty("result", "")
            self.style().unpolish(self); self.style().polish(self)
            return
        self.setProperty("result", kind)
        self.style().unpolish(self); self.style().polish(self)
        big = f"<span style='font-size:22pt; font-weight:bold'>{mark} {html.escape(headline)}</span>"
        self.setText(big + (f"<br><span style='font-size:11pt'>{html.escape(detail)}</span>" if detail else ""))


def heading(text: str) -> QLabel:
    label = QLabel(f"<span style='font-size:16pt; font-weight:bold'>{html.escape(text)}</span>")
    return label


def explanation(text_html: str) -> QLabel:
    label = QLabel(text_html)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setOpenExternalLinks(True)
    return label


# ---------------------------------------------------------------- AppState glue
def go_to(widget: QWidget, state: Any, page_title: str) -> bool:
    """Send the user to another page. Uses state.go_to() (P2, new) when it
    exists, otherwise the main window's show_page(). Returns False if neither
    is available (e.g. the page is running on its own in a test)."""
    if state is not None and callable(getattr(state, "go_to", None)):
        state.go_to(page_title)
        return True
    window = widget.window()
    if callable(getattr(window, "show_page", None)):
        try:
            window.show_page(page_title)
            return True
        except (ValueError, KeyError):
            return False
    return False


def current_mode(state: Any) -> str:
    """"beginner" (default) or "expert". Before P2 adds modes, always beginner."""
    mode = getattr(state, "mode", "beginner") if state is not None else "beginner"
    return mode if mode in ("beginner", "expert") else "beginner"


def on_mode_changed(state: Any, slot: Callable[[str], None]) -> None:
    signal = getattr(state, "modeChanged", None) if state is not None else None
    if signal is not None and hasattr(signal, "connect"):
        signal.connect(slot)
