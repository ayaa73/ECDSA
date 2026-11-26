"""Tests for the application shell (owner: P2): core/types.py, gui/app_state.py,
gui/app.py and gui/main_window.py.

They use small fake curves and fake pages, so they pass no matter how far the
other modules are (even while everything else is still a stub).
"""
from __future__ import annotations

import dataclasses
import sys
import types

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QWidget

from ecdsa_edu.core.types import PrivateKey, PublicKey, Signature
from ecdsa_edu.gui import app as app_module
from ecdsa_edu.gui import app_state as app_state_module
from ecdsa_edu.gui import main_window as mw
from ecdsa_edu.gui.app_state import AppState


@dataclasses.dataclass(frozen=True)
class FakeCurve:
    """Stands in for P1's Curve: same fields, no math."""

    name: str
    p: int = 17
    a: int = 2
    b: int = 2
    G: tuple[int, int] = (5, 1)
    n: int = 19
    h: int = 1


TOY = FakeCurve("toy-17")
TOY97 = FakeCurve("toy-97", p=97)
K1 = FakeCurve("secp256k1", p=2**256 - 2**32 - 977)
BUILTIN = {c.name: c for c in (TOY, TOY97, K1)}


@pytest.fixture
def state(qapp, monkeypatch) -> AppState:
    """An AppState whose built-in curves are the three fakes above."""
    monkeypatch.setattr(app_state_module, "_builtin_curves", lambda: dict(BUILTIN))
    return AppState()


@pytest.fixture
def light_theme(qapp):
    """Apply the light theme for one test and restore the application afterwards."""
    saved = (qapp.styleSheet(), qapp.palette(), qapp.style().objectName(), qapp.property("theme"))
    app_module.apply_theme(qapp, "light")
    yield
    qapp.setStyleSheet(saved[0])
    qapp.setPalette(saved[1])
    qapp.setStyle(saved[2])
    qapp.setProperty("theme", saved[3])


class FakePage(QWidget):
    """A page that follows the contract and records set_curve calls."""

    def __init__(self, state):
        super().__init__()
        self.state = state
        self.curves = []

    def set_curve(self, curve):
        self.curves.append(curve)


def _install_module(monkeypatch, name: str, **attrs) -> None:
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, name, module)


def _window(qtbot, state, monkeypatch, specs) -> mw.MainWindow:
    monkeypatch.setattr(mw, "PAGE_SPECS", specs)
    window = mw.MainWindow(state)
    qtbot.addWidget(window)
    return window


# ================================================================ types
def test_types_hold_the_contract_fields():
    priv, pub, sig = PrivateKey(7, TOY), PublicKey((0, 6), TOY), Signature(3, 4)
    assert (priv.d, priv.curve) == (7, TOY)
    assert (pub.Q, pub.curve) == ((0, 6), TOY)
    assert (sig.r, sig.s) == (3, 4)
    assert [f.name for f in dataclasses.fields(PrivateKey)] == ["d", "curve"]
    assert [f.name for f in dataclasses.fields(PublicKey)] == ["Q", "curve"]
    assert [f.name for f in dataclasses.fields(Signature)] == ["r", "s"]


def test_types_are_frozen_and_compare_by_value():
    with pytest.raises(dataclasses.FrozenInstanceError):
        PrivateKey(7, TOY).d = 8  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        PublicKey((0, 6), TOY).Q = (5, 1)  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        Signature(1, 2).r = 3  # type: ignore[misc]
    assert PrivateKey(7, TOY) == PrivateKey(7, TOY) and Signature(3, 4) == Signature(3, 4)
    assert PublicKey((0, 6), TOY) != PublicKey((5, 1), TOY)
    assert len({Signature(3, 4), Signature(3, 4)}) == 1  # hashable


def test_private_key_repr_does_not_leak_d():
    d = 0x1234567890ABCDEF1234567890ABCDEF
    text = repr(PrivateKey(d, K1))
    assert str(d) not in text and hex(d)[2:] not in text.lower()


