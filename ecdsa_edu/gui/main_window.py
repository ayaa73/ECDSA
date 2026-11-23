"""Main window: sidebar on the left, one page per topic, curve selector on top (owner: P2).

Pages are imported by name from the table ``PAGE_SPECS``. If a page's module is
missing, is still a stub, or crashes while being built, a "coming soon" page is
shown instead - one unfinished page never stops the application from starting.

What a page must provide (see the interface contract):

    class XTab(QWidget):
        def __init__(self, state: AppState): ...
        def set_curve(self, curve): ...      # called whenever the active curve changes
        HELP = "3-4 plain sentences"         # optional: shown by the toolbar "?" button

Toolbar: curve selector, Beginner/Expert switch (Ctrl+E), help "?" (F1) and the
light/dark theme switch (Ctrl+D). The window size, the mode and the
"show Start here at startup" choice are remembered between runs.
"""
from __future__ import annotations

import html
import importlib
import sys
import traceback
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QToolBar,
    QToolButton,
    QWidget,
)

from ecdsa_edu import __version__
from ecdsa_edu.gui.app import apply_theme, current_theme, theme_colors
from ecdsa_edu.gui.app_state import AppState

__all__ = ["MainWindow", "PAGE_SPECS", "PageSpec", "make_icon"]


@dataclass(frozen=True)
class PageSpec:
    """One sidebar entry: ``module.class_name`` is built as ``cls(state)``."""

    title: str
    module: str
    class_name: str
    owner: str
    icon: str


# The single place to edit if a teammate names a module or class differently.
PAGE_SPECS: list[PageSpec] = [
    PageSpec("Start here", "ecdsa_edu.gui.tutorial.tutorial_tab", "TutorialTab", "P4", "home"),
    PageSpec("Overview", "ecdsa_edu.gui.overview_tab", "OverviewTab", "GUI", "overview"),
    PageSpec("Keys", "ecdsa_edu.gui.tabs.keys_tab", "KeysTab", "P2", "key"),
    PageSpec("Sign", "ecdsa_edu.gui.tabs.sign_tab", "SignTab", "P3", "pen"),
    PageSpec("Verify", "ecdsa_edu.gui.tabs.verify_tab", "VerifyTab", "P4", "check"),
    PageSpec("Curve Explorer", "ecdsa_edu.gui.tabs.curve_explorer_tab", "CurveExplorerTab", "P1", "curve"),
    PageSpec("Learn ECDSA", "ecdsa_edu.gui.learn.wizard", "LearnWizard", "P4", "learn"),
    PageSpec("Attack Demo", "ecdsa_edu.gui.tabs.attack_tab", "AttackTab", "P4", "warning"),
    PageSpec("Theory", "ecdsa_edu.gui.theory.theory_tab", "TheoryTab", "P4", "book"),
    PageSpec("History", "ecdsa_edu.gui.tabs.history_tab", "HistoryTab", "P4", "clock"),
]

START_PAGE = "Start here"  # shown first, unless the user turned that off
FALLBACK_START_PAGE = "Keys"  # shown first otherwise
SETTING_SHOW_TUTORIAL = "tutorial/show_at_startup"  # P4's "Don't show at startup" box writes this
SETTING_WINDOW_SIZE = "window/size"
DEFAULT_WINDOW_SIZE = (1200, 800)
NO_HELP_TEXT = "No help written yet for this page."

MODE_TOOLTIP = (
    "Beginner mode shows only what you need for the main task.\n"
    "Expert mode also shows advanced options, such as typing your own private key,\n"
    "choosing the hash, DER encoding and the full step-by-step math.  (Ctrl+E)"
)

CUSTOM_DIALOG = ("ecdsa_edu.gui.tabs.custom_curve_dialog", "CustomCurveDialog")
CURVE_PICKER = ("ecdsa_edu.gui.widgets.curve_picker", "CurvePicker")
_CUSTOM_ENTRY = "\x00custom"  # item data of the "Custom curve…" combo entry


