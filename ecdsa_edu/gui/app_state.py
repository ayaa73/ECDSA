"""Shared application state (owner: P2).

One ``AppState`` object is created at start-up and handed to every page. Pages
read the current curve / keys / last signature / mode from it and listen to its
signals, so they never need to know about each other.

Contract attributes:  .curve  .priv  .pub  .last_sig  .last_msg  .mode
Contract signals:     curveChanged(Curve)  keysChanged()  signatureChanged()
                      modeChanged(str)  pageRequested(str)

How to change the state:

    state.set_curve(curve)            # or: state.curve = curve
    state.set_keys(priv, pub)         # sets both, emits keysChanged once
    state.set_signature(sig, msg)     # sets both, emits signatureChanged once
    state.set_mode("expert")          # "beginner" (default) or "expert"
    state.go_to("Keys")               # ask the main window to show another page

Plain assignment to .priv / .pub / .last_sig / .last_msg also works, but then
the caller must emit the matching signal itself.

Remembered between runs (QSettings): the last built-in curve and the mode.
The main window also keeps the window size and the "show Start here at
startup" choice in the same settings object, ``state.settings``.

``state.curve`` is None only while P1's curve registry does not exist yet.
"""
from __future__ import annotations

import sys
import traceback
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QSettings, Signal

from ecdsa_edu.core.types import PrivateKey, PublicKey, Signature

if TYPE_CHECKING:
    from ecdsa_edu.core.curve import Curve

__all__ = ["AppState", "DEFAULT_CURVE", "DEFAULT_MODE", "MODES", "PAGE_TITLES"]

DEFAULT_CURVE = "toy-17"  # small numbers first: best for teaching
DEFAULT_MODE = "beginner"
MODES = ("beginner", "expert")

# The page titles go_to() understands (the sidebar entries in main_window.py).
PAGE_TITLES = (
    "Start here", "Overview", "Keys", "Sign", "Verify", "Curve Explorer",
    "Learn ECDSA", "Attack Demo", "Theory", "History",
)

# Names of the remembered settings.
SETTING_CURVE = "state/curve"
SETTING_MODE = "state/mode"


def _builtin_curves() -> dict[str, Curve]:
    """P1's CURVES registry, or {} while it is still a stub."""
    try:
        from ecdsa_edu.core.curves_registry import CURVES
    except ImportError:  # module or name not there yet
        return {}
    except Exception:  # the registry exists but is broken: report it, keep the app alive
        traceback.print_exc(file=sys.stderr)
        return {}
    return dict(CURVES)


def make_settings() -> QSettings:
    """The application's settings store: a small .ini file in the user's settings folder."""
    return QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "ECDSA Lab", "ECDSA Lab")