# ============================================================= AppState
def test_state_defaults(state):
    assert state.curve == TOY  # toy-17 is the default
    assert state.priv is None and state.pub is None
    assert state.last_sig is None and state.last_msg is None
    assert list(state.available_curves()) == list(BUILTIN)


def test_state_without_any_curves(qapp, monkeypatch):
    """While P1's registry is a stub the state still works; curve is None."""
    monkeypatch.setattr(app_state_module, "_builtin_curves", lambda: {})
    state = AppState()
    assert state.curve is None and state.available_curves() == {}
    state.set_curve(TOY)
    assert state.curve == TOY


def test_explicit_start_curve(qapp, monkeypatch):
    monkeypatch.setattr(app_state_module, "_builtin_curves", lambda: dict(BUILTIN))
    custom = FakeCurve("mine", p=23)
    assert AppState(K1).curve == K1
    assert "mine" in AppState(custom).available_curves()


def test_set_curve_emits_and_clears_keys_and_signature(qtbot, state):
    state.set_keys(PrivateKey(7, TOY), PublicKey((0, 6), TOY))
    state.set_signature(Signature(3, 4), b"hi")
    received = []
    state.curveChanged.connect(received.append)
    with qtbot.waitSignals([state.curveChanged, state.keysChanged, state.signatureChanged]):
        state.set_curve(K1)
    assert received == [K1] and state.curve is K1
    assert (state.priv, state.pub, state.last_sig, state.last_msg) == (None, None, None, None)


def test_set_same_curve_is_a_no_op(qtbot, state):
    state.set_keys(PrivateKey(7, TOY), PublicKey((0, 6), TOY))
    with qtbot.assertNotEmitted(state.curveChanged), qtbot.assertNotEmitted(state.keysChanged):
        state.set_curve(TOY)
    assert state.priv is not None


def test_curve_can_be_assigned_like_an_attribute(qtbot, state):
    with qtbot.waitSignal(state.curveChanged):
        state.curve = TOY97
    assert state.curve == TOY97
    with pytest.raises(ValueError):
        state.set_curve(None)


def test_listeners_see_consistent_state_during_curve_change(state):
    state.set_keys(PrivateKey(7, TOY), PublicKey((0, 6), TOY))
    seen = []
    state.curveChanged.connect(lambda c: seen.append((c is state.curve, state.priv, state.pub)))
    state.set_curve(TOY97)
    assert seen == [(True, None, None)]


def test_set_keys_emits_once_and_checks_the_curve(state):
    count = []
    state.keysChanged.connect(lambda: count.append(1))
    state.set_keys(PrivateKey(7, TOY), PublicKey((0, 6), TOY))
    assert len(count) == 1 and state.priv.d == 7 and state.pub.Q == (0, 6)
    state.set_keys(None, PublicKey((5, 1), TOY))  # public key only is allowed
    assert state.priv is None
    with pytest.raises(ValueError):
        state.set_keys(PrivateKey(7, K1), PublicKey((1, 2), K1))  # other curve
    state.clear_keys()
    assert state.pub is None and len(count) == 3


def test_set_signature(qtbot, state):
    with qtbot.waitSignal(state.signatureChanged):
        state.set_signature(Signature(3, 4), b"msg")
    assert state.last_sig == Signature(3, 4) and state.last_msg == b"msg"


def test_plain_attribute_assignment_still_works(state):
    """Teammates may assign the attributes and emit the signal by hand."""
    state.last_sig, state.last_msg = Signature(1, 2), b"x"
    state.signatureChanged.emit()
    assert state.last_sig == Signature(1, 2)


