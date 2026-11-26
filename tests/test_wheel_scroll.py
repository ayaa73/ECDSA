"""The mouse wheel scrolls the page wherever the pointer is (see widgets/wheel_scroll.py)."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QPlainTextEdit

from ecdsa_edu.gui.app_state import AppState
from ecdsa_edu.gui.main_window import MainWindow
from ecdsa_edu.gui.widgets.wheel_scroll import install_wheel_scrolling


def wheel(widget, down=True, ctrl=False):
    pos = QPointF(widget.width() / 2, widget.height() / 2)
    event = QWheelEvent(pos, QPointF(widget.mapToGlobal(pos.toPoint())), QPoint(), QPoint(0, -120 if down else 120),
                        Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(widget, event)
    return event


@pytest.fixture
def window(qtbot, qapp):
    from ecdsa_edu.gui.app import apply_theme, current_theme
    if current_theme(qapp) != "dark":
        apply_theme(qapp, "dark")
    win = MainWindow(AppState())
    qtbot.addWidget(win)
    win.resize(1024, 700)
    win.show()
    qtbot.waitExposed(win)
    return win


def test_installed_once(window, qapp):
    assert install_wheel_scrolling(qapp) is install_wheel_scrolling(qapp)


def test_wheel_over_a_closed_drop_down_scrolls_the_page_not_the_value(window, qtbot):
    window.show_page("Sign")
    page = window.pages["Sign"]
    combo, bar = page.hash_combo, page.page_scroll.verticalScrollBar()
    qtbot.wait(20)
    assert bar.maximum() > 0
    bar.setValue(0)
    before = combo.currentIndex()
    wheel(combo)
    assert combo.currentIndex() == before and bar.value() > 0


def test_wheel_over_a_full_text_box_scrolls_the_page(window, qtbot):
    window.show_page("Verify")
    page = window.pages["Verify"]
    bar = page.page_scroll.verticalScrollBar()
    qtbot.wait(20)
    bar.setValue(0)
    wheel(page.msg_edit.viewport())  # short text: the box itself cannot scroll
    assert bar.value() > 0


def test_a_box_that_can_scroll_still_scrolls_itself(window, qtbot):
    window.show_page("Verify")
    page = window.pages["Verify"]
    page.msg_edit.setPlainText("\n".join(f"line {i}" for i in range(200)))
    qtbot.wait(20)
    inner, outer = page.msg_edit.verticalScrollBar(), page.page_scroll.verticalScrollBar()
    outer.setValue(0)
    wheel(page.msg_edit.viewport())
    assert inner.value() > 0 and outer.value() == 0


def test_wheel_over_plots_scrolls_and_ctrl_wheel_zooms(window, qtbot):
    window.show_page("Curve Explorer")
    explorer = window.pages["Curve Explorer"]
    window.resize(1024, 640)
    qtbot.wait(30)
    scroll = explorer.views.currentWidget()
    bar = scroll.verticalScrollBar()
    assert bar.maximum() > 0
    bar.setValue(0)
    view = explorer.real_view
    wheel(explorer.real_canvas)
    assert bar.value() > 0 and explorer.real_view == view  # page scrolled, no zoom
    bar.setValue(0)
    wheel(explorer.real_canvas, ctrl=True)
    assert bar.value() == 0 and explorer.real_view != view  # zoomed, page did not move


def test_wheel_over_the_learn_reading_scrolls_the_step(window, qtbot):
    window.show_page("Learn ECDSA")
    learn = window.pages["Learn ECDSA"]
    page = learn.pages[0]
    page.reading_toggle.click()
    qtbot.wait(30)
    bar = learn._page_scrolls[page].verticalScrollBar()
    bar.setValue(bar.maximum() // 2)
    start = bar.value()
    wheel(page.reading_view.viewport())
    assert bar.value() > start


def test_a_focused_value_widget_keeps_the_wheel(window, qtbot):
    window.show_page("Curve Explorer")
    spin = window.pages["Curve Explorer"].a
    spin.setFocus()
    qtbot.waitUntil(spin.hasFocus, timeout=2000)
    before = spin.value()
    wheel(spin, down=False)
    assert spin.value() != before  # the user clicked into it: the wheel changes it on purpose
