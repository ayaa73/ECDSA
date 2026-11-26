"""The "Keys" page (owner: P2).

Lets a student
  1. pick a private key d (typed, or random with Ctrl+G),
  2. see the public key Q = d * G as coordinates and in both hex encodings,
  3. watch below how Q was computed, step by step,
  4. save / load key files and import somebody else's public key.

While the private key is on screen a warning is shown; "Hide d" masks it.

Beginner and Expert mode (the toolbar switch, Ctrl+E):
  Beginner - one big "Generate my key pair" button, d hidden by default,
             only the compressed public key, Save/Load buttons. The math is
             one click away ("See how Q was computed").
  Expert   - type your own d, both encodings, hexadecimal switch, importing
             someone else's public key and the full step-by-step trace.
The resulting keys are stored in the shared AppState (state.priv, state.pub),
which emits keysChanged so the Sign and Verify pages pick them up.

This file contains no cryptographic math: every computation is a call into
``ecdsa_edu.core`` (run on a background thread), and the returned trace is
handed to the TraceViewer.
"""
from __future__ import annotations

import html
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from ecdsa_edu.core.curve import Curve
from ecdsa_edu.core.key_io import (
    load_private_key,
    load_public_key,
    point_from_hex,
    point_to_hex,
    save_private_key,
    save_public_key,
)
from ecdsa_edu.core.keys import generate_keypair, public_from_private, validate_public_point
from ecdsa_edu.core.trace import Trace
from ecdsa_edu.core.types import PrivateKey, PublicKey
from ecdsa_edu.gui.app_state import AppState
from ecdsa_edu.gui.widgets.bigint_field import BigIntField
from ecdsa_edu.gui.widgets.key_derivation import MANUAL_KEY_NOTE, KeyDerivation
from ecdsa_edu.gui.widgets.hex_field import HexField, HexOutputField
from ecdsa_edu.gui.widgets.worker import run_in_background
from ecdsa_edu.gui.widgets.cards import Card, make_page_header

__all__ = ["KeysTab", "make_trace_view", "set_message"]

_KEY_FILTER = "Key files (*.json);;All files (*)"


def set_message(label: QLabel, text: str, kind: str = "info", *, rich: bool = False) -> None:
    """Show ``text`` in ``label``, coloured by the theme: kind = "info" | "ok" | "warning" | "error"."""
    label.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
    label.setText(text)
    if label.property("kind") != kind:
        label.setProperty("kind", kind)  # the app stylesheet colours QLabel[kind=...]
        label.style().unpolish(label)
        label.style().polish(label)


# --------------------------------------------------------------------------
# Trace display
# --------------------------------------------------------------------------
class _PlainTraceView(QPlainTextEdit):
    """Bare-bones stand-in used only while P3's TraceViewer is not available."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)

    def set_trace(self, trace: Trace) -> None:
        lines: list[str] = []
        for number, step in enumerate(trace, start=1):
            lines.append(f"{number}. {step.title}")
            lines.append(f"     {step.formula}")
            lines.extend(f"       {name} = {value}" for name, value in step.values.items())
            lines.append("")
        self.setPlainText("\n".join(lines))


def make_trace_view() -> QWidget:
    """Return P3's TraceViewer, or a plain-text fallback if it is not merged yet."""
    try:
        from ecdsa_edu.gui.widgets.trace_viewer import TraceViewer
    except ImportError:
        return _PlainTraceView()
    return TraceViewer()


# --------------------------------------------------------------------------
# Background jobs: plain functions that only call core code
# --------------------------------------------------------------------------
def _decode_public(curve: Curve, text: str) -> PublicKey:
    Q = point_from_hex(curve, text)
    validate_public_point(curve, Q)
    return PublicKey(Q, curve)


def _load_private_with_public(path: str, trace: Trace) -> tuple[PrivateKey, PublicKey]:
    priv = load_private_key(path)
    return priv, public_from_private(priv, trace)