def test_register_curve(qtbot, state):
    custom = FakeCurve("my-curve", p=23)
    with qtbot.waitSignal(state.curvesListChanged):
        state.register_curve(custom)
    assert list(state.available_curves())[-1] == "my-curve"
    with qtbot.assertNotEmitted(state.curvesListChanged):
        state.register_curve(custom)  # same curve again
        state.register_curve(TOY)  # built-in: nothing to do
    with pytest.raises(ValueError):
        state.register_curve(FakeCurve("toy-17", p=23))  # hijacks a built-in name


# ================================================================ theme
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_apply_theme(qapp, light_theme, theme):
    app_module.apply_theme(qapp, theme)
    assert app_module.current_theme(qapp) == theme
    colors = app_module.theme_colors(theme)
    assert colors["window"] in qapp.styleSheet() and "monospace" in qapp.styleSheet()


def test_themes_define_the_same_colours():
    assert set(app_module.THEMES["light"]) == set(app_module.THEMES["dark"])
    with pytest.raises(ValueError):
        app_module.apply_theme(QApplication.instance(), "pink")


# =========================================================== MainWindow
PAGE_ORDER = ["Start here", "Overview", "Keys", "Sign", "Verify", "Curve Explorer", "Learn ECDSA",
              "Attack Demo", "History"]


def test_sidebar_lists_every_page_in_order(qtbot, state):
    window = mw.MainWindow(state)
    qtbot.addWidget(window)
    titles = [window.sidebar.item(i).data(256) for i in range(window.sidebar.count())]
    assert titles == PAGE_ORDER
    assert titles == list(window.pages) and window.stack.count() == len(PAGE_ORDER)
    assert all(not window.sidebar.item(i).icon().isNull() for i in range(len(PAGE_ORDER)))
    assert titles == list(app_state_module.PAGE_TITLES)  # go_to() knows every page


def test_sidebar_switches_the_stack(qtbot, state):
    window = mw.MainWindow(state)
    qtbot.addWidget(window)
    assert window.current_page_title() == window._start_page_title()
    window.sidebar.setCurrentRow(PAGE_ORDER.index("Curve Explorer"))
    assert window.stack.currentWidget() is window.pages["Curve Explorer"]
    window.show_page("History")
    assert window.stack.currentWidget() is window.pages["History"]
    window.show_page("Theory")  # removed: its content now lives in Learn ECDSA
    assert window.stack.currentWidget() is window.pages["History"]


def test_real_page_is_built_with_the_state_and_follows_the_curve(qtbot, state, monkeypatch):
    _install_module(monkeypatch, "fake_pages", GoodTab=FakePage)
    window = _window(qtbot, state, monkeypatch, [mw.PageSpec("Good", "fake_pages", "GoodTab", "P9", "key")])
    page = window.pages["Good"]
    assert isinstance(page, FakePage) and page.state is state and not page.property("placeholder")
    state.set_curve(K1)
    assert page.curves == [K1]  # set_curve() was called


@pytest.mark.parametrize(
    "module, class_name, expected",
    [
        ("no_such_package.no_such_module", "GhostTab", "ModuleNotFoundError"),  # file missing
        ("stub_pages", "StubTab", "AttributeError"),  # module is still a stub
    ],
)
def test_missing_or_stub_page_shows_coming_soon(qtbot, state, monkeypatch, module, class_name, expected):
    _install_module(monkeypatch, "stub_pages")  # like a skeleton file: nothing but a docstring
    window = _window(qtbot, state, monkeypatch, [mw.PageSpec("Later", module, class_name, "P9", "pen")])
    page = window.pages["Later"]
    assert isinstance(page, QLabel) and page.property("placeholder")
    assert "Coming soon" in page.text() and "P9" in page.text() and expected in page.text()


