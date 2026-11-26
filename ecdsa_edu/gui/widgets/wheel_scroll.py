"""Mouse-wheel scrolling that always reaches the page (installed once for the app).

Without this, the wheel only scrolls a page when the pointer happens to be
over plain background. Many widgets catch it first:

* plots, closed drop-down lists, number boxes, sliders and tab bars use the
  wheel to zoom or to change their value (a silent, accidental change);
* a small text box or list that cannot scroll any further swallows it.

``WheelRouter`` works like a web browser ("scroll chaining"): if the widget
under the pointer can really scroll in that direction, it scrolls; otherwise
the nearest page around it that can scroll does. Value widgets only take the
wheel while they have keyboard focus. Ctrl + wheel is never touched, so the
Curve Explorer can use it to zoom.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QAbstractScrollArea, QAbstractSlider, QAbstractSpinBox, QApplication, QComboBox, QScrollBar, QTabBar,
    QWidget,
)
from PySide6.QtCore import Qt

__all__ = ["WheelRouter", "install_wheel_scrolling"]


def _is_value_widget(widget: QWidget) -> bool:
    """Widgets that would change a value (or zoom) when the wheel turns over them."""
    if isinstance(widget, QScrollBar):
        return False
    if isinstance(widget, (QComboBox, QAbstractSpinBox, QAbstractSlider, QTabBar)):
        return True
    return any(cls.__name__.startswith("FigureCanvas") for cls in type(widget).__mro__)  # matplotlib plots


def _can_scroll(area: QAbstractScrollArea, delta: int) -> bool:
    bar = area.verticalScrollBar()
    if bar.maximum() <= bar.minimum() or not area.isVisible():
        return False
    return bar.value() > bar.minimum() if delta > 0 else bar.value() < bar.maximum()


def _scroll_areas_around(widget: QWidget) -> list[QAbstractScrollArea]:
    """Scroll areas whose content contains ``widget``, innermost first."""
    areas = []
    child, parent = widget, widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QAbstractScrollArea) and child is parent.viewport():
            areas.append(parent)
        child, parent = parent, parent.parentWidget()
    if isinstance(widget, QAbstractScrollArea):  # the wheel arrived at a scroll area itself
        areas.insert(0, widget)
    return areas


class WheelRouter(QObject):
    """Application-wide event filter; see the module docstring."""

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt naming)
        if event.type() != QEvent.Type.Wheel or not isinstance(obj, QWidget) or not isinstance(event, QWheelEvent):
            return False
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            return False  # Ctrl + wheel: zoom, leave it alone
        delta = event.angleDelta().y() or event.pixelDelta().y()
        if delta == 0 or abs(event.angleDelta().x()) > abs(event.angleDelta().y()):
            return False  # sideways scrolling: leave it alone
        popup = QApplication.activePopupWidget()
        if popup is not None and (popup is obj or popup.isAncestorOf(obj)):
            return False  # an open drop-down list scrolls itself

        # A value widget under the pointer (or one of its parts): it only takes the
        # wheel while it has keyboard focus, i.e. after the user clicked into it.
        widget = obj
        while widget is not None and not isinstance(widget, QAbstractScrollArea):
            if _is_value_widget(widget):
                return False if widget.hasFocus() else self._scroll_page(widget, event, delta)
            widget = widget.parentWidget()

        areas = _scroll_areas_around(obj)
        if not areas or _can_scroll(areas[0], delta):
            return False  # the normal case: the innermost area scrolls
        return self._scroll_page(areas[0], event, delta)

    @staticmethod
    def _scroll_page(start: QWidget, event: QWheelEvent, delta: int) -> bool:
        """Scroll the nearest area around ``start`` that can still move; True = event used up."""
        for area in _scroll_areas_around(start):
            if area is start or not _can_scroll(area, delta):
                continue
            bar = area.verticalScrollBar()
            pixels = event.pixelDelta().y()
            if pixels:
                bar.setValue(bar.value() - pixels)  # touchpads report exact pixels
            else:
                steps = event.angleDelta().y() / 120 * QApplication.wheelScrollLines()
                bar.setValue(bar.value() - round(steps * bar.singleStep()))
            break
        event.accept()
        return True  # used up: never let it change a value by accident


def install_wheel_scrolling(app: QApplication | None = None) -> WheelRouter:
    """Install the router once per application (calling it again changes nothing)."""
    app = app or QApplication.instance()
    router = getattr(app, "_wheel_router", None)
    if router is None:
        router = WheelRouter(app)
        app.installEventFilter(router)
        app._wheel_router = router  # keep it alive and make the install idempotent
    return router
