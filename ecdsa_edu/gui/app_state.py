"""Shared application state (owner: P2).

One ``AppState`` object is created at start-up and handed to every page. Pages
read the current curve / keys / last signature from it and listen to its
signals, so they never need to know about each other.

Contract attributes:  .curve  .priv  .pub  .last_sig  .last_msg
Contract signals:     curveChanged(Curve)  keysChanged()  signatureChanged()

How to change the state (pick one style per update):

    state.set_curve(curve)            # or: state.curve = curve
    state.set_keys(priv, pub)         # sets both, emits keysChanged once
    state.set_signature(sig, msg)     # sets both, emits signatureChanged once

Plain assignment to .priv / .pub / .last_sig / .last_msg also works, but then
the caller must emit the matching signal itself.

``state.curve`` is None only while P1's curve registry does not exist yet.
"""
from __future__ import annotations

import sys
import traceback
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from ecdsa_edu.core.types import PrivateKey, PublicKey, Signature

if TYPE_CHECKING:
    from ecdsa_edu.core.curve import Curve

__all__ = ["AppState", "DEFAULT_CURVE"]

DEFAULT_CURVE = "toy-17"  # small numbers first: best for teaching


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


class AppState(QObject):
    """Single source of truth shared by all pages."""

    curveChanged = Signal(object)  # carries the new Curve
    keysChanged = Signal()
    signatureChanged = Signal()
    # Extra (not in the contract): the list of selectable curves changed.
    curvesListChanged = Signal()

    def __init__(self, curve: Curve | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._builtin: dict[str, Curve] = _builtin_curves()
        self.custom_curves: dict[str, Curve] = {}
        if curve is None and self._builtin:
            curve = self._builtin.get(DEFAULT_CURVE) or next(iter(self._builtin.values()))
        self._curve: Curve | None = curve
        self.priv: PrivateKey | None = None
        self.pub: PublicKey | None = None
        self.last_sig: Signature | None = None
        self.last_msg: bytes | None = None
        if curve is not None and curve.name not in self._builtin:
            self.custom_curves[curve.name] = curve

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
        # Update everything first, then notify: listeners always see a consistent state.
        self._curve = curve
        self.priv = self.pub = None
        self.last_sig = self.last_msg = None
        self.curveChanged.emit(curve)
        if had_keys:
            self.keysChanged.emit()
        if had_sig:
            self.signatureChanged.emit()

    def available_curves(self) -> dict[str, Curve]:
        """Built-in curves followed by the user's custom curves, by name."""
        return {**self._builtin, **self.custom_curves}

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