def test_page_that_needs_a_missing_teammate_module_shows_coming_soon(qtbot, state, monkeypatch):
    """`from ecdsa_edu.core.x import Y` on a stub raises ImportError: also 'coming soon'."""

    class Importing(types.ModuleType):
        def __getattr__(self, name):
            raise ImportError("cannot import name 'Curve' from 'ecdsa_edu.core.curve'")

    monkeypatch.setitem(sys.modules, "importing_pages", Importing("importing_pages"))
    window = _window(qtbot, state, monkeypatch, [mw.PageSpec("Needs P1", "importing_pages", "Tab", "P9", "pen")])
    assert window.pages["Needs P1"].property("placeholder")


def test_crashing_page_shows_coming_soon_and_prints_the_traceback(qtbot, state, monkeypatch, capsys):
    class BrokenTab(QWidget):
        def __init__(self, state):
            raise RuntimeError("page exploded")

    _install_module(monkeypatch, "fake_pages", BrokenTab=BrokenTab, GoodTab=FakePage)
    window = _window(qtbot, state, monkeypatch, [
        mw.PageSpec("Broken", "fake_pages", "BrokenTab", "P9", "warning"),
        mw.PageSpec("Good", "fake_pages", "GoodTab", "P9", "key"),
    ])
    assert "page exploded" in window.pages["Broken"].text()
    assert "page exploded" in capsys.readouterr().err  # developers still get the traceback
    assert isinstance(window.pages["Good"], FakePage)  # the other page is unaffected


def test_curve_combo_is_filled_from_the_registry(qtbot, state, monkeypatch):
    window = _window(qtbot, state, monkeypatch, [])
    combo = window.curve_combo
    texts = [combo.itemText(i) for i in range(combo.count())]
    assert texts[:3] == ["toy-17", "toy-97", "secp256k1"] and texts[-1] == "Custom curve…"
    assert combo.currentText() == "toy-17"


def test_choosing_a_curve_updates_state_pages_and_status(qtbot, state, monkeypatch):
    _install_module(monkeypatch, "fake_pages", GoodTab=FakePage)
    window = _window(qtbot, state, monkeypatch, [
        mw.PageSpec("One", "fake_pages", "GoodTab", "P9", "key"),
        mw.PageSpec("Two", "fake_pages", "GoodTab", "P9", "pen"),
    ])
    index = window.curve_combo.findText("secp256k1")
    window.curve_combo.setCurrentIndex(index)
    window.curve_combo.activated.emit(index)  # what a user click sends
    assert state.curve is K1
    assert window.pages["One"].curves == [K1] and window.pages["Two"].curves == [K1]
    assert "256-bit" in window.curve_info.text() and "secp256k1" in window.status_curve.text()


def test_state_changes_update_combo_and_status_bar(qtbot, state, monkeypatch):
    window = _window(qtbot, state, monkeypatch, [])
    assert "toy-17" in window.status_curve.text() and "no keys yet" in window.status_keys.text()
    state.set_curve(TOY97)
    assert window.curve_combo.currentText() == "toy-97" and "toy-97" in window.status_curve.text()
    state.set_keys(None, PublicKey((1, 2), TOY97))
    assert "public key only" in window.status_keys.text()
    state.set_keys(PrivateKey(3, TOY97), PublicKey((1, 2), TOY97))
    assert "key pair ready" in window.status_keys.text()
    state.set_signature(Signature(1, 2), b"m")
    assert "ready" in window.status_signature.text()


def test_window_without_any_curves(qtbot, qapp, monkeypatch):
    monkeypatch.setattr(app_state_module, "_builtin_curves", lambda: {})
    window = _window(qtbot, AppState(), monkeypatch, [])
    assert window.curve_combo.itemText(0) == "(no curves yet)"
    assert "no curves" in window.curve_info.text() and "-" in window.status_curve.text()


