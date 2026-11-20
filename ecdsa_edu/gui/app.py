"""Application entry point and visual theme (owner: P2).

Run with:

    python -m ecdsa_edu.gui.app

Theme hooks every page can use (they follow the light/dark toggle automatically):

    button.setProperty("primary", True)    filled main-action button
    label.setProperty("note", True)        small grey helper text
    label.setProperty("kind", "ok")        coloured message: "ok" | "error" | "warning" | "info"
    widget.setProperty("mono", True)       monospace font, for numbers and hex
    widget.setProperty("invalid", True)    red border (BigIntField / HexField set this)

After changing a property on a widget that is already visible, re-polish it:
``w.style().unpolish(w); w.style().polish(w)``.
"""
from __future__ import annotations

import sys
import traceback
from collections.abc import Sequence

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

from ecdsa_edu import __version__

__all__ = ["main", "apply_theme", "current_theme", "theme_colors", "THEMES", "MONO_FONT"]

# Font stack for numbers: the first family that exists on the machine is used.
MONO_FONT = '"JetBrains Mono", "Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono", "Courier New", monospace'

# One set of named colours per theme; the stylesheet below is the same for both.
THEMES: dict[str, dict[str, str]] = {
    "light": {
        "window": "#f4f5fa", "panel": "#ffffff", "text": "#1c2140", "muted": "#6b7190",
        "border": "#d5d9e6", "heading": "#1e2761",
        "accent": "#1e2761", "accent_hover": "#2c3780", "accent_text": "#ffffff",
        "toolbar": "#ffffff", "toolbar_text": "#1c2140",
        "sidebar": "#1e2761", "sidebar_text": "#cfd6ef", "sidebar_hover": "#2a357a",
        "sidebar_selected": "#3a4794", "sidebar_selected_text": "#ffffff",
        "input": "#ffffff", "input_readonly": "#f3f4f9", "hover": "#eef1fb", "pressed": "#dfe4f6",
        "disabled": "#eceef5", "disabled_text": "#a3a8bb",
        "ok": "#1f7a4d", "error": "#c0392b", "info": "#4a5170", "warning": "#8a5a00", "invalid": "#fdf3f2",
        "status": "#e9ebf4",
    },
    "dark": {
        "window": "#14172b", "panel": "#1d2140", "text": "#e6e9f5", "muted": "#9aa3c7",
        "border": "#343a63", "heading": "#aab6ff",
        "accent": "#8090f2", "accent_hover": "#99a6f6", "accent_text": "#10132a",
        "toolbar": "#1d2140", "toolbar_text": "#e6e9f5",
        "sidebar": "#0e1022", "sidebar_text": "#aab2d8", "sidebar_hover": "#1b1f3d",
        "sidebar_selected": "#2a3166", "sidebar_selected_text": "#ffffff",
        "input": "#171a33", "input_readonly": "#1a1e3a", "hover": "#272c55", "pressed": "#30366a",
        "disabled": "#1a1d36", "disabled_text": "#5d648a",
        "ok": "#5fd39a", "error": "#ff8a7a", "info": "#aab2d8", "warning": "#f0b84d", "invalid": "#3a1f25",
        "status": "#0e1022",
    },
}