class AppState(QObject):
    """Single source of truth shared by all pages."""

    curveChanged = Signal(object)  # carries the new Curve
    keysChanged = Signal()
    signatureChanged = Signal()
    modeChanged = Signal(str)  # "beginner" or "expert"
    pageRequested = Signal(str)  # a page title, see PAGE_TITLES
    # Extra (not in the contract): the list of selectable curves changed.
    curvesListChanged = Signal()

    def __init__(
        self,
        curve: Curve | None = None,
        parent: QObject | None = None,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__(parent)
        if settings is None:
            settings = make_settings()
        self.settings = settings
        self._builtin: dict[str, Curve] = _builtin_curves()
        self.custom_curves: dict[str, Curve] = {}

        # Starting curve: the one given, else the one used last time, else toy-17.
        if curve is None:
            curve = self._remembered_curve()
        self._curve: Curve | None = curve
        if curve is not None and curve.name not in self._builtin:
            self.custom_curves[curve.name] = curve

        # Starting mode: the one used last time, else Beginner.
        saved_mode = settings.value(SETTING_MODE, DEFAULT_MODE)
        if saved_mode in MODES:
            self.mode = saved_mode
        else:
            self.mode = DEFAULT_MODE

        self.priv: PrivateKey | None = None
        self.pub: PublicKey | None = None
        self.last_sig: Signature | None = None
        self.last_msg: bytes | None = None
        # In words, what the last curve change cleared ("keys and signature"),
        # so the main window can tell the user. Empty when nothing was cleared.
        self.cleared_by_last_curve_change = ""

    def _remembered_curve(self) -> Curve | None:
        """The built-in curve saved last time, or toy-17, or None if there are no curves."""
        if not self._builtin:
            return None
        saved_name = self.settings.value(SETTING_CURVE, DEFAULT_CURVE)
        if saved_name in self._builtin:
            return self._builtin[saved_name]
        if DEFAULT_CURVE in self._builtin:
            return self._builtin[DEFAULT_CURVE]
        return next(iter(self._builtin.values()))  # the first curve in the registry

    # ------------------------------------------------------------ curve
    @property
    def curve(self) -> Curve | None:
        return self._curve

    @curve.setter
    def curve(self, curve: Curve) -> None:
        self.set_curve(curve)

    def set_curve(self, curve: Curve) -> None:
        """Switch curve. Keys and signatures belong to the old curve, so they are cleared."""
        if curve is None:
            raise ValueError("a curve is required")
        if curve == self._curve:
            return
        had_keys = self.priv is not None or self.pub is not None
        had_sig = self.last_sig is not None or self.last_msg is not None

        # Describe in words what is about to be cleared.
        if had_keys and had_sig:
            self.cleared_by_last_curve_change = "keys and signature"
        elif had_keys:
            self.cleared_by_last_curve_change = "keys"
        elif had_sig:
            self.cleared_by_last_curve_change = "signature"
        else:
            self.cleared_by_last_curve_change = ""

        # Update everything first, then notify: listeners always see a consistent state.
        self._curve = curve
        self.priv = self.pub = None
        self.last_sig = self.last_msg = None

        # Remember built-in curves for next time (custom curves are not saved).
        if curve.name in self._builtin:
            self.settings.setValue(SETTING_CURVE, curve.name)

        self.curveChanged.emit(curve)
        if had_keys:
            self.keysChanged.emit()
        if had_sig:
            self.signatureChanged.emit()

    def available_curves(self) -> dict[str, Curve]:
        """Built-in curves followed by the user's custom curves, by name."""
        result = dict(self._builtin)
        result.update(self.custom_curves)
        return result

    def register_curve(self, curve: Curve) -> None:
        """Make a custom curve selectable in the curve list."""
        builtin = self._builtin.get(curve.name)
        if builtin is not None:
            if curve != builtin:
                raise ValueError(f"'{curve.name}' is the name of a built-in curve")
            return
        if self.custom_curves.get(curve.name) == curve:
            return
        self.custom_curves[curve.name] = curve
        self.curvesListChanged.emit()

    # ------------------------------------------------------------- mode
    def set_mode(self, mode: str) -> None:
        """Switch between "beginner" and "expert". Pages listen to modeChanged."""
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}: use 'beginner' or 'expert'")
        if mode == self.mode:
            return
        self.mode = mode
        self.settings.setValue(SETTING_MODE, mode)
        self.modeChanged.emit(mode)

    def is_expert(self) -> bool:
        """Shortcut for pages: True in Expert mode."""
        return self.mode == "expert"

    # ------------------------------------------------------- navigation
    def go_to(self, page_title: str) -> None:
        """Ask the main window to show another page, e.g. go_to("Keys").

        The title must be one of PAGE_TITLES. Pages use this for buttons such as
        "You need a key first -> Go to Keys".
        """
        if page_title not in PAGE_TITLES:
            raise ValueError(f"unknown page {page_title!r}; use one of: {', '.join(PAGE_TITLES)}")
        self.pageRequested.emit(page_title)

    # ------------------------------------------------------------- keys
    def set_keys(self, priv: PrivateKey | None, pub: PublicKey | None) -> None:
        """Set the active keys. ``priv`` may be None (public key only)."""
        for key in (priv, pub):
            if key is not None and key.curve != self._curve:
                raise ValueError("this key belongs to a different curve than the active one")
        self.priv, self.pub = priv, pub
        self.keysChanged.emit()

    def clear_keys(self) -> None:
        self.set_keys(None, None)

    # -------------------------------------------------------- signature
    def set_signature(self, sig: Signature | None, msg: bytes | None) -> None:
        """Remember the most recent signature and the message it signs."""
        self.last_sig, self.last_msg = sig, msg
        self.signatureChanged.emit()