def test_custom_curve_entry_says_coming_soon_until_the_dialog_exists(qtbot, state, monkeypatch):
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda parent, title, text: messages.append(text))
    monkeypatch.setattr(mw, "CUSTOM_DIALOG", ("no_such_package.dialog", "CustomCurveDialog"))
    window = _window(qtbot, state, monkeypatch, [])
    index = window.curve_combo.findText("Custom curve…")
    window.curve_combo.setCurrentIndex(index)
    window.curve_combo.activated.emit(index)
    assert len(messages) == 1 and "Coming soon" in messages[0]
    assert window.curve_combo.currentText() == "toy-17" and state.curve == TOY  # nothing changed


def test_custom_curve_entry_opens_the_dialog_and_uses_its_curve(qtbot, state, monkeypatch):
    custom = FakeCurve("my-curve", p=23)

    class FakeDialog:
        def __init__(self, state, parent=None):
            pass

        def exec(self):
            return 1

        def curve(self):
            return custom

    _install_module(monkeypatch, "fake_dialog", CustomCurveDialog=FakeDialog)
    monkeypatch.setattr(mw, "CUSTOM_DIALOG", ("fake_dialog", "CustomCurveDialog"))
    window = _window(qtbot, state, monkeypatch, [])
    window.open_custom_curve_dialog()
    assert state.curve == custom and window.curve_combo.currentText() == "my-curve"
    texts = [window.curve_combo.itemText(i) for i in range(window.curve_combo.count())]
    assert texts.index("my-curve") == 3 and texts[-1] == "Custom curve…"


def test_theme_toggle(qtbot, qapp, state, monkeypatch, light_theme):
    window = _window(qtbot, state, monkeypatch, mw.PAGE_SPECS)
    window.show()
    qtbot.waitExposed(window)
    assert app_module.current_theme() == "light" and window.theme_button.text() == "Dark theme"
    window.theme_button.click()
    assert app_module.current_theme() == "dark"
    assert window.theme_button.text() == "Light theme" and window.theme_action.isChecked()
    assert app_module.theme_colors("dark")["window"] in qapp.styleSheet()
    window.theme_action.trigger()
    assert app_module.current_theme() == "light" and not window.theme_button.isChecked()
    window.toggle_theme()
    assert app_module.current_theme() == "dark"


def test_menus(qtbot, state, monkeypatch):
    window = _window(qtbot, state, monkeypatch, [])
    menus = [a.text().replace("&", "") for a in window.menuBar().actions()]
    assert menus == ["File", "View", "Help"]
    view_actions = [a.text().replace("&", "") for a in window.menuBar().actions()[1].menu().actions() if not a.isSeparator()]
    assert view_actions == ["Dark theme", "Show “Start here” at startup"]
    file_actions = [a.text().replace("&", "") for a in window.menuBar().actions()[0].menu().actions() if not a.isSeparator()]
    assert file_actions[-2:] == ["Custom curve…", "Quit"]


@pytest.mark.parametrize("name", ["home", "overview", "start", "key", "pen", "check", "curve", "learn",
                                  "warning", "book", "clock", "history", "unknown"])
def test_icons_are_drawn(qapp, name):
    icon = mw.make_icon(name, "#ffffff", "#000000")
    assert not icon.isNull()
    image = icon.pixmap(22, 22).toImage()
    assert any(image.pixelColor(x, y).alpha() > 0 for x in range(image.width()) for y in range(image.height()))



# ======================================================= go_to, settings
def test_go_to_asks_for_a_page(qtbot, state):
    with qtbot.waitSignal(state.pageRequested) as blocker:
        state.go_to("Keys")
    assert blocker.args == ["Keys"]
    with pytest.raises(ValueError):
        state.go_to("Kitchen")


def test_curve_resets_to_toy_on_restart(qapp, monkeypatch):
    monkeypatch.setattr(app_state_module, "_builtin_curves", lambda: dict(BUILTIN))
    first = AppState()
    first.set_curve(K1)
    first.settings.sync()  # write to disk now, as happens when the app closes

    second = AppState()  # like starting the app again
    assert second.curve == TOY