# --------------------------------------------------------------------------
# The tab
# --------------------------------------------------------------------------
class KeysTab(QWidget):
    """Generate, inspect, import and store ECDSA keys."""

    # Shown by the toolbar "?" button.
    HELP = (
        "This page makes Alice's key pair. Press “Generate key pair” (Ctrl+G): the app picks a "
        "secret number d at random and computes the public point Q = d · G. In real use, d should "
        "always be chosen randomly. The Learn ECDSA walkthrough also lets you enter d yourself as "
        "a learning feature, so you can follow a worked example.\n\n"
        "Keep d secret: anyone who has it can sign as you. Q is safe to share; others use it to "
        "check your signatures.\n\n"
        "You can save both keys as small files, load them later, or paste somebody else's "
        "public key to verify their signatures (Expert mode).\n\n"
        "Beginner mode keeps the page simple: d is hidden and only the short (compressed) public "
        "key is shown. Expert mode (Ctrl+E) lets you type your own d and shows every step of the math."
    )

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._curve: Curve = state.curve
        self._job = 0  # id of the newest background job; results of older jobs are dropped
        self._busy = False
        self._trace: Trace = []  # steps of the last computation
        self._shown_trace: Trace | None = None  # what the trace view currently displays
        self._build_ui()
        state.keysChanged.connect(self.refresh)
        self.set_curve(state.curve)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        self.curve_label = QLabel()
        self.curve_label.setTextFormat(Qt.TextFormat.RichText)
        self.curve_label.setWordWrap(True)
        self.hex_check = QCheckBox("Show numbers in hexadecimal")
        self.hex_check.setToolTip("Switch d, Qx and Qy between decimal and hexadecimal")
        header = QHBoxLayout()
        header.addWidget(self.curve_label, 1)
        header.addWidget(self.hex_check)

        # --- 1. private key
        self.d_field = BigIntField(minimum=1)
        self.d_field.setAccessibleName("Private key d")
        self.hide_check = QCheckBox("Hide d")
        self.hide_check.setToolTip("Mask the private key on screen (and the steps below, which contain it)")
        self.warning = QLabel("⚠  Your private key is visible. Anyone who sees it can sign as you.")
        self.warning.setWordWrap(True)
        self.warning.setProperty("kind", "warning")
        self.hidden_note = QLabel("🔒  d is hidden. Never show it to anyone: whoever has it can sign as you.")
        self.hidden_note.setWordWrap(True)
        self.hidden_note.setProperty("note", True)
        self.d_hint = QLabel()
        self.d_hint.setWordWrap(True)
        self.btn_generate = QPushButton("Generate key pair")
        self.btn_generate.setProperty("primary", True)
        self.btn_generate.setShortcut(QKeySequence("Ctrl+G"))
        self.btn_generate.setToolTip("Pick a random private key and compute its public key (Ctrl+G)")
        self.d_note = _note("")
        self.btn_derive = QPushButton("Compute Q from this d")
        self.btn_derive.setToolTip("Build the key pair for the number typed above (Enter)")
        buttons = QVBoxLayout()
        buttons.addWidget(self.btn_generate)
        buttons.addWidget(self.btn_derive)
        buttons.addWidget(self.hide_check)
        self.key_diagram = KeyDerivation(
            self.d_field, buttons, self.d_note, self.warning, self.hidden_note, self.d_hint
        )
        self.key_diagram.theoryRequested.connect(lambda: self._state.go_to("Theory"))

        # --- 2. public key
        box_pub = Card("Public key Q = d · G", "peach", "2")
        self.qx_field = BigIntField(read_only=True)
        self.qy_field = BigIntField(read_only=True)
        self.compressed_field = HexOutputField(lines=3, save_name="public_key_compressed")
        self.uncompressed_field = HexOutputField(lines=5, save_name="public_key_uncompressed")
        form = QFormLayout()
        box_pub.body.addLayout(form)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.addRow("Qx", self.qx_field)
        form.addRow("Qy", self.qy_field)
        form.addRow("Compressed", self.compressed_field)
        form.addRow("Uncompressed", self.uncompressed_field)
        self.encoding_note = _note("")
        form.addRow("", self.encoding_note)
        # Beginner mode: a shortcut to the math, instead of the full trace below.
        self.btn_show_math = QPushButton("See how Q was computed  →")
        self.btn_show_math.setToolTip("Switch to Expert mode and show every step of Q = d · G")
        form.addRow("", self.btn_show_math)
        self._pub_form = form

        # --- key files
        box_files = Card("Key files", "lavender")
        self.btn_save_priv = QPushButton("Save private key…")
        self.btn_save_pub = QPushButton("Save public key…")
        self.btn_load_priv = QPushButton("Load private key…")
        self.btn_load_pub = QPushButton("Load public key…")
        grid = QGridLayout()
        box_files.body.addLayout(grid)
        grid.addWidget(self.btn_save_priv, 0, 0)
        grid.addWidget(self.btn_save_pub, 0, 1)
        grid.addWidget(self.btn_load_priv, 1, 0)
        grid.addWidget(self.btn_load_pub, 1, 1)
        grid.addWidget(_note("Small JSON files. Private-key files are not encrypted."), 2, 0, 1, 2)

        # --- import
        box_import = Card("Use someone else's public key", "pink")
        self.import_field = HexField(lines=2)
        self.import_field.setAccessibleName("Public key hex to import")
        self.btn_import = QPushButton("Use this public key")
        row = QHBoxLayout()
        row.addWidget(self.btn_import)
        row.addStretch(1)
        lay = box_import.body
        lay.addWidget(_note("Paste a compressed or uncompressed public key (hex) to verify that person's signatures."))
        lay.addWidget(self.import_field)
        lay.addLayout(row)

        self.status = QLabel()
        self.status.setWordWrap(True)
        # Shown after a curve change cleared the keys: one click makes new ones.
        self.btn_regenerate = QPushButton("Generate new keys")
        self.btn_regenerate.setVisible(False)
        status_row = QHBoxLayout()
        status_row.addWidget(self.status, 1)
        status_row.addWidget(self.btn_regenerate)
        self._box_import = box_import

        # Put secondary controls below the shared simulator, using the dashboard cards.
        details = QWidget()
        self._details = details
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.addLayout(header)
        details_layout.addWidget(box_pub)
        details_layout.addWidget(box_files)
        details_layout.addWidget(box_import)
        box_trace = Card("How Q = d · G was computed", "white")
        self._box_trace = box_trace
        self.trace_note = _note("")
        self.trace_view = make_trace_view()
        box_trace.body.addWidget(self.trace_note)
        box_trace.body.addWidget(self.trace_view, 1)
        details_layout.addWidget(box_trace)
        details.hide()

        self.details_button = QPushButton("Show key details")
        self.details_button.setCheckable(True)
        self.details_button.toggled.connect(self._toggle_details)
        top = QWidget()
        top_lay = QVBoxLayout(top)
        top_lay.addWidget(make_page_header("Your keys", "Create a private key and share its matching public key."))
        top_lay.addLayout(status_row)
        top_lay.addWidget(self.key_diagram)
        top_lay.addWidget(self.details_button, alignment=Qt.AlignmentFlag.AlignLeft)
        top_lay.addWidget(details)
        top_lay.addStretch(1)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setWidget(top)
        if hasattr(self.trace_view, "use_page_scrolling"):
            # The full Keys page scrolls already, so the trace can grow with it.
            self.trace_view.use_page_scrolling(self._scroll)
        outer = QVBoxLayout(self)
        outer.addWidget(self._scroll)

        # --- wiring
        self.btn_generate.clicked.connect(self.generate)
        self.btn_derive.clicked.connect(self.derive)
        self.d_field.returnPressed.connect(self.derive)
        self.d_field.textChanged.connect(self._update_controls)
        self.import_field.valueChanged.connect(self._update_controls)
        self.btn_import.clicked.connect(self.import_public_hex)
        self.btn_save_priv.clicked.connect(self.save_private_key_dialog)
        self.btn_save_pub.clicked.connect(self.save_public_key_dialog)
        self.btn_load_priv.clicked.connect(self.load_private_key_dialog)
        self.btn_load_pub.clicked.connect(self.load_public_key_dialog)
        self.hex_check.toggled.connect(self._set_hex)
        self.hide_check.toggled.connect(self._apply_privacy)
        self.btn_regenerate.clicked.connect(self.generate)
        self.btn_show_math.clicked.connect(self._open_trace)
        self._state.modeChanged.connect(self.apply_mode)
        self.apply_mode()

    # ------------------------------------------------------ beginner / expert
    def apply_mode(self, _mode: str = "") -> None:
        """Show the simple page (Beginner) or every option (Expert)."""
        expert = self._state.mode == "expert"
        self.btn_generate.setText("Generate key pair" if expert else "Generate my key pair")
        self.btn_generate.setProperty("big", not expert)
        self.btn_generate.style().unpolish(self.btn_generate)
        self.btn_generate.style().polish(self.btn_generate)
        # Typing your own d is an Expert feature.
        self.d_field.setReadOnly(not expert)
        self.btn_derive.setVisible(expert)
        if expert:
            self.d_note.setText(MANUAL_KEY_NOTE)
        else:
            self.d_note.setText("The app picks a random secret number for you, as it should be in real use. "
                                "(Expert mode, Ctrl+E, lets you type your own.)")
            self.hide_check.setChecked(True)  # Beginner: d is hidden by default
        # Beginner sees only the compressed public key.
        self._pub_form.setRowVisible(self.uncompressed_field, expert)
        if expert:
            self.encoding_note.setText("Compressed = 02/03 + Qx (the prefix tells whether Qy is even or odd). "
                                       "Uncompressed = 04 + Qx + Qy.")
        else:
            self.encoding_note.setText("This short text is your public key: share it so others can check "
                                       "your signatures.")
        self.hex_check.setVisible(expert)
        self._box_import.setVisible(expert)
        self._box_trace.setVisible(expert)
        self._pub_form.setRowVisible(self.btn_show_math, not expert)
        self._update_controls()

    def _toggle_details(self, visible: bool) -> None:
        self._details.setVisible(visible)
        self.details_button.setText("Hide key details" if visible else "Show key details")
        self._apply_privacy()

    def _open_trace(self) -> None:
        self._state.set_mode("expert")
        self.details_button.setChecked(True)
        QTimer.singleShot(0, self, lambda: self._scroll.ensureWidgetVisible(self._box_trace))

    # ------------------------------------------------------- tab contract
    def set_curve(self, curve: Curve) -> None:
        """Switch the page to ``curve`` (called whenever the active curve changes).

        Keys of another curve are useless on this one, so they are cleared - with a notice.
        """
        old_curve = self._curve
        showed_keys = bool(self.d_field.text().strip() or self.qx_field.text())
        self._curve = curve
        self._job += 1  # anything still running was for the old curve
        self._busy = False
        # Normally AppState has already dropped the old keys; make sure of it.
        stale = [k for k in (self._state.priv, self._state.pub) if k is not None and k.curve != curve]
        if stale:
            self._state.clear_keys()
        bits = curve.n.bit_length()
        order = f"order n = {curve.n}" if bits <= 64 else f"a {bits}-bit order n"
        self.curve_label.setText(
            f"<b>Curve {html.escape(curve.name)}</b> &nbsp;·&nbsp; base point G has {order}. "
            "A key pair is a secret number <b>d</b> and the point <b>Q = d · G</b>."
        )
        self.d_field.set_range(1, curve.n - 1)
        self.d_field.set_value(None)
        self.import_field.set_hex("")
        self._show_trace([])
        use_hex = curve.p.bit_length() > 32  # decimal reads best on toy curves
        if self.hex_check.isChecked() == use_hex:
            self._set_hex(use_hex)
        else:
            self.hex_check.setChecked(use_hex)  # triggers _set_hex
        if showed_keys and old_curve is not None and old_curve != curve:
            self._set_status(
                f"The curve changed to {curve.name}. The keys shown before belonged to "
                f"{old_curve.name} and were cleared - generate or load new ones.",
                "warning",
            )
            self.btn_regenerate.setVisible(True)
        else:
            self._set_status("")
        self.refresh()

    def refresh(self) -> None:
        """Re-read the keys from the shared state and show them."""
        priv, pub = self._keys()
        if priv is not None:
            self.d_field.set_value(priv.d)
        elif pub is not None:
            self.d_field.set_value(None)  # public key only: d is unknown
        if pub is not None:
            self.qx_field.set_value(pub.Q[0])
            self.qy_field.set_value(pub.Q[1])
            self.compressed_field.set_hex(point_to_hex(self._curve, pub.Q, compressed=True))
            self.uncompressed_field.set_hex(point_to_hex(self._curve, pub.Q, compressed=False))
        else:
            self.qx_field.set_value(None)
            self.qy_field.set_value(None)
            self.compressed_field.set_hex("")
            self.uncompressed_field.set_hex("")
        self._update_controls()

    # ------------------------------------------------------------ actions
    def generate(self) -> None:
        """Create a random key pair on the current curve."""
        trace: Trace = []
        self._run(
            "Generating a key pair…",
            generate_keypair, self._curve, trace,
            on_result=lambda keys: self._adopt(keys[0], keys[1], trace, "New key pair generated."),
        )

    def derive(self) -> None:
        """Compute the public key for the d typed by the user."""
        d = self.d_field.value()
        if d is None:
            self._set_status(self.d_field.error() or "Type a private key d first.", "error")
            return
        priv = PrivateKey(d, self._curve)
        trace: Trace = []
        self._run(
            "Computing Q = d · G…",
            public_from_private, priv, trace,
            on_result=lambda pub: self._adopt(priv, pub, trace, "Public key computed from your d."),
        )

    def import_public_hex(self) -> None:
        """Use the pasted hex string as the active public key (no private key)."""
        text = self.import_field.hex_value()
        if not text:
            self._set_status(self.import_field.error() or "Paste a public key in hex first.", "error")
            return
        self._run(
            "Checking the public key…",
            _decode_public, self._curve, text,
            on_result=lambda pub: self._adopt(None, pub, [], "Public key imported (no private key)."),
        )

    def save_private_key_dialog(self) -> None:
        priv, _ = self._keys()
        if priv is None:
            self._set_status("There is no private key to save.", "error")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save private key", f"{self._curve.name}_private.json", _KEY_FILTER
        )
        if not path:
            return
        try:
            save_private_key(path, priv)
        except (OSError, ValueError) as exc:
            self._alert("Could not save the private key", str(exc))
        else:
            self._set_status(f"Private key saved to {path}. The file is not encrypted - keep it safe.", "ok")

    def save_public_key_dialog(self) -> None:
        _, pub = self._keys()
        if pub is None:
            self._set_status("There is no public key to save.", "error")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save public key", f"{self._curve.name}_public.json", _KEY_FILTER
        )
        if not path:
            return
        try:
            save_public_key(path, pub)
        except (OSError, ValueError) as exc:
            self._alert("Could not save the public key", str(exc))
        else:
            self._set_status(f"Public key saved to {path}.", "ok")

    def load_private_key_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load private key", "", _KEY_FILTER)
        if not path:
            return
        trace: Trace = []
        self._run(
            "Loading the private key…",
            _load_private_with_public, path, trace,
            on_result=lambda keys: self._adopt(keys[0], keys[1], trace, "Private key loaded."),
            alert_title="Could not load the private key",
        )

    def load_public_key_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load public key", "", _KEY_FILTER)
        if not path:
            return
        self._run(
            "Loading the public key…",
            load_public_key, path,
            on_result=lambda pub: self._adopt(None, pub, [], "Public key loaded (no private key)."),
            alert_title="Could not load the public key",
        )

    # ---------------------------------------------------------- internals
    def _keys(self) -> tuple[PrivateKey | None, PublicKey | None]:
        """The state's keys, but only if they belong to the curve this tab shows."""
        priv, pub = self._state.priv, self._state.pub
        if priv is not None and priv.curve != self._curve:
            priv = None
        if pub is not None and pub.curve != self._curve:
            pub = None
        return priv, pub

    def _run(
        self,
        message: str,
        fn: Callable[..., Any],
        *args: Any,
        on_result: Callable[[Any], None],
        alert_title: str | None = None,
    ) -> None:
        """Run a core call in the background, with busy state and error handling."""
        if self._busy:
            return
        self._job += 1
        job = self._job
        self._busy = True
        self._set_status(message)
        self._update_controls()

        def finished(result: Any = None, error: Exception | None = None) -> None:
            # Ignore results that arrive after the tab was closed or the curve changed.
            if not isValid(self) or job != self._job:
                return
            self._busy = False
            if error is None:
                try:
                    on_result(result)
                except ValueError as exc:
                    error = exc
            if error is not None:
                if alert_title:
                    self._set_status("")
                    self._alert(alert_title, str(error))
                else:
                    self._set_status(str(error), "error")
            self._update_controls()

        def failed(exc: Exception) -> bool:
            finished(error=exc)
            return True  # shown by this page; the worker need not open its own message box

        run_in_background(fn, *args, on_done=finished, on_error=failed)

    def _adopt(self, priv: PrivateKey | None, pub: PublicKey, trace: Trace, message: str) -> None:
        """Make (priv, pub) the application's active keys and show how they were computed."""
        curve = pub.curve
        if curve != self._state.curve:  # a key file may bring its own (custom) curve
            self._state.register_curve(curve)
            self._state.set_curve(curve)
        if curve != self._curve:
            self.set_curve(curve)
        self.btn_regenerate.setVisible(False)
        self._state.set_keys(priv, pub)  # -> keysChanged -> refresh()
        self._show_trace(trace)
        self._set_status(message, "ok")

    def _update_controls(self) -> None:
        """Enable/disable buttons and update the hint under the d field."""
        priv, pub = self._keys()
        idle = not self._busy
        self.btn_generate.setEnabled(idle)
        self.btn_regenerate.setEnabled(idle)
        self.btn_show_math.setEnabled(pub is not None and bool(self._trace))
        self.btn_derive.setEnabled(idle and self.d_field.is_valid())
        self.btn_import.setEnabled(idle and self.import_field.is_valid())
        self.btn_load_priv.setEnabled(idle)
        self.btn_load_pub.setEnabled(idle)
        self.btn_save_priv.setEnabled(priv is not None)
        self.btn_save_pub.setEnabled(pub is not None)

        n = self._curve.n
        typed = self.d_field.value()
        if self.d_field.error():
            hint, kind = f"Not a valid private key: {self.d_field.error()}.", "error"
        elif typed is not None and (priv is None or priv.d != typed):
            hint, kind = "Press “Compute Q from this d” (or Enter) to build the key pair for this number.", "info"
        elif priv is None and pub is not None:
            hint, kind = "Public key only - the matching private key is not known to this app.", "info"
        elif n.bit_length() <= 64:
            hint, kind = f"Allowed values: 1 ≤ d ≤ n − 1 = {n - 1}.", "info"
        else:
            hint, kind = f"Allowed values: 1 ≤ d ≤ n − 1 (about 2^{n.bit_length()} possibilities).", "info"
        set_message(self.d_hint, hint, kind)
        self._apply_privacy()

    def _show_trace(self, trace: Trace) -> None:
        """Remember the steps of the last computation and display them (unless d is hidden)."""
        self._trace = list(trace)
        self._apply_privacy()

    def _apply_privacy(self) -> None:
        """Apply the "Hide d" toggle: mask the field, the warning and the steps (they contain d)."""
        hidden = self.hide_check.isChecked()
        self.d_field.setEchoMode(QLineEdit.EchoMode.Password if hidden else QLineEdit.EchoMode.Normal)
        self.warning.setVisible(not hidden and bool(self.d_field.text().strip()))
        has_d = bool(self.d_field.text().strip())
        self.hidden_note.setVisible(hidden and has_d)
        priv, pub = self._keys()
        d = self.d_field.value()
        matches_d = d == (priv.d if priv is not None else None)
        Q = pub.Q if pub is not None and matches_d else None
        self.key_diagram.update_values(d, self._curve, Q, hidden=hidden, use_hex=self.hex_check.isChecked())
        if hidden and self._trace:
            shown: Trace = []
            note = "The steps are hidden while “Hide d” is on, because they contain the private key."
        elif self._curve.n.bit_length() > 64 and not self.details_button.isChecked():
            # Building hundreds of trace cards delays the visible key result.
            # Keep the steps in memory until the user opens the details.
            shown = []
            note = "Open key details to see every step of Q = d · G."
        else:
            shown = self._trace
            note = ("Every step of the double-and-add computation of Q = d · G." if shown
                    else "Generate a key pair to see how Q = d · G is computed with double-and-add.")
        self.trace_note.setText(note)
        if shown is not self._shown_trace:
            self._shown_trace = shown
            self.trace_view.set_trace(shown)

    def _set_hex(self, use_hex: bool) -> None:
        for field in (self.d_field, self.qx_field, self.qy_field):
            field.set_display_hex(use_hex)
        self._apply_privacy()

    def _set_status(self, text: str, kind: str = "info") -> None:
        set_message(self.status, text, kind)

    def _alert(self, title: str, text: str) -> None:
        QMessageBox.warning(self, title, text)


# --------------------------------------------------------------------------
# Small layout helpers
# --------------------------------------------------------------------------
def _note(text: str) -> QLabel:
    """A small grey explanatory label."""
    label = QLabel(text)
    label.setWordWrap(True)
    label.setProperty("note", True)
    return label
