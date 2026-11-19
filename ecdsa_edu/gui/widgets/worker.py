"""Run slow core calls off the GUI thread (owner: P2).

    run_in_background(sign, priv, msg, on_done=self._show, on_error=self._fail)

``fn(*args)`` runs on a QThreadPool thread. Exactly one callback is then called
**on the GUI thread**: ``on_done(result)`` or ``on_error(exception)``.

Errors never crash the app. When ``fn`` raises:

* ``on_error(exc)`` is called first, so the page can re-enable its buttons;
* then a friendly message box is shown: the text of a ``ValueError`` as it is
  (core functions use ValueError for "your input is wrong"), a generic
  "unexpected error" text for anything else (the traceback goes to the console).
* A page that shows the error itself (e.g. in a label) returns ``True`` from
  ``on_error`` to say "handled" - then no message box appears.

Busy indicator: while at least one job runs, the mouse cursor is a "busy"
cursor and ``busy_tracker().busyChanged(bool)`` is emitted, which the main
window uses for the progress bar in its status bar.

Rules for callers:
* call run_in_background from the GUI thread;
* ``fn`` must be pure core code - it must not touch any widget;
* a ``trace`` list passed in ``args`` is safe to read inside ``on_done``.
"""
from __future__ import annotations

import sys
import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

__all__ = ["run_in_background", "busy_tracker", "show_error", "friendly_message"]


# --------------------------------------------------------------------------
# Busy indicator
# --------------------------------------------------------------------------
class BusyTracker(QObject):
    """Counts running jobs; shows a busy cursor and announces busy / idle."""

    busyChanged = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._running = 0

    def is_busy(self) -> bool:
        return self._running > 0

    def _started(self) -> None:
        self._running += 1
        if self._running == 1:
            QGuiApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
            self.busyChanged.emit(True)

    def _finished(self) -> None:
        self._running -= 1
        if self._running == 0:
            QGuiApplication.restoreOverrideCursor()
            self.busyChanged.emit(False)


_tracker: BusyTracker | None = None


def busy_tracker() -> BusyTracker:
    """The application-wide busy tracker (created on first use)."""
    global _tracker
    if _tracker is None:
        _tracker = BusyTracker()
    return _tracker


# --------------------------------------------------------------------------
# Friendly error reporting
# --------------------------------------------------------------------------
def friendly_message(exc: BaseException) -> tuple[str, str]:
    """(title, text) suitable for showing ``exc`` to a student."""
    if isinstance(exc, ValueError):
        text = str(exc).strip() or "The input is not valid."
        return "Please check your input", text[:1].upper() + text[1:]
    if isinstance(exc, OSError):
        return "File problem", exc.strerror or str(exc) or "The file could not be read or written."
    return (
        "Unexpected error",
        f"Something went wrong inside the program ({type(exc).__name__}: {exc}).\n\n"
        "This is a bug, not your mistake. Details were printed to the console.",
    )


def show_error(exc: BaseException, parent=None) -> None:
    """Show ``exc`` in a friendly message box (GUI thread only)."""
    title, text = friendly_message(exc)
    icon = QMessageBox.Icon.Warning if isinstance(exc, (ValueError, OSError)) else QMessageBox.Icon.Critical
    box = QMessageBox(icon, title, text, QMessageBox.StandardButton.Ok, parent or QApplication.activeWindow())
    box.exec()


# --------------------------------------------------------------------------
# The worker
# --------------------------------------------------------------------------
class _Relay(QObject):
    """Lives on the GUI thread and hands the worker's result to the callbacks.

    The worker thread only *emits* a signal. Because the connections are queued
    and this object belongs to the GUI thread, the slots below run on the GUI
    thread, where touching widgets is allowed.
    """

    done = Signal(object)
    failed = Signal(object)

    def __init__(self, on_done: Callable[[Any], Any], on_error: Callable[[Exception], Any]) -> None:
        super().__init__()
        self._on_done, self._on_error = on_done, on_error
        self.done.connect(self._deliver_done, Qt.ConnectionType.QueuedConnection)
        self.failed.connect(self._deliver_error, Qt.ConnectionType.QueuedConnection)

    def _release(self) -> None:
        _ACTIVE.discard(self)
        busy_tracker()._finished()

    @Slot(object)
    def _deliver_done(self, result: Any) -> None:
        self._release()
        try:
            self._on_done(result)
        except Exception as exc:  # a bug in the callback must not take the app down
            traceback.print_exc(file=sys.stderr)
            show_error(exc)

    @Slot(object)
    def _deliver_error(self, exc: Exception) -> None:
        self._release()
        if not isinstance(exc, (ValueError, OSError)):
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
        try:
            handled = self._on_error(exc) is True
        except Exception as callback_exc:
            traceback.print_exc(file=sys.stderr)
            exc, handled = callback_exc, False
        if not handled:
            show_error(exc)


class _Job(QRunnable):
    def __init__(self, fn: Callable[..., Any], args: tuple, relay: _Relay) -> None:
        super().__init__()
        self._fn, self._args, self._relay = fn, args, relay

    def run(self) -> None:  # executed on a pool thread
        try:
            result = self._fn(*self._args)
        except Exception as exc:  # report every failure to the GUI thread instead of dying silently
            signal, payload = self._relay.failed, exc
        else:
            signal, payload = self._relay.done, result
        try:
            signal.emit(payload)
        except RuntimeError:
            pass  # the application was closed while the job was still running


# Relays of running jobs. Keeping a reference here stops Python from
# garbage-collecting a relay before its result has been delivered.
_ACTIVE: set[_Relay] = set()


def run_in_background(
    fn: Callable[..., Any],
    *args: Any,
    on_done: Callable[[Any], Any],
    on_error: Callable[[Exception], Any],
) -> None:
    """Run ``fn(*args)`` in the background; report back on the GUI thread.

    ``on_error`` may return ``True`` to say it has shown the error itself;
    otherwise a friendly message box is shown after it returns.
    """
    relay = _Relay(on_done, on_error)
    _ACTIVE.add(relay)
    busy_tracker()._started()
    QThreadPool.globalInstance().start(_Job(fn, args, relay))