def test_bad_or_missing_settings_fall_back_to_defaults(qapp, monkeypatch):
    monkeypatch.setattr(app_state_module, "_builtin_curves", lambda: dict(BUILTIN))
    first = AppState()
    first.settings.setValue(app_state_module.SETTING_CURVE, "no-such-curve")
    first.settings.sync()
    second = AppState()
    assert second.curve == TOY


def test_custom_curves_are_not_remembered(qapp, monkeypatch):
    monkeypatch.setattr(app_state_module, "_builtin_curves", lambda: dict(BUILTIN))
    first = AppState()
    custom = FakeCurve("mine", p=23)
    first.register_curve(custom)
    first.set_curve(custom)
    first.settings.sync()
    assert AppState().curve == TOY


def test_curve_change_says_what_was_cleared(qtbot, state, monkeypatch):
    window = _window(qtbot, state, monkeypatch, [])
    state.set_keys(PrivateKey(7, TOY), PublicKey((0, 6), TOY))
    state.set_signature(Signature(3, 4), b"hi")
    state.set_curve(TOY97)
    assert window.statusBar().currentMessage() == "New curve toy-97: keys and signature cleared."
    state.set_curve(K1)
    assert window.statusBar().currentMessage() == "New curve: secp256k1."


def test_there_is_no_beginner_expert_switch(qtbot, state, monkeypatch):
    window = _window(qtbot, state, monkeypatch, [])
    assert not hasattr(window, "mode_button") and not hasattr(window, "mode_action")
    assert not hasattr(state, "mode") and not hasattr(state, "set_mode")
    shortcuts = [a.shortcut().toString() for menu in window.menuBar().actions() for a in menu.menu().actions()]
    assert "Ctrl+E" not in shortcuts


def test_go_to_switches_the_page(qtbot, state, monkeypatch):
    _install_module(monkeypatch, "fake_pages", GoodTab=FakePage)
    window = _window(qtbot, state, monkeypatch, [
        mw.PageSpec("Keys", "fake_pages", "GoodTab", "P2", "key"),
        mw.PageSpec("Sign", "fake_pages", "GoodTab", "P3", "pen"),
    ])
    assert window.current_page_title() == "Keys"
    state.go_to("Sign")
    assert window.current_page_title() == "Sign" and window.stack.currentWidget() is window.pages["Sign"]
    state.go_to("History")  # a real title, but not in this window: a message, no crash
    assert window.current_page_title() == "Sign" and "History" in window.statusBar().currentMessage()


def test_help_button_shows_the_pages_help(qtbot, state, monkeypatch):
    class HelpfulTab(FakePage):
        HELP = "This page does useful things."

    _install_module(monkeypatch, "fake_pages", HelpfulTab=HelpfulTab, GoodTab=FakePage)
    window = _window(qtbot, state, monkeypatch, [
        mw.PageSpec("Keys", "fake_pages", "HelpfulTab", "P2", "key"),
        mw.PageSpec("Sign", "fake_pages", "GoodTab", "P3", "pen"),
        mw.PageSpec("Verify", "no_such_package.verify", "VerifyTab", "P4", "check"),
    ])
    shown = []
    monkeypatch.setattr(mw.QMessageBox, "information", lambda parent, title, text: shown.append((title, text)))
    window.help_button.click()
    window.show_page("Sign")
    window.show_help()
    window.show_page("Verify")
    window.show_help()
    assert shown[0] == ("Help: Keys", "This page does useful things.")
    assert shown[1] == ("Help: Sign", mw.NO_HELP_TEXT)
    assert "coming soon" in shown[2][1]
    assert "F1" in window.help_button.toolTip()


