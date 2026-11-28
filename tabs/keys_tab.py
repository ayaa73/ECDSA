"""The "Keys" page (owner: P2).

Lets a student
  1. pick a private key d (typed, or random with Ctrl+G),
  2. see the public key Q = d * G as coordinates and in both hex encodings,
  3. watch below how Q was computed, step by step,
  4. copy the private key (it is never written to a file), save / load the
     public key, export a self-signed X.509 certificate (secp256k1 / P-256),
     and load a private key file.

While the private key is on screen a warning is shown; "Hide d" masks it.
A new private key made here must be copied before leaving the page: the
main window asks confirm_leave() and the user may go back to copy it.

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

from PySide6.QtCore import QEvent, Qt, QTimer
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
    QApplication,
)
from shiboken6 import isValid

from ecdsa_edu.core.curve import Curve
from ecdsa_edu.core.key_io import load_private_key, load_public_key, point_to_hex, save_public_key
from ecdsa_edu.core.keys import generate_keypair, public_from_private
from ecdsa_edu.core.trace import Trace
from ecdsa_edu.core.types import PrivateKey, PublicKey
from ecdsa_edu.core.x509 import certificate_supported, make_self_signed_certificate, to_pem
from ecdsa_edu.gui.app_state import AppState
from ecdsa_edu.gui.widgets.bigint_field import BigIntField, format_bigint
from ecdsa_edu.gui.widgets.key_derivation import MANUAL_KEY_NOTE, KeyDerivation
from ecdsa_edu.gui.widgets.hex_field import HexOutputField
from ecdsa_edu.gui.widgets.worker import run_in_background
from ecdsa_edu.gui.widgets.cards import Card, make_page_header

__all__ = ["KeysTab", "make_trace_view", "set_message"]

_KEY_FILTER = "Key files (*.json);;All files (*)"
_PEM_FILTER, _DER_FILTER = "PEM certificate (*.pem *.crt)", "DER certificate (*.der *.cer)"
CERTIFICATE_NAME = "ECDSA Lab key"
CERT_ONLY_REAL_CURVES = ("Certificates work with secp256k1 and P-256 only: X.509 names curves with standard "
                         "identifiers, and the toy curves have none.")

PRIVATE_KEY_NOTE = "Copy your private key before leaving this tab."
LEAVE_WARNING = "You haven't copied your private key. It will be lost if you continue."


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
        "Your private key is never saved to a file: press “Copy key” and keep it somewhere safe, "
        "such as a password manager. If you leave the page without copying a new key, the app "
        "reminds you. The public key can be saved as a small file and loaded again later; to "
        "check somebody else's signatures, give their public key on the Verify page.\n\n"
        "You can also type your own d, see the public key in both encodings and follow every "
        "step of the math under “Show key details”."
    )

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._curve: Curve = state.curve
        self._job = 0  # id of the newest background job; results of older jobs are dropped
        self._busy = False
        self._trace: Trace = []  # steps of the last computation
        self._shown_trace: Trace | None = None  # what the trace view currently displays
        # A private key made on this page that the user has not copied yet (None: nothing to lose).
        self._uncopied: PrivateKey | None = None
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
        self.btn_derive = QPushButton("Compute Q from chosen d")
        self.btn_derive.setStyleSheet("""
            QPushButton { background: #FFD166; color: #261522; font-weight: 700;
                          border: 2px solid #8B6124; border-radius: 12px; padding: 7px; }
            QPushButton:hover { background: #FFE29F; }
            QPushButton:focus { border-color: #4D2875; }
            QPushButton:disabled { background: #BBAE9D; color: #483F39; }
        """)
        self.btn_derive.setToolTip("Build the key pair for the number you typed or pasted above (Enter)")
        self.btn_copy_priv = QPushButton("Copy key")
        self.btn_copy_priv.setAccessibleName("Copy the private key")
        self.btn_copy_priv.setToolTip("Copy the private key d to the clipboard")
        self.copy_note = QLabel(PRIVATE_KEY_NOTE)
        self.copy_note.setWordWrap(True)
        self.copy_note.setProperty("kind", "warning")
        buttons = QVBoxLayout()
        buttons.addWidget(self.d_hint)
        buttons.addWidget(self.btn_generate)
        buttons.addWidget(self.btn_derive)
        buttons.addWidget(self.hide_check)
        self.range_label = QLabel()
        self.range_label.setWordWrap(True)
        self.range_label.setTextFormat(Qt.TextFormat.RichText)
        self.range_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        buttons.addWidget(self.range_label)
        self.key_diagram = KeyDerivation(
            self.d_field, buttons,
            beside=self.btn_copy_priv, below=self.copy_note,
        )

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
        self._pub_form = form

        # --- key files
        box_files = Card("Key files", "lavender")
        self.btn_save_pub = QPushButton("Save public key…")
        self.btn_load_pub = QPushButton("Load public key…")
        self.btn_load_priv = QPushButton("Load private key…")
        self.btn_export_cert = QPushButton("Export certificate…")
        self.btn_export_cert.setToolTip("Save a self-signed X.509 certificate for your public key, signed with "
                                        "your private key. Load it on the Verify page to check signatures.")
        self.cert_note = _note(CERT_ONLY_REAL_CURVES)
        grid = QGridLayout()
        box_files.body.addLayout(grid)
        grid.addWidget(self.btn_save_pub, 0, 0)
        grid.addWidget(self.btn_load_pub, 0, 1)
        grid.addWidget(self.btn_load_priv, 1, 0)
        grid.addWidget(self.btn_export_cert, 1, 1)
        grid.addWidget(self.cert_note, 3, 0, 1, 2)
        grid.addWidget(_note("The public key is saved as a small JSON file. The private key is never "
                             "saved by the app: copy it instead."), 2, 0, 1, 2)

        self.status = QLabel()
        self.status.setWordWrap(True)

        # Put secondary controls below the shared simulator, using the dashboard cards.
        details = QWidget()
        self._details = details
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.addLayout(header)
        self.full_values = QPlainTextEdit()
        self.full_values.setAccessibleName("Full key values")
        self.full_values.setReadOnly(True)
        self.full_values.setMinimumHeight(180)
        details_layout.addWidget(self.full_values)
        details_layout.addWidget(self.d_note)
        details_layout.addWidget(self.warning)
        details_layout.addWidget(self.hidden_note)
        details_layout.addWidget(box_pub)
        details_layout.addWidget(box_files)
        box_trace = Card("How Q = d · G was computed", "white")
        self._box_trace = box_trace
        self.trace_note = _note("")
        self.trace_view = make_trace_view()
        self.trace_toggle = QCheckBox("Show calculation steps")
        self.trace_toggle.toggled.connect(self._apply_privacy)
        box_trace.body.addWidget(self.trace_toggle)
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
        top_lay.addWidget(self.status)
        top_lay.addWidget(self.key_diagram)
        top_lay.addWidget(self.details_button, alignment=Qt.AlignmentFlag.AlignLeft)
        top_lay.addWidget(details)
        top_lay.addStretch(1)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setWidget(top)
        self._scroll.viewport().installEventFilter(self)
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
        self.btn_copy_priv.clicked.connect(self.copy_private_key)
        self.btn_export_cert.clicked.connect(self.export_certificate_dialog)
        self.btn_save_pub.clicked.connect(self.save_public_key_dialog)
        self.btn_load_priv.clicked.connect(self.load_private_key_dialog)
        self.btn_load_pub.clicked.connect(self.load_public_key_dialog)
        self.hex_check.toggled.connect(self._set_hex)
        self.hide_check.toggled.connect(self._apply_privacy)
        self.d_note.setText(MANUAL_KEY_NOTE)
        self.encoding_note.setText("Compressed = 02/03 + Qx (the prefix tells whether Qy is even or odd). "
                                   "Uncompressed = 04 + Qx + Qy.")
        self._update_controls()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize and watched is self._scroll.viewport():
            self.key_diagram.set_compact(event.size().width() < 900)
        return super().eventFilter(watched, event)

    def _toggle_details(self, visible: bool) -> None:
        self._details.setVisible(visible)
        self.details_button.setText("Hide key details" if visible else "Show key details")
        self._apply_privacy()
        if visible:
            QTimer.singleShot(0, self, lambda: self._scroll.ensureWidgetVisible(self.full_values))

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
        self._show_trace([])
        use_hex = curve.p.bit_length() > 32  # decimal reads best on toy curves
        if self.hex_check.isChecked() == use_hex:
            self._set_hex(use_hex)
        else:
            self.hex_check.setChecked(use_hex)  # triggers _set_hex
        if showed_keys and old_curve is not None and old_curve != curve:
            self._set_status(
                f"The curve changed to {curve.name}. The keys shown before belonged to "
                f"{old_curve.name} and were cleared. Press “Generate key pair” or load new keys.",
                "warning",
            )
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
            on_result=lambda keys: self._adopt(keys[0], keys[1], trace, "New key pair generated.",
                                               must_copy=True),
        )

    def derive(self) -> None:
        """Compute the public key for the d typed by the user."""
        d = self.d_field.value()
        if d is None:
            self._set_status(self._d_problem() or "Type or paste a private key d first.", "error")
            return
        priv = PrivateKey(d, self._curve)
        trace: Trace = []
        self._run(
            "Computing Q = d · G…",
            public_from_private, priv, trace,
            on_result=lambda pub: self._adopt(priv, pub, trace, "Public key computed from your d.",
                                              must_copy=True),
        )

    def copy_private_key(self) -> None:
        """Copy d to the clipboard (in the base shown on screen) and briefly confirm."""
        priv, _ = self._keys()
        if priv is None:
            return
        value = format_bigint(priv.d, self.hex_check.isChecked())
        clipboard = QApplication.clipboard()
        clipboard.setText(value)
        if clipboard.text() != value:
            self._set_status("Copy failed. Please try again.", "error")
            return
        self.copy_note.hide()
        if self._uncopied == priv:
            self._uncopied = None
        self.btn_copy_priv.setText("\u2713 Copied")
        QTimer.singleShot(1500, self, lambda: self.btn_copy_priv.setText("Copy key"))

    @property
    def private_key_uncopied(self) -> bool:
        """True while a private key made on this page has not been copied yet."""
        priv, _ = self._keys()
        return priv is not None and self._uncopied == priv

    def confirm_leave(self, closing: bool = False) -> bool:
        if not self.private_key_uncopied:
            return True
        if closing:
            return self._ask_to_leave()
        box = QMessageBox(self)
        box.setWindowTitle("Copy your private key")
        box.setText("Copy your private key before switching tabs. Keep it somewhere safe.")
        stay = box.addButton("Stay here", QMessageBox.ButtonRole.RejectRole)
        copy = box.addButton("Copy and switch tabs", QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(stay)
        box.exec()
        if box.clickedButton() is copy:
            self.copy_private_key()
            return not self.private_key_uncopied
        return False

    def _ask_to_leave(self) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Copy your private key")
        box.setText(LEAVE_WARNING)
        go_back = box.addButton("Go back", QMessageBox.ButtonRole.RejectRole)
        box.addButton("Continue anyway", QMessageBox.ButtonRole.DestructiveRole)
        box.setDefaultButton(go_back)
        box.exec()
        return box.clickedButton() is not go_back

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

    def export_certificate_dialog(self) -> None:
        """Save a self-signed X.509 certificate (PEM or DER) for the current key pair."""
        priv, pub = self._keys()
        if priv is None or pub is None:
            self._set_status("Generate or load a key pair first: the certificate is signed with the private key.",
                             "error")
            return
        if not certificate_supported(self._curve):
            self._set_status(CERT_ONLY_REAL_CURVES, "error")
            return
        path, chosen = QFileDialog.getSaveFileName(
            self, "Export certificate", f"{self._curve.name}_certificate.pem", f"{_PEM_FILTER};;{_DER_FILTER}"
        )
        if not path:
            return
        try:
            der = make_self_signed_certificate(priv, pub, CERTIFICATE_NAME)
            as_der = chosen == _DER_FILTER or path.lower().endswith((".der", ".cer"))
            with open(path, "wb") as file:
                file.write(der if as_der else to_pem(der).encode("ascii"))
        except (OSError, ValueError) as exc:
            self._alert("Could not export the certificate", str(exc))
        else:
            self._set_status(f"Certificate saved to {path}. Load it on the Verify page (Certificate).", "ok")

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

    def _adopt(self, priv: PrivateKey | None, pub: PublicKey, trace: Trace, message: str,
               must_copy: bool = False) -> None:
        """Make (priv, pub) the application's active keys and show how they were computed.

        ``must_copy``: the private key was made here, so it only exists in memory and
        the user is reminded to copy it before leaving.
        """
        curve = pub.curve
        if curve != self._state.curve:  # a key file may bring its own (custom) curve
            self._state.register_curve(curve)
            self._state.set_curve(curve)
        if curve != self._curve:
            self.set_curve(curve)
        self._uncopied = priv if must_copy else None  # a new key: copying starts over
        self._state.set_keys(priv, pub)  # -> keysChanged -> refresh()
        self._show_trace(trace)
        self._set_status(message, "ok")
        if must_copy:
            self.key_diagram.play_merge()

    def _update_controls(self) -> None:
        """Enable/disable buttons and update the hint under the d field."""
        priv, pub = self._keys()
        idle = not self._busy
        self.btn_generate.setEnabled(idle)
        self.btn_derive.setEnabled(idle and self.d_field.is_valid())
        self.btn_load_priv.setEnabled(idle)
        self.btn_load_pub.setEnabled(idle)
        self.btn_save_pub.setEnabled(pub is not None)
        supported = certificate_supported(self._curve)
        self.btn_export_cert.setEnabled(idle and priv is not None and supported)
        self.cert_note.setVisible(not supported)

        typed = self.d_field.value()
        active_value_shown = priv is not None and typed == priv.d
        self.btn_copy_priv.setVisible(active_value_shown)
        self.copy_note.setVisible(active_value_shown and self.private_key_uncopied)
        # "Compute Q" is only needed when the user types or pastes their own d: a
        # generated key pair already has its Q.
        own_d = bool(self.d_field.text().strip()) and (priv is None or typed != priv.d)
        self.btn_derive.setVisible(own_d)
        if self.d_field.error():
            hint, kind = f"Not a valid private key: {self._d_problem()}", "error"
        elif priv is None and pub is not None and not own_d:
            hint, kind = "Public key loaded. The private key is unknown.", "info"
        else:
            hint, kind = "", "info"
        self.d_hint.setVisible(bool(hint))
        set_message(self.d_hint, hint, kind)
        self._apply_privacy()

    def _d_problem(self) -> str:
        """A friendly sentence for an invalid d ('' if the field is fine)."""
        error = self.d_field.error()
        if not error:
            return ""
        if error.startswith("must be at least"):
            return "Choose a positive whole number. The smallest private key is 1."
        if error.startswith("must be at most"):
            return f"This value exceeds the maximum for {self._curve.name}. Use the range below."
        return "Enter a whole number in decimal or hexadecimal (for example, 7 or 0x07)."

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
        use_hex = self.hex_check.isChecked()
        def full(value: int) -> str:
            return format_bigint(value, use_hex)
        gx, gy = self._curve.G
        lines = [f"d   = {'Hidden' if hidden and d is not None else full(d) if d is not None else '—'}",
                 f"G.x = {full(gx)}", f"G.y = {full(gy)}",
                 f"Q.x = {full(Q[0]) if Q else '—'}", f"Q.y = {full(Q[1]) if Q else '—'}"]
        values = "\n".join(lines)
        if self.full_values.toPlainText() != values:
            self.full_values.setPlainText(values)
        large = self._curve.n.bit_length() > 64
        self.trace_toggle.setVisible(large and not hidden)
        if hidden and self._trace:
            shown: Trace = []
            note = "The steps are hidden while “Hide d” is on, because they contain the private key."
        elif large and not (self.details_button.isChecked() and self.trace_toggle.isChecked()):
            # Building hundreds of trace cards delays the visible key result.
            # Keep the steps in memory until the user opens the details.
            shown = []
            note = "Select “Show calculation steps” to inspect the double-and-add trace."
        else:
            shown = self._trace
            note = ("Every step of the double-and-add computation of Q = d · G." if shown
                    else "Generate a key pair to see how Q = d · G is computed with double-and-add.")
        self.trace_note.setText(note)
        if shown is not self._shown_trace:
            self._shown_trace = shown
            self.trace_view.set_trace(shown)

    def _set_hex(self, use_hex: bool) -> None:
        upper = format_bigint(self._curve.n - 1, use_hex)
        # Break long bounds at digit groups so the whole number fits a narrow card.
        digits = upper.removeprefix("0x")
        groups = "&#8203;".join(digits[i:i+8] for i in range(0, len(digits), 8))
        bound = ("0x" if use_hex else "") + groups
        self.range_label.setText(f"<b>Allowed range · {html.escape(self._curve.name)}</b><br>"
                                 f"1 ≤ d ≤ <span style='font-family:monospace'>{bound}</span>")
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