# --------------------------------------------------------------------------
# Sidebar icons: drawn in code, so they need no image files and follow the theme
# --------------------------------------------------------------------------
def _icon_path(name: str) -> QPainterPath:
    """Outline of the icon ``name`` in a 24 x 24 box."""
    p = QPainterPath()
    if name == "overview":  # connected steps in the ECDSA flow
        p.addRoundedRect(QRectF(2.5, 5, 6, 5), 1.2, 1.2)
        p.addRoundedRect(QRectF(15.5, 5, 6, 5), 1.2, 1.2)
        p.addRoundedRect(QRectF(9, 15, 6, 5), 1.2, 1.2)
        p.moveTo(8.5, 7.5); p.lineTo(15.5, 7.5)
        p.moveTo(18.5, 10); p.lineTo(13.5, 15)
        p.moveTo(5.5, 10); p.lineTo(10.5, 15)
    elif name == "home":  # house: the Start here page
        p.moveTo(3, 11.5); p.lineTo(12, 3.5); p.lineTo(21, 11.5)
        p.moveTo(5.5, 9.5); p.lineTo(5.5, 20.5); p.lineTo(18.5, 20.5); p.lineTo(18.5, 9.5)
        p.moveTo(10, 20.5); p.lineTo(10, 14.5); p.lineTo(14, 14.5); p.lineTo(14, 20.5)
    elif name == "clock":  # clock: the History page
        p.addEllipse(QPointF(12, 12), 9, 9)
        p.moveTo(12, 6.5); p.lineTo(12, 12); p.lineTo(16, 14.5)
    elif name == "key":
        p.addEllipse(QPointF(8, 8), 4.5, 4.5)
        p.moveTo(11.2, 11.2); p.lineTo(20.5, 20.5)
        p.moveTo(16.5, 16.5); p.lineTo(19, 14)
        p.moveTo(19.5, 19.5); p.lineTo(21.5, 17.5)
    elif name == "pen":
        p.moveTo(4, 20); p.lineTo(5, 15); p.lineTo(16, 4); p.lineTo(20, 8); p.lineTo(9, 19); p.closeSubpath()
        p.moveTo(13.5, 6.5); p.lineTo(17.5, 10.5)
    elif name == "check":
        p.addEllipse(QPointF(12, 12), 9, 9)
        p.moveTo(7.5, 12.5); p.lineTo(10.8, 15.8); p.lineTo(16.5, 9)
    elif name == "curve":  # the two pieces of an elliptic curve
        p.addEllipse(QPointF(6.5, 12), 3, 4)
        p.moveTo(21, 3); p.cubicTo(9, 10, 9, 14, 21, 21)
    elif name == "learn":  # graduation cap
        p.moveTo(12, 5); p.lineTo(22, 10); p.lineTo(12, 15); p.lineTo(2, 10); p.closeSubpath()
        p.moveTo(6, 12.5); p.lineTo(6, 17); p.quadTo(12, 21, 18, 17); p.lineTo(18, 12.5)
    elif name == "warning":
        p.moveTo(12, 3.5); p.lineTo(22, 20); p.lineTo(2, 20); p.closeSubpath()
        p.moveTo(12, 9.5); p.lineTo(12, 14.5)
        p.addEllipse(QPointF(12, 17.2), 0.4, 0.4)
    elif name == "book":
        p.moveTo(12, 6); p.quadTo(7, 3.5, 3, 5); p.lineTo(3, 19); p.quadTo(7, 17.5, 12, 20)
        p.quadTo(17, 17.5, 21, 19); p.lineTo(21, 5); p.quadTo(17, 3.5, 12, 6); p.lineTo(12, 20)
    elif name == "start":  # a "play" triangle in a circle
        p.addEllipse(QPointF(12, 12), 9, 9)
        p.moveTo(10, 8); p.lineTo(16, 12); p.lineTo(10, 16); p.closeSubpath()
    elif name == "history":  # a clock
        p.addEllipse(QPointF(12, 12), 9, 9)
        p.moveTo(12, 7); p.lineTo(12, 12); p.lineTo(15.5, 14)
    else:  # unknown name: a plain dot
        p.addEllipse(QPointF(12, 12), 3, 3)
    return p