def test_start_here_is_shown_first_when_it_exists(qtbot, state, monkeypatch):
    _install_module(monkeypatch, "fake_pages", GoodTab=FakePage)
    from ecdsa_edu.gui.tutorial.tutorial_tab import settings
    settings().setValue(mw.SETTING_SHOW_TUTORIAL, True)
    specs = [
        mw.PageSpec("Start here", "fake_pages", "GoodTab", "P4", "start"),
        mw.PageSpec("Keys", "fake_pages", "GoodTab", "P2", "key"),
    ]
    window = _window(qtbot, state, monkeypatch, specs)
    assert window.current_page_title() == "Start here"

    # The user turns it off (View menu): next start opens on Keys.
    window.tutorial_action.setChecked(False)
    again = _window(qtbot, AppState(settings=state.settings), monkeypatch, specs)
    assert again.current_page_title() == "Keys"


def test_session_drawer_floats_over_the_page(qtbot, state, monkeypatch):
    _install_module(monkeypatch, "fake_pages", GoodTab=FakePage)
    window = _window(qtbot, state, monkeypatch, [
        mw.PageSpec("Keys", "fake_pages", "GoodTab", "P2", "key"),
    ])
    for size in ((1024, 700), (1440, 900)):
        window.resize(*size)
        window.show()
        qtbot.waitExposed(window)
        qtbot.wait(50)  # let the layout settle after the resize
        assert not window.side_panel.isVisible()  # closed by default
        page_width = window.stack.width()

        window.session_handle.click()
        qtbot.wait(50)
        assert window.side_panel.isVisible()
        assert window.stack.width() == page_width  # it does not take width from the page
        handle = window.session_handle.geometry()
        assert window.side_panel.geometry().right() < handle.left()
        assert handle.right() <= window.surface.width()

        window.session_handle.click()
        assert not window.side_panel.isVisible()


def test_session_panel_has_no_navigation_buttons(qtbot, state, monkeypatch):
    from PySide6.QtWidgets import QPushButton
    window = _window(qtbot, state, monkeypatch, [])
    assert [b.text() for b in window.side_panel.findChildren(QPushButton)] == []


def test_window_size_is_remembered_but_fits_the_screen(qtbot, state, monkeypatch):
    from PySide6.QtCore import QSize

    window = _window(qtbot, state, monkeypatch, [])
    window.resize(1000, 700)
    window.close()  # closing saves the size
    assert state.settings.value(mw.SETTING_WINDOW_SIZE) == QSize(1000, 700)

    # The test screen may be small, so work out what the window can actually be.
    screen = QApplication.primaryScreen().availableGeometry()

    def expected(width, height):
        fitted_w = max(min(width, screen.width()), window.minimumWidth())
        fitted_h = max(min(height, screen.height()), window.minimumHeight())
        return (fitted_w, fitted_h)

    again = _window(qtbot, AppState(settings=state.settings), monkeypatch, [])
    assert (again.width(), again.height()) == expected(1000, 700)

    state.settings.setValue(mw.SETTING_WINDOW_SIZE, QSize(9000, 9000))  # bigger than any screen
    huge = _window(qtbot, AppState(settings=state.settings), monkeypatch, [])
    assert (huge.width(), huge.height()) == expected(9000, 9000)


def test_custom_curve_summary_is_friendly(qtbot, state, monkeypatch):
    custom = FakeCurve("my-curve", p=23, n=7, h=4)

    class FakeDialog:
        def __init__(self, state, parent=None):
            pass

        def exec(self):
            return 1

        def curve(self):
            return custom

    _install_module(monkeypatch, "fake_dialog", CustomCurveDialog=FakeDialog)
    monkeypatch.setattr(mw, "CUSTOM_DIALOG", ("fake_dialog", "CustomCurveDialog"))
    shown = []
    monkeypatch.setattr(mw.QMessageBox, "information", lambda parent, title, text: shown.append(text))
    window = _window(qtbot, state, monkeypatch, [])
    window.open_custom_curve_dialog()
    assert len(shown) == 1
    assert "n = 7 points in G's group" in shown[0] and "cofactor h = 4" in shown[0]
    assert "works for ECDSA" in shown[0]
