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

from pathlib import Path
from PySide6.QtGui import QColor, QPalette, QFontDatabase, QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from ecdsa_edu import __version__
from ecdsa_edu.gui.p3_style import P3_STYLE

__all__ = ["main", "apply_theme", "current_theme", "theme_colors", "THEMES", "MONO_FONT"]

# Font stack for numbers: the first family that exists on the machine is used.
MONO_FONT = '"JetBrains Mono", "Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono", "Courier New", monospace'

# One set of named colours per theme; the stylesheet below is the same for both.
THEMES: dict[str, dict[str, str]] = {
    "light": {
        "window": "#f5e4ef", "panel": "#fffaf0", "text": "#211a20", "muted": "#756873",
        "border": "#ead5e1", "heading": "#211a20",
        "accent": "#e9b0d1", "accent_hover": "#dc96c1", "accent_text": "#25151f",
        "toolbar": "#fffaf0", "toolbar_text": "#211a20",
        "sidebar": "#111010", "sidebar_text": "#f4eaf0", "sidebar_hover": "#30272d",
        "sidebar_selected": "#d998bd", "sidebar_selected_text": "#21131b",
        "input": "#fffdf8", "input_readonly": "#f7edf2", "hover": "#f8e6f0", "pressed": "#efcfe0",
        "disabled": "#f0e9ed", "disabled_text": "#a49aa1",
        "ok": "#347754", "error": "#b33b47", "info": "#62545f", "warning": "#855519", "invalid": "#fff0f0",
        "status": "#f1e1ea",
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

# Shared pastel tokens supplement the original public theme keys.
THEMES["light"].update(dict(window="#BFEBDA", panel="#FFFFFF", text="#141414", muted="#625D59",
    border="#E5DDD8", heading="#141414", accent="#111111", accent_hover="#333333", accent_text="#FFFFFF",
    toolbar="#FBF7F4", toolbar_text="#141414", sidebar="#F3ECE7", sidebar_text="#141414",
    sidebar_hover="#E9E0DB", sidebar_selected="#111111", sidebar_selected_text="#FFFFFF",
    input="#FFFFFF", input_readonly="#F3ECE7", hover="#EFE7E2", pressed="#E5DAD4",
    disabled="#EAE4E0", disabled_text="#77716D", ok="#2E9E6A", error="#D9534F",
    info="#625D59", warning="#B7791F", invalid="#FBE8E8", status="#FBF7F4",
    surface="#FBF7F4", rail="#F3ECE7", pink="#F4C6C6", peach="#F9DDBB",
    lavender="#CFC8F7", mint="#BFE8D6", pastel_text="#141414"))
THEMES["dark"].update(dict(window="#111113", panel="#29292E", text="#F6F3F1", muted="#C5BFBC",
    border="#45454A", heading="#F6F3F1", accent="#F6F3F1", accent_hover="#D7D2CF", accent_text="#17171A",
    toolbar="#17171A", toolbar_text="#F6F3F1", sidebar="#202024", sidebar_text="#F6F3F1",
    sidebar_hover="#37373D", sidebar_selected="#FFFFFF", sidebar_selected_text="#17171A",
    input="#303036", input_readonly="#242429", hover="#39393F", pressed="#48484F",
    disabled="#303036", disabled_text="#A5A0A0", ok="#74D5A5", error="#FF9D99",
    info="#C5BFBC", warning="#F0C17D", invalid="#513133", status="#17171A",
    surface="#17171A", rail="#202024", pink="#986B70", peach="#A18367",
    lavender="#817BA6", mint="#70998B", pastel_text="#111111"))

# Wine-to-Rosewood: quiet surfaces, one dark anchor, and restrained accents.
THEMES["light"].update(dict(window="#F8E6E9", surface="#FDF9FA", panel="#FFFFFF", rail="#4A1220",
    sidebar="#4A1220", sidebar_text="#F8E6E9", sidebar_hover="#7A1F35", sidebar_selected="#7A1F35",
    sidebar_selected_text="#FFFFFF", text="#4A1220", heading="#4A1220", muted="#765F65", border="#EBD8DD",
    toolbar="#FDF9FA", toolbar_text="#4A1220", status="#FDF9FA", input="#FFFFFF", input_readonly="#FAF1F3",
    hover="#F8E6E9", pressed="#F2D9DE", accent="#7A1F35", accent_hover="#A63A50", accent_text="#FFFFFF",
    yellow="#F8E6E9", pink="#F4DFE3", olive="#F6E9EB", periwinkle="#EFD7DD", peach="#FAEFF1", lilac="#F1DEE2",
    lavender="#EFD7DD", mint="#F5EAEC", pastel_text="#4A1220", ok="#446B58", error="#A63A50", warning="#A63A50"))
THEMES["dark"].update(dict(window="#1A1013", surface="#24171B", panel="#302025", rail="#4A1220",
    sidebar="#4A1220", sidebar_text="#F8E6E9", sidebar_hover="#7A1F35", sidebar_selected="#A63A50",
    sidebar_selected_text="#FFFFFF", text="#F8E6E9", heading="#FFF0F2", muted="#CCAFB6", border="#51343D",
    toolbar="#24171B", toolbar_text="#F8E6E9", status="#24171B", input="#3A292E", input_readonly="#302329",
    hover="#432D34", pressed="#5B3842", accent="#D17A88", accent_hover="#E49AA5", accent_text="#2A1018",
    disabled="#352A2E", disabled_text="#AA9399", ok="#9BC5AB", error="#F0A1AA", info="#CCAFB6",
    warning="#E8BAC2", invalid="#5B303B", yellow="#51333C", pink="#55333D", olive="#48353B",
    periwinkle="#5A3742", peach="#4C343B", lilac="#54343F", lavender="#5A3742", mint="#47353A",
    pastel_text="#F8E6E9"))

# Sign uses pink and lilac; calculation steps use the periwinkle block.
for colors in THEMES.values():
    colors.update(p3_card=colors["periwinkle"], p3_inner=colors["surface"],
                  p3_row=colors["hover"], p3_text=colors["text"],
                  p3_muted=colors["muted"], p3_border=colors["border"],
                  p3_variable=colors["heading"], p3_value=colors["text"])

_STYLE = """
QWidget {{ font-size: 11pt; color: {text}; }}
QMainWindow, QDialog, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {window}; }}
QToolTip {{ background: {panel}; color: {text}; border: 1px solid {border}; }}

/* toolbar */
QToolBar {{ background: {toolbar}; border: none; border-bottom: 1px solid {border}; padding: 10px 16px; spacing: 12px; }}
QToolBar QLabel {{ color: {toolbar_text}; background: transparent; }}
QToolBar QLabel#appTitle {{ color: {heading}; font-size: 16pt; font-weight: 600; padding-right: 12px; }}
QToolBar QLabel#curveInfo {{ color: {muted}; }}

/* sidebar */
QListWidget#sidebar {{ background: {sidebar}; border: none; outline: none; padding: 14px 10px; }}
QListWidget#sidebar::item {{ color: {sidebar_text}; padding: 13px 14px; margin: 3px 0; border-radius: 8px; }}
QListWidget#sidebar::item:hover {{ background: {sidebar_hover}; }}
QListWidget#sidebar::item:selected {{ background: {sidebar_selected}; color: {sidebar_selected_text}; font-weight: 600; }}

/* panels and text */
QGroupBox {{ background: {panel}; border: 1px solid {border}; border-radius: 9px;
            margin-top: 16px; padding: 15px 13px 13px 13px; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 5px; color: {heading}; }}
QGroupBox QLabel, QGroupBox QCheckBox {{ font-weight: normal; background: transparent; }}
QLabel[note="true"] {{ color: {muted}; font-size: 10pt; }}
QLabel[kind="ok"] {{ color: {ok}; }}
QLabel[kind="error"] {{ color: {error}; }}
QLabel[kind="info"] {{ color: {info}; }}
QLabel[kind="warning"] {{ color: {warning}; font-weight: 600; }}
QLabel#comingSoon {{ color: {muted}; font-size: 11pt; }}
*[mono="true"], BigIntField, HexField {{ font-family: {mono}; }}

/* buttons */
QPushButton, QToolButton {{ padding: 8px 16px; border: 1px solid {border}; border-radius: 6px;
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

/* curve picker cards (gui/widgets/curve_picker.py) and the toolbar curve button */
QPushButton[card="true"] {{ background: {panel}; border: 1px solid {border}; border-radius: 8px; padding: 0; text-align: left; }}
QPushButton[card="true"]:hover {{ background: {hover}; border-color: {accent}; }}
QPushButton[card="true"]:focus {{ border: 2px solid {accent}; }}
QPushButton[card="true"][current="true"] {{ border: 2px solid {ok}; }}
QLabel[cardTitle="true"] {{ color: {heading}; font-size: 11pt; background: transparent; }}
QLabel[badge="true"] {{ background: {ok}; color: {accent_text}; border-radius: 8px; padding: 1px 8px; font-size: 8pt; font-weight: 600; }}
QLabel[groupTitle="true"] {{ color: {heading}; font-size: 12pt; font-weight: 600; padding-top: 8px; }}
QPushButton#curveButton {{ font-weight: 600; padding: 6px 16px; }}
QPushButton[big="true"] {{ padding: 10px 22px; font-size: 11pt; }}

/* menus and status bar */
QMenuBar {{ background: {toolbar}; color: {toolbar_text}; }}
QMenuBar::item:selected, QMenu::item:selected {{ background: {hover}; color: {text}; }}
QMenu {{ background: {panel}; border: 1px solid {border}; }}
QStatusBar {{ background: {status}; color: {muted}; }}
QStatusBar QLabel {{ color: {muted}; padding: 0 8px; }}
QStatusBar QLabel#statusCurve {{ font-family: {mono}; }}
QProgressBar {{ border: 1px solid {border}; border-radius: 5px; background: {input_readonly}; }}
QProgressBar::chunk {{ background: {accent}; border-radius: 4px; }}

/* Pastel dashboard components. Properties keep page widgets theme-aware. */
QWidget#appSurface, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {surface}; border: none; }}
QWidget#appSurface {{ border: 1px solid {border}; border-radius: 26px; }}
QWidget#appSurface > QWidget {{ border: none; }}
QWidget#sidePanel {{ background: {hover}; border-radius: 24px; }}
QWidget#sidePanel QLabel {{ background: transparent; }}
QWidget#sidePanel QLabel#activityCard {{ background: {panel}; border-radius: 20px; padding: 16px; }}
QWidget#rail {{ background: {rail}; border-radius: 24px; }}
QWidget#sidebar {{ background: {rail}; }}
QLabel#railLogo {{ color: {sidebar_text}; background: transparent; font-size: 20px; font-weight: 500; padding: 12px 0; }}
QPushButton[nav="true"] {{ background: transparent; color: {sidebar_text}; text-align: left; border: none; border-radius: 12px; padding: 5px 10px; }}
QPushButton[nav="true"]:hover {{ background: {sidebar_hover}; color: {sidebar_selected_text}; }}
QPushButton[nav="true"]:checked {{ background: {sidebar_selected}; color: {sidebar_selected_text}; }}
QToolBar {{ background: {surface}; border: none; }}
QListWidget#sidebar {{ background: {rail}; border-radius: 24px; padding: 8px; }}
QListWidget#sidebar::item {{ background: transparent; border-radius: 12px; padding: 0 11px; margin: 3px 8px; min-height: 44px; }}
QListWidget#sidebar::item:selected {{ background: {sidebar_selected}; }}
QGroupBox {{ background: {panel}; border: none; border-radius: 20px; margin-top: 18px; padding: 20px 16px 16px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 16px; padding: 4px; }}
QPushButton, QToolButton, QComboBox {{ border: 2px solid transparent; border-radius: 18px; background: {hover}; padding: 7px 15px; }}
QToolButton {{ padding: 2px; }}
QPushButton:focus, QToolButton:focus, QComboBox:focus {{ border: 2px solid {accent}; }}
QPushButton[primary="true"] {{ border: 2px solid {accent}; }}
QLineEdit, QPlainTextEdit, QTextEdit {{ border: 2px solid transparent; border-radius: 14px; padding: 7px; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border: 2px solid {accent}; }}
QWidget[card="pink"] {{ background: {pink}; color: {pastel_text}; border: none; border-radius: 22px; }}
QWidget[card="peach"] {{ background: {peach}; color: {pastel_text}; border: none; border-radius: 22px; }}
QWidget[card="lavender"] {{ background: {lavender}; color: {pastel_text}; border: none; border-radius: 22px; }}
QWidget[card="mint"] {{ background: {mint}; color: {pastel_text}; border: none; border-radius: 22px; }}
QWidget[card="white"] {{ background: {panel}; border: none; border-radius: 22px; }}
QWidget[card="yellow"] {{ background: {yellow}; color: {pastel_text}; border-radius: 18px; }}
QWidget[card="olive"] {{ background: {olive}; color: {pastel_text}; border-radius: 18px; }}
QWidget[card="periwinkle"] {{ background: {periwinkle}; color: {pastel_text}; border-radius: 18px; }}
QWidget[card="lilac"] {{ background: {lilac}; color: {pastel_text}; border-radius: 18px; }}
QFrame[card="pink"] QLabel, QFrame[card="peach"] QLabel, QFrame[card="lavender"] QLabel, QFrame[card="mint"] QLabel {{ color: {pastel_text}; background: transparent; }}
QFrame[card="yellow"] QLabel, QFrame[card="olive"] QLabel, QFrame[card="periwinkle"] QLabel, QFrame[card="lilac"] QLabel {{ color: {pastel_text}; background: transparent; }}
QLabel[cardHeader="true"] {{ font-size: 13px; font-weight: 600; }}
QLabel[step="true"] {{ background: {accent}; color: {accent_text}; border-radius: 16px; font-weight: 600; }}
QFrame QLabel[step="true"] {{ background: {accent}; color: {accent_text}; }}
QPushButton[chip="true"]:checked {{ background: {accent}; color: {accent_text}; }}
QLabel[badge="true"] {{ background: {panel}; color: {text}; border-radius: 12px; padding: 4px 10px; }}
QLabel[heading="hero"] {{ color: {heading}; font-size: 36px; font-weight: 500; }}
QLabel[heading="section"] {{ color: {heading}; font-size: 16pt; font-weight: 600; }}
QLabel[muted="true"] {{ color: {muted}; }}
QLabel[formula="true"] {{ background: {input_readonly}; border-radius: 14px; padding: 14px; font-size: 20pt; }}
QPushButton[tutorialChoice="true"] {{ text-align: left; padding: 10px 14px; }}
QLabel[result="good"] {{ background: {mint}; color: {pastel_text}; border-radius: 24px; padding: 12px; }}
QLabel[result="bad"] {{ background: {pink}; color: {pastel_text}; border-radius: 24px; padding: 12px; }}
QLabel[result="info"] {{ background: {hover}; border-radius: 24px; padding: 12px; }}
QScrollBar:vertical {{ background: transparent; width: 6px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 3px; min-height: 25px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 6px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: #D8CFC0; border-radius: 3px; min-width: 25px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
QComboBox::drop-down {{ border: none; width: 32px; }}
QComboBox::down-arrow {{ image: url(ecdsa_edu/gui/assets/icons/chevron.svg); width: 12px; height: 12px; }}
QFrame[card="pink"] QComboBox, QFrame[card="peach"] QComboBox, QFrame[card="lavender"] QComboBox, QFrame[card="mint"] QComboBox {{ background: white; color: #141414; }}
QFrame[card="periwinkle"] QComboBox {{ background: white; color: #141414; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {text}; border-radius: 5px; background: {input}; }}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; image: url(ecdsa_edu/gui/assets/icons/check.svg); }}
QRadioButton::indicator {{ width: 16px; height: 16px; border: 1px solid {text}; border-radius: 8px; background: {input}; }}
QRadioButton::indicator:checked {{ background: {accent}; border: 4px solid {input}; }}
QToolTip, QMenu {{ background: {panel}; color: {text}; border: 1px solid {border}; border-radius: 12px; padding: 6px; }}
QStatusBar {{ background: {status}; }}
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
    if app.style().objectName().lower() != "fusion":
        app.setStyle("Fusion")
    font_path = Path(__file__).parent / "assets" / "fonts" / "DMSans-Variable.ttf"
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
    app.setFont(QFont(families[0] if families else "Segoe UI", 10))
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
    app.setStyleSheet((_STYLE + P3_STYLE).format(mono=MONO_FONT, **c))
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
    apply_theme(app, "dark")
    _install_excepthook()
    state = AppState()
    window = MainWindow(state)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