def _draw_icon(name: str, color: str, size: int = 22) -> QPixmap:
    scale = 2  # draw at double resolution so the icon stays sharp on HiDPI screens
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size * scale / 24, size * scale / 24)
    pen = QPen(QColor(color), 1.7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawPath(_icon_path(name))
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return pixmap


def make_icon(name: str, color: str, selected_color: str | None = None) -> QIcon:
    """Line icon by name: home, overview, key, pen, check, curve, learn, warning, book, clock
    (start and history are older names that still work)."""
    icon = QIcon()
    icon.addPixmap(_draw_icon(name, color), QIcon.Mode.Normal)
    icon.addPixmap(_draw_icon(name, selected_color or color), QIcon.Mode.Selected)
    return icon


# --------------------------------------------------------------------------
# The window
# --------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """Application shell: toolbar, sidebar, pages, menus, status bar."""

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self.setWindowTitle("ECDSA Lab")
        self.setMinimumSize(900, 600)
        self._restore_window_size()

        self._build_toolbar()
        self._build_pages()
        self._build_menus()
        self._build_status_bar()

        state.curveChanged.connect(self._on_curve_changed)
        state.modeChanged.connect(self._sync_mode_controls)
        state.pageRequested.connect(self.show_page)
        state.curvesListChanged.connect(self._fill_curve_combo)
        state.keysChanged.connect(self._update_status)
        state.signatureChanged.connect(self._update_status)
        self._refresh_curve_widgets()
        self._update_status()
        self._apply_icons()

    # ------------------------------------------------------------ toolbar
    def _build_toolbar(self) -> None:
        bar = QToolBar("Main")
        bar.setMovable(False)
        bar.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.addToolBar(bar)

        title = QLabel("ECDSA Lab")
        title.setObjectName("appTitle")
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.curve_info = QLabel()
        self.curve_info.setObjectName("curveInfo")
        label = QLabel("Curve")
        self.curve_combo = QComboBox()
        self.curve_combo.setMinimumWidth(190)
        self.curve_combo.setAccessibleName("Curve")
        self.curve_combo.setToolTip("The curve used by every page")
        label.setBuddy(self.curve_combo)
        self.curve_combo.setToolTip("The curve used by every page. The last entry makes your own curve.")

        # Beginner / Expert switch: a button that stays pressed in Expert mode.
        self.mode_button = QToolButton()
        self.mode_button.setCheckable(True)
        self.mode_button.setAccessibleName("Expert mode")
        self.mode_button.setToolTip(MODE_TOOLTIP)

        # "?" button: help for the page that is shown.
        self.help_button = QToolButton()
        self.help_button.setText("?")
        self.help_button.setAccessibleName("Help for this page")
        self.help_button.setToolTip("Help for this page  (F1)")

        self.theme_button = QToolButton()
        self.theme_button.setCheckable(True)
        self.theme_button.setToolTip("Switch between the light and the dark theme  (Ctrl+D)")

        # The main way to choose a curve: a big button that opens the card picker.
        # (The combo box above stays as a quick shortcut, but only in Expert mode.)
        self.curve_button = QPushButton()
        self.curve_button.setObjectName("curveButton")
        self.curve_button.setAccessibleName("Choose a curve")
        self.curve_button.setToolTip("Choose the curve every page uses (Ctrl+K)")
        self.curve_button.setShortcut(QKeySequence("Ctrl+K"))

        widgets = [title, spacer, self.curve_info, self.curve_button, label, self.curve_combo,
                   self.mode_button, self.help_button, self.theme_button]
        self._toolbar_actions = {}
        for widget in widgets:
            # Widgets inside a toolbar are shown and hidden through their action.
            self._toolbar_actions[widget] = bar.addWidget(widget)
        self._expert_only = [label, self.curve_combo]

        self._fill_curve_combo()
        self.curve_combo.activated.connect(self._on_combo_activated)  # user choices only
        self.curve_button.clicked.connect(self.open_curve_picker)
        self.mode_button.clicked.connect(self._on_mode_button)
        self.help_button.clicked.connect(self.show_help)
        self.theme_button.clicked.connect(lambda checked: self.set_theme("dark" if checked else "light"))
        self._sync_theme_controls()
        self._sync_mode_controls()

    def _fill_curve_combo(self) -> None:
        """(Re)build the curve list: built-in curves, custom curves, then "Custom curve…"."""
        combo = self.curve_combo
        combo.blockSignals(True)
        combo.clear()
        curves = self.state.available_curves()
        for name in curves:
            combo.addItem(name, name)
        if not curves:
            combo.addItem("(no curves yet)", None)
            combo.model().item(0).setEnabled(False)
        combo.insertSeparator(combo.count())
        combo.addItem("Custom curve…", _CUSTOM_ENTRY)
        combo.blockSignals(False)
        self._select_current_curve()

    def _select_current_curve(self) -> None:
        """Make the combo show the state's curve (without emitting anything)."""
        combo = self.curve_combo
        curve = self.state.curve
        index = combo.findData(curve.name) if curve is not None else 0
        combo.blockSignals(True)
        combo.setCurrentIndex(max(index, 0))
        combo.blockSignals(False)

    def _on_combo_activated(self, index: int) -> None:
        data = self.curve_combo.itemData(index)
        if data == _CUSTOM_ENTRY:
            self._select_current_curve()  # "Custom curve…" is a command, not a selection
            self.open_custom_curve_dialog()
            return
        curve = self.state.available_curves().get(data)
        if curve is not None:
            self.state.set_curve(curve)  # -> curveChanged -> every page's set_curve()

    def open_curve_picker(self) -> None:
        """Show the curve cards; use the chosen curve, or open the custom-curve dialog."""
        module_name, class_name = CURVE_PICKER
        try:
            picker_class = getattr(importlib.import_module(module_name), class_name)
        except (ImportError, AttributeError):
            self.curve_combo.showPopup()  # no picker available: fall back to the plain list
            return
        picker = picker_class(self.state, self)
        if not picker.exec():
            return
        if picker.wants_custom():
            self.open_custom_curve_dialog()
        elif picker.chosen() is not None:
            self.use_curve(picker.chosen())

    def open_custom_curve_dialog(self) -> None:
        """Open the custom-curve dialog, or say "coming soon" while it does not exist."""
        module_name, class_name = CUSTOM_DIALOG
        try:
            dialog_class = getattr(importlib.import_module(module_name), class_name)
        except (ImportError, AttributeError):
            QMessageBox.information(
                self, "Custom curve", "Coming soon: defining your own small curve is not available yet."
            )
            return
        dialog = dialog_class(self.state, self)
        if dialog.exec() and dialog.curve() is not None:
            curve = dialog.curve()
            self.use_curve(curve)  # adds it to the selector and selects it
            if self.state.curve == curve:
                self.statusBar().showMessage(
                    f"Custom curve “{curve.name}” added: n = {curve.n}, h = {curve.h}", 15000
                )
                QMessageBox.information(
                    self,
                    "Your curve is ready",
                    f"Your curve “{curve.name}” has n = {curve.n} points in G's group and "
                    f"cofactor h = {curve.h}, so it works for ECDSA.\n\n"
                    "It is now selected on every page.",
                )

    def use_curve(self, curve) -> None:
        """Register (if custom) and activate ``curve``."""
        try:
            self.state.register_curve(curve)
        except ValueError as exc:
            QMessageBox.warning(self, "Custom curve", str(exc))
            return
        self.state.set_curve(curve)

    # -------------------------------------------------------------- pages
    def _build_pages(self) -> None:
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(200)
        self.sidebar.setIconSize(QSize(22, 22))
        self.sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar.setAccessibleName("Pages")
        self.stack = QStackedWidget()
        self.pages: dict[str, QWidget] = {}

        for spec in PAGE_SPECS:
            page = self._load_page(spec)
            self.pages[spec.title] = page
            self.stack.addWidget(page)
            item = QListWidgetItem(spec.title)
            item.setData(Qt.ItemDataRole.UserRole, spec.icon)
            if page.property("placeholder"):
                item.setToolTip(f"{spec.title} - coming soon")
            self.sidebar.addItem(item)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.show_page(self._start_page_title())

    def _tutorial_settings(self):
        """Where the "show Start here at startup" choice lives.

        P4's Start here page stores it with its own settings() helper; we read and
        write the same place, so its checkbox and the View menu always agree.
        """
        try:
            from ecdsa_edu.gui.tutorial import tutorial_tab
            return tutorial_tab.settings()
        except Exception:  # page not written yet, or a different version
            return self.state.settings

    def _show_tutorial_at_startup(self) -> bool:
        value = self._tutorial_settings().value(SETTING_SHOW_TUTORIAL, True)
        return value not in (False, "false", "0", 0)

    def _set_show_tutorial(self, checked: bool) -> None:
        self._tutorial_settings().setValue(SETTING_SHOW_TUTORIAL, bool(checked))
        box = getattr(self.pages.get(START_PAGE), "startup_box", None)  # P4's checkbox, if shown
        if box is not None and box.isChecked() != bool(checked):
            box.blockSignals(True)
            box.setChecked(bool(checked))
            box.blockSignals(False)

    def _start_page_title(self) -> str:
        """Which page to show first: "Start here", unless it is turned off or not written yet."""
        show_tutorial = self._show_tutorial_at_startup()
        tutorial = self.pages.get(START_PAGE)
        if show_tutorial and tutorial is not None and not tutorial.property("placeholder"):
            return START_PAGE
        if FALLBACK_START_PAGE in self.pages:
            return FALLBACK_START_PAGE
        for title in self.pages:  # otherwise the first page in the sidebar
            return title
        return ""  # no pages at all

    def _load_page(self, spec: PageSpec) -> QWidget:
        """Import and build one page; fall back to "coming soon" on any failure."""
        try:
            page_class = getattr(importlib.import_module(spec.module), spec.class_name)
        except (ImportError, AttributeError) as exc:
            # Module missing, still a stub, or waiting for a teammate's module.
            return self._coming_soon(spec, exc)
        except Exception as exc:  # the module exists but fails while importing
            traceback.print_exc(file=sys.stderr)
            return self._coming_soon(spec, exc)
        try:
            page = page_class(self.state)
        except Exception as exc:  # a broken page must not prevent start-up
            traceback.print_exc(file=sys.stderr)
            return self._coming_soon(spec, exc)
        if callable(getattr(page, "set_curve", None)):
            self.state.curveChanged.connect(page.set_curve)
        return page

    @staticmethod
    def _coming_soon(spec: PageSpec, exc: Exception) -> QWidget:
        label = QLabel(
            f"<h2>{html.escape(spec.title)}</h2>"
            f"<p>Coming soon (owner: {html.escape(spec.owner)}).</p>"
            f"<p><small>Expected <code>{spec.module}.{spec.class_name}</code><br>"
            f"{html.escape(type(exc).__name__)}: {html.escape(str(exc))}</small></p>"
        )
        label.setObjectName("comingSoon")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        label.setProperty("placeholder", True)
        return label

    def show_page(self, title: str) -> None:
        """Switch to the page with this sidebar title (also used by state.go_to)."""
        titles = list(self.pages)
        if title not in titles:
            if title:
                self.statusBar().showMessage(f"There is no page called “{title}”.", 5000)
            return
        self.sidebar.setCurrentRow(titles.index(title))

    def current_page_title(self) -> str:
        """Title of the page that is shown ('' if there are no pages)."""
        row = self.sidebar.currentRow()
        titles = list(self.pages)
        if 0 <= row < len(titles):
            return titles[row]
        return ""

    # ------------------------------------------------------- help and mode
    def show_help(self) -> None:
        """Show the HELP text of the current page (the toolbar "?" button, F1)."""
        title = self.current_page_title()
        if not title:
            return
        page = self.pages[title]
        if page.property("placeholder"):
            text = "This page is not written yet. It is coming soon."
        else:
            text = getattr(page, "HELP", None)
            # The Learn wizard: prefer the help of the step that is on screen.
            steps = getattr(page, "pages", None)
            index = getattr(page, "index", None)
            if isinstance(steps, list) and isinstance(index, int) and 0 <= index < len(steps):
                text = getattr(steps[index], "HELP", None) or text
            text = text or NO_HELP_TEXT
        QMessageBox.information(self, f"Help: {title}", text)

    def _on_mode_button(self, checked: bool) -> None:
        if checked:
            self.state.set_mode("expert")
        else:
            self.state.set_mode("beginner")

    def toggle_mode(self) -> None:
        """Switch between Beginner and Expert (View menu, Ctrl+E)."""
        if self.state.mode == "expert":
            self.state.set_mode("beginner")
        else:
            self.state.set_mode("expert")

    def _sync_mode_controls(self, _mode: str = "") -> None:
        """Make the toolbar button and the menu entry show the current mode."""
        expert = self.state.mode == "expert"
        self.mode_button.setChecked(expert)
        if expert:
            self.mode_button.setText("Mode: Expert")
        else:
            self.mode_button.setText("Mode: Beginner")
        action = getattr(self, "mode_action", None)  # menus are built after the toolbar
        if action is not None:
            action.setChecked(expert)
        for widget in self._expert_only:  # the curve combo is an Expert shortcut
            self._toolbar_actions[widget].setVisible(expert)

    # ---------------------------------------------------- window size
    def _restore_window_size(self) -> None:
        """Use the size from last time, but never bigger than the screen."""
        width, height = DEFAULT_WINDOW_SIZE
        saved = self.state.settings.value(SETTING_WINDOW_SIZE)
        if isinstance(saved, QSize) and saved.isValid():
            width, height = saved.width(), saved.height()
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            width = min(width, available.width())
            height = min(height, available.height())
        self.resize(width, height)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Remember the window size for next time."""
        self.state.settings.setValue(SETTING_WINDOW_SIZE, self.size())
        super().closeEvent(event)

    # -------------------------------------------------------------- menus
    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        keys_page = self.pages.get("Keys")
        for text, method, shortcut in (
            ("&Load private key…", "load_private_key_dialog", QKeySequence.StandardKey.Open),
            ("Load &public key…", "load_public_key_dialog", None),
            ("&Save private key…", "save_private_key_dialog", QKeySequence.StandardKey.Save),
            ("Save p&ublic key…", "save_public_key_dialog", None),
        ):
            handler = getattr(keys_page, method, None)
            if handler is None:  # the Keys page is not available (yet)
                continue
            action = QAction(text, self)
            if shortcut is not None:
                action.setShortcut(shortcut)
            action.triggered.connect(lambda _checked=False, h=handler: self._run_keys_action(h))
            file_menu.addAction(action)
        if file_menu.actions():
            file_menu.addSeparator()
        custom = QAction("&Custom curve…", self)
        custom.triggered.connect(self.open_custom_curve_dialog)
        file_menu.addAction(custom)
        file_menu.addSeparator()
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        view_menu = self.menuBar().addMenu("&View")
        self.theme_action = QAction("&Dark theme", self)
        self.theme_action.setCheckable(True)
        self.theme_action.setShortcut(QKeySequence("Ctrl+D"))
        self.theme_action.triggered.connect(lambda checked: self.set_theme("dark" if checked else "light"))
        view_menu.addAction(self.theme_action)
        self.mode_action = QAction("&Expert mode", self)
        self.mode_action.setCheckable(True)
        self.mode_action.setShortcut(QKeySequence("Ctrl+E"))
        self.mode_action.triggered.connect(self.toggle_mode)
        view_menu.addAction(self.mode_action)
        view_menu.addSeparator()
        self.tutorial_action = QAction("Show “Start here” at startup", self)
        self.tutorial_action.setCheckable(True)
        self.tutorial_action.setChecked(self._show_tutorial_at_startup())
        self.tutorial_action.toggled.connect(
            self._set_show_tutorial
        )
        view_menu.addAction(self.tutorial_action)
        # P4's "Show this page when the app starts" box can change it too: refresh on open.
        view_menu.aboutToShow.connect(lambda: self.tutorial_action.setChecked(self._show_tutorial_at_startup()))
        self._sync_theme_controls()
        self._sync_mode_controls()

        help_menu = self.menuBar().addMenu("&Help")
        page_help = QAction("&Help for this page", self)
        page_help.setShortcut(QKeySequence("F1"))
        page_help.triggered.connect(self.show_help)
        help_menu.addAction(page_help)
        about = QAction("&About ECDSA Lab", self)
        about.triggered.connect(self._about)
        help_menu.addAction(about)

    def _run_keys_action(self, handler) -> None:
        self.show_page("Keys")
        handler()

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "About ECDSA Lab",
            f"<h3>ECDSA Lab {__version__}</h3>"
            "<p>An educational tool for the Elliptic Curve Digital Signature Algorithm. "
            "All elliptic-curve math is implemented from scratch in pure Python.</p>"
            "<p><b>For teaching only</b> - the code is not constant-time and key files are "
            "not encrypted. Do not use it to protect real data.</p>",
        )

    # -------------------------------------------------------------- theme
    def set_theme(self, theme: str) -> None:
        """Switch the application to "light" or "dark"."""
        apply_theme(QApplication.instance(), theme)
        self._sync_theme_controls()
        self._apply_icons()

    def toggle_theme(self) -> None:
        self.set_theme("light" if current_theme() == "dark" else "dark")

    def _sync_theme_controls(self) -> None:
        dark = current_theme() == "dark"
        self.theme_button.setChecked(dark)
        self.theme_button.setText("Light theme" if dark else "Dark theme")
        action = getattr(self, "theme_action", None)  # menus are built after the toolbar
        if action is not None:
            action.setChecked(dark)

    def _apply_icons(self) -> None:
        """(Re)draw the sidebar icons in the colours of the current theme."""
        colors = theme_colors(current_theme())
        for row in range(self.sidebar.count()):
            item = self.sidebar.item(row)
            item.setIcon(
                make_icon(item.data(Qt.ItemDataRole.UserRole), colors["sidebar_text"], colors["sidebar_selected_text"])
            )

    # ------------------------------------------------------------- status
    def _build_status_bar(self) -> None:
        self.status_curve = QLabel()
        self.status_curve.setObjectName("statusCurve")
        self.status_keys = QLabel()
        self.status_signature = QLabel()
        # Busy indicator: an "endless" progress bar, visible while a background job runs.
        self.busy_bar = QProgressBar()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setTextVisible(False)
        self.busy_bar.setFixedSize(120, 12)
        self.busy_bar.setVisible(False)
        # (permanent widgets stay visible while the status bar shows a message)
        self.statusBar().addPermanentWidget(self.busy_bar)
        for label in (self.status_curve, self.status_keys, self.status_signature):
            self.statusBar().addPermanentWidget(label)
        self.statusBar().setSizeGripEnabled(False)
        try:  # widgets/worker.py may still be a stub
            from ecdsa_edu.gui.widgets.worker import busy_tracker
        except ImportError:
            return
        busy_tracker().busyChanged.connect(self._on_busy_changed)

    def _on_busy_changed(self, busy: bool) -> None:
        self.busy_bar.setVisible(busy)
        if busy:
            self.statusBar().showMessage("Working…")
        else:
            self.statusBar().clearMessage()

    def _on_curve_changed(self, curve) -> None:
        self._refresh_curve_widgets()
        self._update_status()
        cleared = self.state.cleared_by_last_curve_change
        if cleared:
            self.statusBar().showMessage(f"New curve {curve.name}: {cleared} cleared.", 8000)
        else:
            self.statusBar().showMessage(f"New curve: {curve.name}.", 5000)

    def _refresh_curve_widgets(self) -> None:
        self._select_current_curve()
        curve = self.state.curve
        if curve is None:
            self.curve_info.setText("no curves available yet")
            self.curve_button.setText("Curve: none  ▾")
        else:
            self.curve_button.setText("Curve: " + curve.name + "  ▾")
            bits = curve.p.bit_length()
            kind = "toy curve" if bits <= 32 else "real-world curve"
            self.curve_info.setText(f"{bits}-bit field · {kind}")

    def _update_status(self) -> None:
        state = self.state
        curve = state.curve
        if curve is None:
            curve_text = "Curve: -"
        elif curve.n.bit_length() <= 64:  # toy and custom curves: the numbers are short enough to show
            curve_text = f"Curve: {curve.name}  ·  n = {curve.n}  ·  h = {curve.h}"
        else:
            curve_text = f"Curve: {curve.name}  ·  n: {curve.n.bit_length()} bits  ·  h = {curve.h}"
        self.status_curve.setText(curve_text)
        if state.priv is not None:
            keys = "key pair ready"
        elif state.pub is not None:
            keys = "public key only"
        else:
            keys = "no keys yet"
        self.status_keys.setText(f"Keys: {keys}")
        self.status_signature.setText("Signature: ready" if state.last_sig is not None else "Signature: none yet")
