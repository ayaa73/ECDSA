"""Verify tab (owner: P4): check a signature and see exactly why it passes or fails.

Students pick a message, a public key and a signature, press Verify and get a
big VALID / INVALID banner with the reason in plain words, plus the steps from
core.verify's trace. "Change one letter" tampers with the message and checks
again, so they can watch the signature break.

Beginner mode (default) uses the current key from the Keys page and the last
signature from the Sign page. Expert mode adds pasting or loading a key and a
signature, signing files, and choosing the hash.

No math here: everything comes from core.verify / core.key_io and the trace.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QScrollArea, QVBoxLayout, QWidget, QBoxLayout, QSizePolicy,
)

from ecdsa_edu.core.hashing import HASHES
from ecdsa_edu.core.key_io import load_public_key, point_from_hex
from ecdsa_edu.core.types import PublicKey
from ecdsa_edu.core.verify import verify, verify_file
from ecdsa_edu.gui.tabs.p4_logic import fmt_number, fmt_point, parse_signature_text, tamper_text, verdict_from_trace
from ecdsa_edu.gui.tabs.p4_widgets import (
    ResultBanner, current_mode, explanation, go_to, heading, make_trace_view, on_mode_changed,
)
from ecdsa_edu.gui.widgets.worker import run_in_background
from ecdsa_edu.gui.widgets.cards import Card, make_page_header

__all__ = ["VerifyTab"]

# Item data for the source combos.
CURRENT, PASTE, FILE = "current", "paste", "file"


class VerifyTab(QWidget):
    """Check a signature: message + public key + signature -> VALID / INVALID."""

    HELP = ("Check whether a signature is genuine. Bob only needs the message, Alice's public key and the "
            "signature. Press Verify: a green VALID means this exact message was signed with the matching private "
            "key. Then press \"Change one letter\" to see that even a tiny change makes the signature INVALID.")

    def __init__(self, state: Any) -> None:
        super().__init__()
        self.state = state
        self._file_path: Path | None = None
        self._loaded_pub: PublicKey | None = None
        self._loaded_sig_text: str | None = None
        self._autofilled = True  # message box still holds the last signed message
        self._busy = False
        self._tamper_note = ""  # set by "Change one letter", shown with the next result

        # ---- message
        self.msg_edit = QPlainTextEdit()
        self.msg_edit.setPlaceholderText("Type or paste the message that was signed.")
        self.msg_edit.setFixedHeight(120)
        self.msg_edit.textChanged.connect(self._on_message_edited)
        self.file_button = QPushButton("Use a file instead…")
        self.file_button.clicked.connect(self._choose_file)
        self.file_label = QLabel()
        self.file_clear = QPushButton("Back to text")
        self.file_clear.clicked.connect(self._clear_file)
        file_row = QHBoxLayout()
        for w in (self.file_button, self.file_label, self.file_clear):
            file_row.addWidget(w)
        file_row.addStretch(1)
        msg_box = Card("The message", "periwinkle", "1")
        msg_layout = msg_box.body
        msg_layout.addWidget(self.msg_edit)
        msg_layout.addLayout(file_row)

        # ---- public key
        self.key_source = QComboBox()
        self.key_source.addItem("My current public key (from the Keys page)", CURRENT)
        self.key_source.addItem("Paste a public key (hex)", PASTE)
        self.key_source.addItem("Load a public key file…", FILE)
        self.key_source.activated.connect(self._key_source_chosen)
        self.key_hex = QLineEdit()
        self.key_hex.setPlaceholderText("02… or 03… (compressed) or 04… (uncompressed)")
        self.key_status = QLabel()
        self.key_status.setWordWrap(True)
        self.key_go = QPushButton("Make a key →")
        self.key_go.setProperty("primary", True)
        self.key_go.clicked.connect(lambda *_: go_to(self, self.state, "Keys"))
        key_box = Card("Public key", "periwinkle", "2")
        key_layout = key_box.body
        key_layout.addWidget(self.key_source)
        key_layout.addWidget(self.key_hex)
        key_layout.addWidget(self.key_status)
        key_layout.addWidget(self.key_go, alignment=Qt.AlignmentFlag.AlignLeft)

        # ---- signature
        self.sig_source = QComboBox()
        self.sig_source.addItem("My last signature (from the Sign page)", CURRENT)
        self.sig_source.addItem("Paste a signature", PASTE)
        self.sig_source.addItem("Load a signature file…", FILE)
        self.sig_source.activated.connect(self._sig_source_chosen)
        for combo in (self.key_source, self.sig_source):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(8)
        self.sig_text = QLineEdit()
        self.sig_text.setPlaceholderText("r, s   for example: 7, 17   (or the hex / DER from the Sign page)")
        self.sig_status = QLabel()
        self.sig_status.setWordWrap(True)
        self.sig_go = QPushButton("Sign something on the Sign page")
        self.sig_go.clicked.connect(lambda *_: go_to(self, self.state, "Sign"))
        sig_box = Card("Signature (r, s)", "periwinkle", "3")
        sig_layout = sig_box.body
        sig_layout.addWidget(self.sig_source)
        sig_layout.addWidget(self.sig_text)
        sig_layout.addWidget(self.sig_status)
        sig_layout.addWidget(self.sig_go, alignment=Qt.AlignmentFlag.AlignLeft)

        # ---- options (expert)
        self.hash_combo = QComboBox()
        for name in HASHES:
            self.hash_combo.addItem(name.upper() + ("  (insecure, for comparison only)" if name == "sha1" else ""),
                                    name)
        self.options_box = QGroupBox("Options")
        opt = QFormLayout(self.options_box)
        opt.addRow("Hash used when signing:", self.hash_combo)

        # ---- actions + result
        self.verify_button = QPushButton("Verify")
        self.verify_button.setMinimumHeight(52)
        self.verify_button.setProperty("big", True)
        self.verify_button.setProperty("primary", True)
        self.verify_button.setToolTip("Check the signature (Ctrl+Shift+V)")
        self.verify_button.clicked.connect(self.run_verify)
        QShortcut(QKeySequence("Ctrl+Shift+V"), self, activated=self.run_verify)
        self.tamper_button = QPushButton("Change one letter")
        self.tamper_button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.tamper_button.setToolTip("Changes one character of the message, then verifies again")
        self.tamper_button.clicked.connect(self.tamper_and_verify)
        self.banner = ResultBanner()
        self.show_math = QPushButton("Show calculations")
        self.show_math.setCheckable(True)
        self.show_math.setEnabled(False)
        self.show_math.toggled.connect(lambda on: self._toggle_trace(on))
        self.trace_view = make_trace_view()
        self.trace_view.hide()

        # ---- page layout
        content = QWidget()
        page = QVBoxLayout(content)
        page.setContentsMargins(12, 12, 12, 24)
        page.setSpacing(24)
        page.addWidget(make_page_header("Verify a signature", "Check that this exact message was signed with the matching private key."))
        self.columns = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.columns.setSpacing(24)
        left = QVBoxLayout()
        left.setSpacing(24)
        left.addWidget(msg_box)
        self.inputs = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.inputs.setSpacing(24)
        self.inputs.addWidget(key_box)
        self.inputs.addWidget(sig_box)
        left.addLayout(self.inputs)
        left.addWidget(self.options_box)
        left.addStretch()
        self.columns.addLayout(left, 3)
        self.result_card = Card("Result", "olive")
        self.result_card.body.addWidget(self.verify_button)
        self.result_card.body.addWidget(self.banner)
        self.result_card.body.addWidget(self.tamper_button)
        self.result_card.body.addWidget(self.show_math)
        self.result_card.body.addWidget(self.trace_view, 1)
        self.result_card.body.addStretch()
        self.columns.addWidget(self.result_card, 2)
        page.addLayout(self.columns, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        if hasattr(self.trace_view, "use_page_scrolling"):
            self.trace_view.use_page_scrolling(scroll)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        # ---- state wiring
        for name, slot in (("keysChanged", self._refresh_key_status), ("signatureChanged", self._on_new_signature)):
            signal = getattr(state, name, None)
            if signal is not None:
                signal.connect(slot)
        on_mode_changed(state, self._apply_mode)
        self._clear_file()
        self._apply_mode(current_mode(state))
        self._on_new_signature()
        self._refresh_key_status()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "columns"):
            wide = self.window().width() >= 1100
            direction = QBoxLayout.Direction.LeftToRight if wide else QBoxLayout.Direction.TopToBottom
            self.columns.setDirection(direction)
            self.inputs.setDirection(direction)

    # ------------------------------------------------------------ tab contract
    def set_curve(self, curve: Any) -> None:
        """New curve: keys and signatures from the old curve no longer apply."""
        self._loaded_pub = None
        self._loaded_sig_text = None
        self.key_hex.clear()
        self.sig_text.clear()
        self.trace_view.set_trace([])
        self.show_math.setChecked(False)
        self.show_math.setEnabled(False)
        name = getattr(curve, "name", "the new curve")
        self.banner.show_message("info", f"Curve changed to {name}",
                                 "Keys and signatures from the old curve were cleared.")
        self._refresh_key_status()
        self._on_new_signature()

    # ------------------------------------------------------------ mode
    def _apply_mode(self, mode: str) -> None:
        expert = mode == "expert"
        for combo in (self.key_source, self.sig_source):
            for row in (1, 2):  # paste / file sources only in Expert mode
                combo.model().item(row).setEnabled(expert)
            if not expert:
                combo.setCurrentIndex(0)
        for w in (self.file_button, self.options_box):
            w.setVisible(expert)
        if not expert:
            self.hash_combo.setCurrentIndex(0)
            if self._file_path is not None:
                self._clear_file()
        self._on_key_source()
        self._on_sig_source()

    def _toggle_trace(self, visible: bool) -> None:
        """Show the recorded verification steps only when requested."""
        self.show_math.setText("Hide calculations" if visible else "Show calculations")
        self.trace_view.setVisible(visible)

    # ------------------------------------------------------------ inputs
    def _on_message_edited(self) -> None:
        if not self.msg_edit.signalsBlocked():
            self._autofilled = False

    def _set_message(self, text: str) -> None:
        self.msg_edit.blockSignals(True)
        self.msg_edit.setPlainText(text)
        self.msg_edit.blockSignals(False)

    def _choose_file(self, *_: Any) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose the file that was signed")
        if path:
            self._file_path = Path(path)
            self.file_label.setText(f"File: <b>{self._file_path.name}</b>")
            self.msg_edit.setEnabled(False)
            self.file_clear.setVisible(True)

    def _clear_file(self, *_: Any) -> None:
        self._file_path = None
        self.file_label.setText("")
        self.msg_edit.setEnabled(True)
        self.file_clear.setVisible(False)

    def _on_new_signature(self) -> None:
        """Pre-fill the message with the one just signed (unless the user typed their own)."""
        last_msg = getattr(self.state, "last_msg", None)
        if last_msg is not None and (self._autofilled or not self.msg_edit.toPlainText()):
            self._set_message(last_msg.decode("utf-8", errors="replace"))
            self._autofilled = True
        self._on_sig_source()

    def _key_source_chosen(self, *_: Any) -> None:
        if self.key_source.currentData() == FILE:
            self._load_key_file()
        self._on_key_source()

    def _on_key_source(self, *_: Any) -> None:
        self.key_hex.setVisible(self.key_source.currentData() == PASTE)
        self._refresh_key_status()

    def _load_key_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load a public key", "", "Key files (*.json);;All files (*)")
        if not path:
            if self._loaded_pub is None:
                self.key_source.setCurrentIndex(0)
            return
        try:
            self._loaded_pub = load_public_key(path)
        except (ValueError, OSError) as exc:
            self._loaded_pub = None
            self.key_source.setCurrentIndex(0)
            self.banner.show_message("bad", "Could not load the key", str(exc))

    def _refresh_key_status(self, *_: Any) -> None:
        source = self.key_source.currentData()
        pub = getattr(self.state, "pub", None)
        curve = getattr(self.state, "curve", None)
        self.key_go.setVisible(False)
        if source == CURRENT:
            if pub is None:
                self.key_status.setText("You don't have a key yet.")
                self.key_go.setVisible(True)
            else:
                self.key_status.setText(f"Using your public key Q = {fmt_point(pub.Q, curve)}")
        elif source == FILE:
            self.key_status.setText(
                f"Loaded key Q = {fmt_point(self._loaded_pub.Q, curve)} on {self._loaded_pub.curve.name}"
                if self._loaded_pub else "No key file loaded.")
        else:
            self.key_status.setText("Paste the public key exactly as the Keys page shows it.")

    def _sig_source_chosen(self, *_: Any) -> None:
        if self.sig_source.currentData() == FILE:
            self._load_sig_file()
        self._on_sig_source()

    def _on_sig_source(self, *_: Any) -> None:
        source = self.sig_source.currentData()
        self.sig_text.setVisible(source == PASTE)
        self.sig_go.setVisible(False)
        sig = getattr(self.state, "last_sig", None)
        if source == CURRENT:
            if sig is None:
                self.sig_status.setText("You haven't signed anything yet.")
                self.sig_go.setVisible(True)
            else:
                curve = getattr(self.state, "curve", None)
                self.sig_status.setText(f"Using your last signature: r = {fmt_number(sig.r, curve)}, "
                                        f"s = {fmt_number(sig.s, curve)}")
        elif source == FILE:
            self.sig_status.setText("Signature loaded from file." if self._loaded_sig_text else "")
        else:
            self.sig_status.setText("Type r, s (two numbers), or paste the hex or DER from the Sign page.")

    def _load_sig_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load a signature")
        if not path:
            if self._loaded_sig_text is None:
                self.sig_source.setCurrentIndex(0)
            return
        try:
            raw = Path(path).read_bytes()[:10_000]
        except OSError as exc:
            self.sig_source.setCurrentIndex(0)
            self.banner.show_message("bad", "Could not read the file", exc.strerror or str(exc))
            return
        try:
            self._loaded_sig_text = raw.decode("ascii").strip()
        except UnicodeDecodeError:
            self._loaded_sig_text = raw.hex()  # binary DER: hand it over as hex

    # ------------------------------------------------------------ collect + verify
    def _collect(self) -> tuple[PublicKey, Any, Any, str]:
        """Gather the inputs, or raise ValueError with a message a student can act on."""
        curve = getattr(self.state, "curve", None)
        if curve is None:
            raise ValueError("Choose a curve first (toolbar at the top).")

        source = self.key_source.currentData()
        if source == CURRENT:
            pub = getattr(self.state, "pub", None)
            if pub is None:
                raise ValueError("You need a public key first: make one on the Keys page.")
        elif source == PASTE:
            text = self.key_hex.text().strip()
            if not text:
                raise ValueError("Paste the public key in hex first.")
            pub = PublicKey(point_from_hex(curve, text), curve)
        else:
            pub = self._loaded_pub
            if pub is None:
                raise ValueError("Load a public key file first.")
            if pub.curve != curve:
                raise ValueError(f"This key belongs to the curve {pub.curve.name}. Select that curve at the top "
                                 "first.")

        source = self.sig_source.currentData()
        if source == CURRENT:
            sig = getattr(self.state, "last_sig", None)
            if sig is None:
                raise ValueError("There is no signature yet: sign a message on the Sign page, or paste one.")
        elif source == PASTE:
            sig = parse_signature_text(self.sig_text.text(), curve)
        else:
            if not self._loaded_sig_text:
                raise ValueError("Load a signature file first.")
            sig = parse_signature_text(self._loaded_sig_text, curve)

        message: Any = self._file_path if self._file_path is not None else \
            self.msg_edit.toPlainText().encode("utf-8")
        return pub, message, sig, self.hash_combo.currentData() or "sha256"

    def run_verify(self, *_: Any) -> None:
        if self._busy:
            return
        try:
            pub, message, sig, hash_name = self._collect()
        except ValueError as exc:
            text = str(exc)
            # "...first" messages mean a missing step; anything else is input that can't be used.
            missing_step = "first" in text
            self.banner.show_message("info" if missing_step else "bad",
                                     "Not ready yet" if missing_step else "Check your input",
                                     text[:1].upper() + text[1:])
            return
        trace: list = []
        fn = verify_file if isinstance(message, Path) else verify
        self._set_busy(True)
        run_in_background(fn, pub, message, sig, hash_name, trace,
                          on_done=lambda ok: self._show_result(ok, trace), on_error=self._show_error)

    def tamper_and_verify(self, *_: Any) -> None:
        if self._file_path is not None:
            self.banner.show_message("info", "Tamper works on typed messages",
                                     "Switch back to text to try it, or edit the file and verify again.")
            return
        new_text, what = tamper_text(self.msg_edit.toPlainText())
        self._set_message(new_text)
        self._autofilled = False
        self._tamper_note = what
        self.run_verify()

    def _show_result(self, ok: bool, trace: list) -> None:
        self._set_busy(False)
        verdict = verdict_from_trace(ok, trace)
        note = getattr(self, "_tamper_note", "")
        self._tamper_note = ""
        detail = (f"We {note}. " if note else "") + verdict.reason
        self.banner.show_message("good" if verdict.valid else "bad", verdict.headline, detail)
        self.result_card.setProperty("card", "olive" if verdict.valid else "pink")
        self.result_card.style().unpolish(self.result_card)
        self.result_card.style().polish(self.result_card)
        self.trace_view.set_trace(trace)
        self.show_math.setEnabled(bool(trace))
        signal = getattr(self.state, "verificationCompleted", None)
        if signal is not None:
            signal.emit(bool(ok))

    def _show_error(self, exc: Exception) -> bool:
        self._set_busy(False)
        self.banner.show_message("bad", "Could not verify", str(exc))
        return True  # handled: no extra message box

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.verify_button.setEnabled(not busy)
        self.tamper_button.setEnabled(not busy)
