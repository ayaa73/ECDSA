"""Main window: sidebar on the left, one page per topic, curve selector on top (owner: P2).

Pages are imported by name from the table ``PAGE_SPECS``. If a page's module is
missing, is still a stub, or crashes while being built, a "coming soon" page is
shown instead - one unfinished page never stops the application from starting.

What a page must provide (see the interface contract):

    class XTab(QWidget):
        def __init__(self, state: AppState): ...
        def set_curve(self, curve): ...      # called whenever the active curve changes
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
    PageSpec("Overview", "ecdsa_edu.gui.overview_tab", "OverviewTab", "GUI", "overview"),
    PageSpec("Keys", "ecdsa_edu.gui.tabs.keys_tab", "KeysTab", "P2", "key"),
    PageSpec("Sign", "ecdsa_edu.gui.tabs.sign_tab", "SignTab", "P3", "pen"),
    PageSpec("Verify", "ecdsa_edu.gui.tabs.verify_tab", "VerifyTab", "P4", "check"),
    PageSpec("Curve Explorer", "ecdsa_edu.gui.tabs.curve_explorer_tab", "CurveExplorerTab", "P1", "curve"),
    PageSpec("Learn ECDSA", "ecdsa_edu.gui.learn.wizard", "LearnWizard", "P4", "learn"),
    PageSpec("Attack Demo", "ecdsa_edu.gui.tabs.attack_tab", "AttackTab", "P4", "warning"),
    PageSpec("Theory", "ecdsa_edu.gui.theory.theory_tab", "TheoryTab", "P4", "book"),
]

CUSTOM_DIALOG = ("ecdsa_edu.gui.tabs.custom_curve_dialog", "CustomCurveDialog")
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
    """Line icon by name: overview, key, pen, check, curve, learn, warning, book."""
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
        self.resize(1240, 800)

        self._build_toolbar()
        self._build_pages()
        self._build_menus()
        self._build_status_bar()

        state.curveChanged.connect(self._on_curve_changed)
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
        self.theme_button = QToolButton()
        self.theme_button.setCheckable(True)
        self.theme_button.setToolTip("Switch between the light and the dark theme")

        for widget in (title, spacer, self.curve_info, label, self.curve_combo, self.theme_button):
            bar.addWidget(widget)

        self._fill_curve_combo()
        self.curve_combo.activated.connect(self._on_combo_activated)  # user choices only
        self.theme_button.clicked.connect(lambda checked: self.set_theme("dark" if checked else "light"))
        self._sync_theme_controls()

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
        self.sidebar.setCurrentRow(0)

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
        """Switch to the page with this sidebar title."""
        self.sidebar.setCurrentRow(list(self.pages).index(title))

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
        self._sync_theme_controls()

        help_menu = self.menuBar().addMenu("&Help")
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
        self.theme_button.setText("Light mode" if dark else "Dark mode")
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

    def _on_curve_changed(self, _curve) -> None:
        self._refresh_curve_widgets()
        self._update_status()

    def _refresh_curve_widgets(self) -> None:
        self._select_current_curve()
        curve = self.state.curve
        if curve is None:
            self.curve_info.setText("no curves available yet")
        else:
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