_STYLE = """
QWidget {{ font-size: 10pt; color: {text}; }}
QMainWindow, QDialog, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {window}; }}
QToolTip {{ background: {panel}; color: {text}; border: 1px solid {border}; }}

/* toolbar */
QToolBar {{ background: {toolbar}; border: none; border-bottom: 1px solid {border}; padding: 8px 12px; spacing: 10px; }}
QToolBar QLabel {{ color: {toolbar_text}; background: transparent; }}
QToolBar QLabel#appTitle {{ color: {heading}; font-size: 14pt; font-weight: 600; padding-right: 12px; }}
QToolBar QLabel#curveInfo {{ color: {muted}; }}

/* sidebar */
QListWidget#sidebar {{ background: {sidebar}; border: none; outline: none; padding: 10px 8px; }}
QListWidget#sidebar::item {{ color: {sidebar_text}; padding: 10px 12px; margin: 2px 0; border-radius: 6px; }}
QListWidget#sidebar::item:hover {{ background: {sidebar_hover}; }}
QListWidget#sidebar::item:selected {{ background: {sidebar_selected}; color: {sidebar_selected_text}; font-weight: 600; }}

/* panels and text */
QGroupBox {{ background: {panel}; border: 1px solid {border}; border-radius: 6px;
            margin-top: 14px; padding: 12px 10px 10px 10px; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 5px; color: {heading}; }}
QGroupBox QLabel, QGroupBox QCheckBox {{ font-weight: normal; background: transparent; }}
QLabel[note="true"] {{ color: {muted}; font-size: 9pt; }}
QLabel[kind="ok"] {{ color: {ok}; }}
QLabel[kind="error"] {{ color: {error}; }}
QLabel[kind="info"] {{ color: {info}; }}
QLabel[kind="warning"] {{ color: {warning}; font-weight: 600; }}
QLabel#comingSoon {{ color: {muted}; font-size: 11pt; }}
*[mono="true"], BigIntField, HexField {{ font-family: {mono}; }}

/* buttons */
QPushButton, QToolButton {{ padding: 6px 14px; border: 1px solid {border}; border-radius: 4px;
                           background: {panel}; color: {text}; font-weight: normal; }}
QPushButton:hover, QToolButton:hover {{ background: {hover}; }}
QPushButton:pressed, QToolButton:pressed, QToolButton:checked {{ background: {pressed}; }}
QPushButton:disabled {{ color: {disabled_text}; background: {disabled}; }}
QPushButton[primary="true"] {{ background: {accent}; color: {accent_text}; border: 1px solid {accent}; font-weight: 600; }}
QPushButton[primary="true"]:hover {{ background: {accent_hover}; }}
QPushButton[primary="true"]:disabled {{ background: {disabled}; border-color: {border}; color: {disabled_text}; }}

/* inputs */
QLineEdit, QPlainTextEdit, QTextEdit {{ border: 1px solid {border}; border-radius: 4px; padding: 4px 6px;
                                       background: {input}; color: {text}; font-weight: normal;
                                       selection-background-color: {accent}; selection-color: {accent_text}; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {accent}; }}
QLineEdit:read-only, QPlainTextEdit[readOnly="true"] {{ background: {input_readonly}; }}
QLineEdit[invalid="true"], QPlainTextEdit[invalid="true"] {{ border: 1px solid {error}; background: {invalid}; }}
QComboBox {{ padding: 4px 8px; font-weight: normal; }}

/* menus and status bar */
QMenuBar {{ background: {toolbar}; color: {toolbar_text}; }}
QMenuBar::item:selected, QMenu::item:selected {{ background: {hover}; color: {text}; }}
QMenu {{ background: {panel}; border: 1px solid {border}; }}
QStatusBar {{ background: {status}; color: {muted}; }}
QStatusBar QLabel {{ color: {muted}; padding: 0 8px; }}
QStatusBar QLabel#statusCurve {{ font-family: {mono}; }}
QProgressBar {{ border: 1px solid {border}; border-radius: 5px; background: {input_readonly}; }}
QProgressBar::chunk {{ background: {accent}; border-radius: 4px; }}
"""


def theme_colors(theme: str) -> dict[str, str]:
    """The named colours of ``theme`` ("light" or "dark")."""
    return THEMES[theme]


def current_theme(app: QApplication | None = None) -> str:
    """Name of the theme that is active right now."""
    app = app or QApplication.instance()
    name = app.property("theme") if app is not None else None
    return name if name in THEMES else "light"


def apply_theme(app: QApplication, theme: str = "light") -> None:
    """Switch the whole application to the light or dark theme.

    Fusion style + our own palette, so the app looks the same on every OS.
    """
    if theme not in THEMES:
        raise ValueError(f"unknown theme: {theme!r}")
    c = THEMES[theme]
    app.setStyle("Fusion")
    palette = QPalette()
    for role, key in (
        (QPalette.ColorRole.Window, "window"),
        (QPalette.ColorRole.WindowText, "text"),
        (QPalette.ColorRole.Base, "input"),
        (QPalette.ColorRole.AlternateBase, "input_readonly"),
        (QPalette.ColorRole.Text, "text"),
        (QPalette.ColorRole.Button, "panel"),
        (QPalette.ColorRole.ButtonText, "text"),
        (QPalette.ColorRole.ToolTipBase, "panel"),
        (QPalette.ColorRole.ToolTipText, "text"),
        (QPalette.ColorRole.Highlight, "accent"),
        (QPalette.ColorRole.HighlightedText, "accent_text"),
        (QPalette.ColorRole.PlaceholderText, "disabled_text"),
        (QPalette.ColorRole.Link, "heading"),
    ):
        palette.setColor(role, QColor(c[key]))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(c["disabled_text"]))
    app.setPalette(palette)
    app.setStyleSheet(_STYLE.format(mono=MONO_FONT, **c))
    app.setProperty("theme", theme)


def _install_excepthook() -> None:
    """Show unexpected errors in a dialog instead of silently printing to a hidden console."""

    def hook(exc_type, exc, tb) -> None:
        traceback.print_exception(exc_type, exc, tb)
        if QApplication.instance() is not None and not issubclass(exc_type, KeyboardInterrupt):
            QMessageBox.critical(None, "Unexpected error", f"{exc_type.__name__}: {exc}")

    sys.excepthook = hook


def main(argv: Sequence[str] | None = None) -> int:
    """Start the application and return its exit code."""
    # Imported here (not at the top) because main_window itself imports this module.
    from ecdsa_edu.gui.app_state import AppState
    from ecdsa_edu.gui.main_window import MainWindow

    app = QApplication(list(argv) if argv is not None else sys.argv)
    app.setApplicationName("ECDSA Lab")
    app.setApplicationVersion(__version__)
    apply_theme(app, "light")
    _install_excepthook()
    state = AppState()
    window = MainWindow(state)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
