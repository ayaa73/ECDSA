"""Curve Explorer, real-numbers tab: continuous curve, zoom, pan and the note."""
from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from ecdsa_edu.gui.app_state import AppState
from ecdsa_edu.gui.tabs.curve_explorer_tab import DEFAULT_REAL_VIEW, REAL_NUMBERS_NOTE, CurveExplorerTab


@pytest.fixture
def tab(qtbot):
    widget = CurveExplorerTab(AppState())
    qtbot.addWidget(widget)
    widget.resize(900, 700)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


def _curve_vertices(tab):
    ax = tab.real_canvas.figure.axes[0]
    paths = [path for collection in ax.collections for path in getattr(collection, "get_paths", lambda: [])()]
    return [path.vertices for path in paths if len(path.vertices)]


def test_curve_is_continuous_down_to_y_zero(tab):
    """y^2 = x^3 - x + 1 crosses y = 0 at x ~ -1.3247 with a vertical tangent: the old
    sampled drawing stopped short of it. The contour reaches y = 0 from both halves."""
    vertices = np.concatenate(_curve_vertices(tab))
    root = -1.324717957
    near_root = vertices[np.abs(vertices[:, 0] - root) < 0.02]
    assert len(near_root) and np.min(np.abs(near_root[:, 1])) < 0.05
    # every drawn vertex really is on the curve (up to the grid resolution)
    x, y = vertices[:, 0], vertices[:, 1]
    assert np.max(np.abs(y**2 - (x**3 - x + 1)) / (1 + np.abs(x**3))) < 0.2


def test_zoom_buttons_and_reset(tab):
    width = DEFAULT_REAL_VIEW[1] - DEFAULT_REAL_VIEW[0]
    tab.zoom_in_button.click()
    x0, x1, *_ = tab.real_view
    assert x1 - x0 == pytest.approx(width / 1.25)
    assert tab.real_canvas.figure.axes[0].get_xlim() == pytest.approx((x0, x1))
    tab.zoom_out_button.click()
    tab.zoom_out_button.click()
    assert tab.real_view[1] - tab.real_view[0] == pytest.approx(width * 1.25)
    tab.reset_real_view()
    assert tab.real_view == DEFAULT_REAL_VIEW
    assert _curve_vertices(tab)  # the curve is redrawn for the new area


def _wheel(widget, modifiers):
    pos = QPointF(widget.width() / 2, widget.height() / 2)
    event = QWheelEvent(pos, QPointF(widget.mapToGlobal(pos.toPoint())), QPoint(), QPoint(0, 120),
                        Qt.MouseButton.NoButton, modifiers, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(widget, event)
    return event


def test_ctrl_wheel_zooms_and_plain_wheel_is_left_to_the_page(tab):
    canvas = tab.real_canvas
    event = _wheel(canvas, Qt.KeyboardModifier.NoModifier)
    assert not event.isAccepted() and tab.real_view == DEFAULT_REAL_VIEW
    event = _wheel(canvas, Qt.KeyboardModifier.ControlModifier)
    assert event.isAccepted()
    assert tab.real_view[1] - tab.real_view[0] < DEFAULT_REAL_VIEW[1] - DEFAULT_REAL_VIEW[0]


def test_zoom_keeps_the_point_under_the_mouse(tab):
    tab.zoom_real(0.5, 2.0, 3.0)
    x0, x1, y0, y1 = tab.real_view
    assert (2.0 - x0) / (x1 - x0) == pytest.approx((2.0 + 5) / 10)
    assert (3.0 - y0) / (y1 - y0) == pytest.approx((3.0 + 12) / 24)


def test_drag_pans_and_click_still_selects(tab, qtbot):
    class Event:
        def __init__(self, x, y, ax=None):
            self.x, self.y, self.inaxes, self.xdata, self.ydata = x, y, ax, None, None

    ax = tab.real_canvas.figure.axes[0]
    cx, cy = ax.bbox.x0 + ax.bbox.width / 2, ax.bbox.y0 + ax.bbox.height / 2
    tab._press_real(Event(cx, cy, ax))
    tab._drag_real(Event(cx + ax.bbox.width / 10, cy))
    tab._release_real(Event(cx + ax.bbox.width / 10, cy, ax))
    assert tab.real_view[0] == pytest.approx(DEFAULT_REAL_VIEW[0] - 1.0)  # moved left by a tenth of 10
    assert tab.real_points == []  # a drag selects nothing

    # a click (no movement) near the curve point (0, 1) selects it
    px, py = ax.transData.transform((0.0, 1.0))
    event = Event(px, py, ax)
    event.xdata, event.ydata = 0.0, 1.0
    tab._press_real(event)
    tab._release_real(event)
    assert len(tab.real_points) == 1 and tab.real_points[0] == pytest.approx((0.0, 1.0), abs=0.05)


def test_result_rounded_to_two_decimals_and_note_under_the_plot(tab):
    assert tab.real_explanation.text() == REAL_NUMBERS_NOTE
    assert "finite field with whole numbers" in REAL_NUMBERS_NOTE
    tab.real_points = [(0.0, 1.0), (1.0, 1.0)]  # on y^2 = x^3 - x + 1; P + Q = (-1, -1)
    tab._draw_real()
    text = tab.real_note.text()
    assert "P + Q = (-1.00, -1.00)" in text and "P = (0.00, 1.00)" in text
    import re
    assert all(len(decimals) == 2 for decimals in re.findall(r"\d\.(\d+)", text))


def test_fit_all_points_shows_the_whole_construction(tab):
    tab.zoom_real(0.05, 3.0, 8.0)  # zoomed far in, away from the points
    tab.real_points = [(-1.0, 1.0), (0.0, 1.0)]
    tab._draw_real()
    assert "off-screen" in tab.real_note.text()
    tab._fit_all_real()
    x0, x1, y0, y1 = tab.real_view
    assert x0 <= -1.0 and x1 >= 0.0 and y0 <= -1.0 and y1 >= 1.0
    assert "off-screen" not in tab.real_note.text()
