"""Practical ECDSA signing page (owner: P3).

Students use this page to sign text or, in Expert mode, a file. The page never
implements cryptographic arithmetic: it calls the P3 core functions, displays
their result, and hands their recorded steps to the shared trace widget.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QAction, QFont, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ecdsa_edu.core.sig_encoding import sig_to_der, sig_to_hex
from ecdsa_edu.core.sign import sign, sign_file
from ecdsa_edu.core.trace import TraceStep
from ecdsa_edu.core.types import PrivateKey, Signature
from ecdsa_edu.gui.tabs.keys_tab import set_message
from ecdsa_edu.gui.tabs.p4_widgets import current_mode, go_to, make_trace_view, on_mode_changed
from ecdsa_edu.gui.widgets.bigint_field import BigIntField
from ecdsa_edu.gui.widgets.hex_field import HexOutputField
from ecdsa_edu.gui.widgets.worker import run_in_background

__all__ = ["SignTab"]


class _ModernComboBox(QComboBox):
    """Draw a small clean chevron instead of the platform's dated arrow."""

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.palette().text().color(), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        centre_x = self.width() - 20
        centre_y = self.height() // 2
        painter.drawLine(centre_x - 4, centre_y - 2, centre_x, centre_y + 2)
        painter.drawLine(centre_x, centre_y + 2, centre_x + 4, centre_y - 2)


def _sign_request(
    priv: PrivateKey,
    message: bytes,
    file_path: str | None,
    hash_name: str,
    nonce_mode: str,
    manual_k: int | None,
) -> tuple[Signature, list, bytes | None]:
    """Run one core signing request away from the GUI thread."""
    trace: list = []
    if file_path is not None:
        # sign_file hashes in chunks. Its fixed contract supports deterministic
        # and random modes, but intentionally has no manual-k argument.
        sig = sign_file(
            priv,
            file_path,
            hash_name,
            deterministic=nonce_mode != "random",
            trace=trace,
        )
        remembered_message = None
    else:
        sig = sign(
            priv,
            message,
            hash_name,
            k=manual_k if nonce_mode == "manual" else None,
            deterministic=nonce_mode != "random",
            trace=trace,
        )
        remembered_message = message
    return sig, trace, remembered_message


def _hide_private_values(trace: list) -> list[TraceStep]:
    """Copy a trace while replacing any accidentally recorded private key."""
    cleaned: list[TraceStep] = []
    for step in trace:
        values = {
            str(name): "hidden" if str(name).strip().lower() == "d" else str(value)
            for name, value in step.values.items()
        }
        cleaned.append(TraceStep(step.title, step.formula, values))
    return cleaned


class SignTab(QWidget):
    """Sign text or a file using the private key stored in ``AppState``."""

    HELP = (
        "Enter a message and press Sign to create an ECDSA signature. "
        "Beginner mode uses SHA-256 and the safe RFC 6979 nonce automatically. "
        "Expert mode adds file signing, other hashes, and nonce experiments. "
        "Never reuse a manually chosen nonce with a real private key."
    )

    def __init__(self, state, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("signTab")
        self.state = state
        self._curve = state.curve
        self._file_path: str | None = None
        self._busy = False
        self._job_priv: PrivateKey | None = None
        self._last_signature: Signature | None = None
        self._last_trace: list[TraceStep] = []

        heading = QLabel("Sign a message")
        heading.setObjectName("signHeading")
        intro = QLabel(
            "Alice uses her private key to sign a message. Anyone with her public key can then check "
            "that the message is authentic and unchanged."
        )
        intro.setObjectName("signIntro")
        intro.setWordWrap(True)

        # The empty state is deliberately actionable instead of being a dead warning.
        self.no_key_box = QGroupBox("You need a private key first")
        self.no_key_box.setObjectName("emptyCard")
        no_key_layout = QHBoxLayout(self.no_key_box)
        no_key_text = QLabel("Create or load a private key before signing.")
        self.go_to_keys_button = QPushButton("Go to Keys")
        no_key_layout.addWidget(no_key_text)
        no_key_layout.addStretch(1)
        no_key_layout.addWidget(self.go_to_keys_button)

        self.message_edit = QPlainTextEdit()
        self.message_edit.setAccessibleName("Message to sign")
        self.message_edit.setPlaceholderText("Type the message Alice wants to sign")
        self.message_edit.setPlainText("Hello, ECDSA!")
        self.message_edit.setMinimumHeight(90)

        self.file_label = QLabel("Using the typed message")
        self.file_label.setWordWrap(True)
        self.choose_file_button = QPushButton("Choose file…")
        self.use_text_button = QPushButton("Use typed message")
        self.use_text_button.setEnabled(False)
        file_row = QHBoxLayout()
        file_row.addWidget(self.choose_file_button)
        file_row.addWidget(self.use_text_button)
        file_row.addWidget(self.file_label, 1)

        self.hash_combo = _ModernComboBox()
        self.hash_combo.setObjectName("modernCombo")
        for label, name in (
            ("SHA-256 (recommended)", "sha256"),
            ("SHA-384", "sha384"),
            ("SHA-512", "sha512"),
            ("SHA-1 (insecure; comparison only)", "sha1"),
        ):
            self.hash_combo.addItem(label, name)

        self.deterministic_radio = QRadioButton("Deterministic (RFC 6979)")
        self.random_radio = QRadioButton("Random")
        self.manual_radio = QRadioButton("Manual k")
        self.deterministic_radio.setChecked(True)
        self.nonce_group = QButtonGroup(self)
        self.nonce_group.addButton(self.deterministic_radio)
        self.nonce_group.addButton(self.random_radio)
        self.nonce_group.addButton(self.manual_radio)
        nonce_row = QHBoxLayout()
        nonce_row.addWidget(self.deterministic_radio)
        nonce_row.addWidget(self.random_radio)
        nonce_row.addWidget(self.manual_radio)
        nonce_row.addStretch(1)

        self.manual_k_field = BigIntField(minimum=1)
        self.manual_k_field.setAccessibleName("Manual nonce k")
        self.manual_k_field.setPlaceholderText("k from 1 to n - 1")
        self.manual_warning = QLabel("⚠ Never reuse k. Reuse can reveal the private key.")
        self.manual_warning.setProperty("kind", "error")
        self.manual_warning.setWordWrap(True)
        manual_row = QHBoxLayout()
        manual_row.addWidget(QLabel("k ="))
        manual_row.addWidget(self.manual_k_field, 1)
        manual_row.addWidget(self.manual_warning, 2)
        self.manual_row_widget = QWidget()
        self.manual_row_widget.setLayout(manual_row)
        self.manual_row_widget.hide()

        self.expert_options = QGroupBox("Expert options")
        self.expert_options.setObjectName("expertCard")
        expert_layout = QVBoxLayout(self.expert_options)
        expert_layout.addLayout(file_row)
        hash_form = QFormLayout()
        hash_form.addRow("Hash", self.hash_combo)
        expert_layout.addLayout(hash_form)
        expert_layout.addLayout(nonce_row)
        expert_layout.addWidget(self.manual_row_widget)

        self.sign_button = QPushButton("Sign")
        self.sign_button.setProperty("primary", True)
        self.sign_button.setProperty("big", True)
        self.sign_button.setMinimumHeight(44)
        self.status = QLabel()
        self.status.setWordWrap(True)

        self.result_box = QGroupBox("Signature")
        self.result_box.setObjectName("resultCard")
        result_layout = QFormLayout(self.result_box)
        self.r_output = HexOutputField(lines=1, save_name="signature-r", show_save=False)
        self.s_output = HexOutputField(lines=1, save_name="signature-s", show_save=False)
        self.r_output.setAccessibleName("Signature value r")
        self.s_output.setAccessibleName("Signature value s")
        result_layout.addRow("r", self.r_output)
        result_layout.addRow("s", self.s_output)

        self.encoding_panel = QGroupBox("Signature encoding")
        self.encoding_panel.setObjectName("encodingCard")
        encoding_layout = QVBoxLayout(self.encoding_panel)
        encoding_help = QLabel(
            "Fixed-width hex places padded r followed by padded s. DER is the standard binary "
            "format used by cryptography tools and saved certificates."
        )
        encoding_help.setWordWrap(True)
        self.hex_encoding_radio = QRadioButton("Fixed-width hex: r followed by s")
        self.der_encoding_radio = QRadioButton("DER: standard ASN.1 format")
        self.hex_encoding_radio.setChecked(True)
        self.encoding_group = QButtonGroup(self)
        self.encoding_group.addButton(self.hex_encoding_radio)
        self.encoding_group.addButton(self.der_encoding_radio)
        encoding_choices = QHBoxLayout()
        encoding_choices.addWidget(self.hex_encoding_radio)
        encoding_choices.addWidget(self.der_encoding_radio)
        encoding_choices.addStretch(1)
        self.encoding_output = HexOutputField(lines=2, save_name="signature")
        self.encoding_output.setAccessibleName("Encoded signature")
        self.encoding_output.setMinimumHeight(92)
        encoding_layout.addWidget(encoding_help)
        encoding_layout.addLayout(encoding_choices)
        encoding_layout.addWidget(QLabel("Encoded signature"))
        encoding_layout.addWidget(self.encoding_output)
        self.encoding_panel.setMinimumHeight(190)
        result_layout.addRow(self.encoding_panel)
        self.result_box.hide()

        self.trace_box = QGroupBox("How was this calculated?")
        self.trace_box.setObjectName("traceCard")
        trace_layout = QVBoxLayout(self.trace_box)
        self.trace_view = make_trace_view(self)
        self.trace_view.setMinimumHeight(360)
        trace_layout.addWidget(self.trace_view)
        self.trace_box.hide()

        # This page becomes tall in Expert mode. Keeping one outer scroll area
        # lets every output and trace control stay at a readable height.
        page_content = QWidget()
        page_content.setObjectName("signPage")
        self.page_content = page_content
        content_layout = QVBoxLayout(page_content)
        content_layout.addWidget(heading)
        content_layout.addWidget(intro)
        content_layout.addWidget(self.no_key_box)
        content_layout.addWidget(QLabel("Message"))
        content_layout.addWidget(self.message_edit)
        content_layout.addWidget(self.expert_options)
        content_layout.addWidget(self.sign_button)
        content_layout.addWidget(self.status)
        content_layout.addWidget(self.result_box)
        content_layout.addWidget(self.trace_box)
        content_layout.addStretch(1)

        self.page_scroll = QScrollArea()
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.page_scroll.setWidget(page_content)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.page_scroll)

        self.go_to_keys_button.clicked.connect(lambda: go_to(self, self.state, "Keys"))
        self.choose_file_button.clicked.connect(self.choose_file)
        self.use_text_button.clicked.connect(self.use_typed_message)
        self.sign_button.clicked.connect(self.sign_current_input)
        self.manual_radio.toggled.connect(self.manual_row_widget.setVisible)
        self.encoding_group.buttonClicked.connect(self._show_encoding)
        self.message_edit.textChanged.connect(self._input_changed)
        self.hash_combo.currentIndexChanged.connect(self._input_changed)
        self.nonce_group.buttonClicked.connect(self._input_changed)
        self.manual_k_field.textChanged.connect(self._input_changed)
        state.keysChanged.connect(self._refresh_key_state)
        on_mode_changed(state, self._apply_mode)

        self.save_action = QAction("Save signature", self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(self.encoding_output.save_dialog)
        self.addAction(self.save_action)

        self._update_curve_controls()
        self._apply_mode(current_mode(state))
        self._refresh_key_state()
        self._apply_visual_style()

    # ---------------------------------------------------------------- input
    def choose_file(self) -> None:
        """Choose a file; signing later uses ``sign_file`` and chunked hashing."""
        path, _ = QFileDialog.getOpenFileName(self, "Choose a file to sign", "", "All files (*)")
        if not path:
            return
        self._file_path = path
        self.file_label.setText(f"File: {Path(path).name}")
        self.file_label.setToolTip(path)
        self.message_edit.setEnabled(False)
        self.use_text_button.setEnabled(True)
        # The contract for sign_file has no manual-k parameter. Keep the user
        # on a mode that the core supports rather than secretly reading the file.
        self.manual_radio.setEnabled(False)
        if self.manual_radio.isChecked():
            self.deterministic_radio.setChecked(True)
        self._input_changed()

    def use_typed_message(self) -> None:
        """Leave file mode and return to the message box."""
        self._file_path = None
        self.file_label.setText("Using the typed message")
        self.file_label.setToolTip("")
        self.message_edit.setEnabled(True)
        self.use_text_button.setEnabled(False)
        self.manual_radio.setEnabled(True)
        self._input_changed()

    def _nonce_mode(self) -> str:
        if self.random_radio.isChecked():
            return "random"
        if self.manual_radio.isChecked():
            return "manual"
        return "deterministic"

    def _input_changed(self, *_: Any) -> None:
        """A previous result no longer describes the visible input."""
        if self._last_signature is not None:
            self._clear_result()
            if self.state.last_sig is not None:
                self.state.set_signature(None, None)

    # --------------------------------------------------------------- signing
    def sign_current_input(self) -> None:
        """Validate the page and send the core signing call to a worker."""
        if self._busy:
            return
        priv = self.state.priv
        if priv is None:
            set_message(self.status, "Create or load a private key first.", "warning")
            return

        mode = self._nonce_mode()
        manual_k = self.manual_k_field.value() if mode == "manual" else None
        if mode == "manual" and manual_k is None:
            reason = self.manual_k_field.error() or "enter k first"
            set_message(self.status, f"Manual k is not valid: {reason}.", "error")
            return
        if self._file_path is not None and mode == "manual":
            set_message(self.status, "Manual k is available for text messages only.", "warning")
            return

        message = self.message_edit.toPlainText().encode("utf-8")
        hash_name = str(self.hash_combo.currentData() or "sha256")
        self._busy = True
        self._job_priv = priv
        self.sign_button.setEnabled(False)
        set_message(self.status, "Signing…", "info")
        run_in_background(
            _sign_request,
            priv,
            message,
            self._file_path,
            hash_name,
            mode,
            manual_k,
            on_done=self._sign_done,
            on_error=self._sign_failed,
        )

    def _sign_done(self, result: tuple[Signature, list, bytes | None]) -> None:
        """Display a worker result, unless the key changed while it ran."""
        self._busy = False
        self.sign_button.setEnabled(self.state.priv is not None)
        sig, trace, remembered_message = result
        if self.state.priv is not self._job_priv or self.state.priv is None:
            set_message(self.status, "The key changed while signing. Please sign again.", "warning")
            return

        self._last_signature = sig
        self._last_trace = _hide_private_values(trace)
        self.state.set_signature(sig, remembered_message)
        self._show_result()
        target = f"file {Path(self._file_path).name}" if self._file_path else "message"
        hash_name = str(self.hash_combo.currentData() or "sha256").upper().replace("SHA", "SHA-")
        note = f"Signature created for the {target} with {hash_name}."
        if self.hash_combo.currentData() == "sha1":
            note += " SHA-1 is insecure and is included only for comparison."
        set_message(self.status, note, "ok")

    def _sign_failed(self, exc: Exception) -> bool:
        self._busy = False
        self.sign_button.setEnabled(self.state.priv is not None)
        set_message(self.status, str(exc) or "The signature could not be created.", "error")
        return True  # this page has already shown the friendly error

    # --------------------------------------------------------------- display
    def _show_result(self) -> None:
        sig = self._last_signature
        if sig is None or self._curve is None:
            return
        size = (self._curve.n.bit_length() + 7) // 8
        self.r_output.set_hex(sig.r.to_bytes(size, "big").hex())
        self.s_output.set_hex(sig.s.to_bytes(size, "big").hex())
        self._show_encoding()
        self.trace_view.set_trace(self._last_trace)
        self.result_box.show()
        self.trace_box.show()

    def _show_encoding(self, *_: Any) -> None:
        sig = self._last_signature
        if sig is None or self._curve is None:
            self.encoding_output.clear()
            return
        if self.der_encoding_radio.isChecked():
            self.encoding_output.set_bytes(sig_to_der(sig))
        else:
            self.encoding_output.set_hex(sig_to_hex(sig, self._curve))

    def _clear_result(self) -> None:
        self._last_signature = None
        self._last_trace = []
        self.r_output.clear()
        self.s_output.clear()
        self.encoding_output.clear()
        self.trace_view.set_trace([])
        self.result_box.hide()
        self.trace_box.hide()

    def _refresh_key_state(self) -> None:
        has_key = self.state.priv is not None
        self.no_key_box.setVisible(not has_key)
        self.sign_button.setEnabled(has_key and not self._busy)
        if not has_key:
            self._clear_result()

    def _update_curve_controls(self) -> None:
        if self._curve is None:
            return
        self.manual_k_field.set_range(1, self._curve.n - 1)
        self.manual_k_field.set_display_hex(self._curve.n.bit_length() > 64)

    def _apply_mode(self, mode: str) -> None:
        expert = mode == "expert"
        self.expert_options.setVisible(expert)
        self.encoding_panel.setVisible(expert)
        if not expert:
            # Beginner mode always returns to the safest working defaults.
            self.use_typed_message()
            self.hash_combo.setCurrentIndex(self.hash_combo.findData("sha256"))
            self.deterministic_radio.setChecked(True)

    def _apply_visual_style(self) -> None:
        """Give this teaching page the same visual character as Overview."""
        dark = self.palette().window().color().lightness() < 128
        # setStyleSheet can produce another palette event. Remembering the
        # current choice keeps that event from styling the page a second time.
        if getattr(self, "_visual_dark", None) == dark:
            return
        self._visual_dark = dark
        if dark:
            page = "#14172b"
            card = "#1c2b43"
            inner = "#17243a"
            text = "#edf3fc"
            muted = "#aabbd3"
            border = "#6689bc"
            accent = "#6286b8"
            accent_hover = "#7699c8"
            accent_text = "#10182a"
        else:
            page = "#f4f7fc"
            card = "#eef5ff"
            inner = "#f8fbff"
            text = "#102b56"
            muted = "#365f99"
            border = "#8eacd5"
            accent = "#194f91"
            accent_hover = "#2f63ad"
            accent_text = "#ffffff"

        self.setFont(QFont("Georgia", 10))
        # Number fields keep the monospace font they already receive from the
        # shared widgets. The rest of this page follows Overview's Georgia look.
        self.setStyleSheet(
            f"""
            QWidget#signTab, QWidget#signPage {{ background: {page}; color: {text}; }}
            QLabel#signHeading {{
                color: {text}; font-family: Georgia; font-size: 20pt;
                font-weight: 600; padding: 4px 2px;
            }}
            QLabel#signIntro {{ color: {muted}; font-family: Georgia; font-size: 11pt; padding-bottom: 4px; }}
            QWidget#signPage QGroupBox {{
                background: {card}; color: {text}; border: 1px solid {border};
                border-radius: 14px; margin-top: 18px; padding: 16px 14px 14px 14px;
                font-family: Georgia; font-weight: 600;
            }}
            QWidget#signPage QGroupBox::title {{
                subcontrol-origin: margin; left: 18px; padding: 0 7px;
                color: {text}; background: {page};
            }}
            QGroupBox#encodingCard {{ background: {inner}; border-radius: 12px; }}
            QGroupBox#encodingCard::title {{ background: {card}; }}
            QWidget#signPage QPushButton {{
                border: 1px solid {border}; border-radius: 10px; padding: 7px 16px;
                background: {inner}; color: {text};
            }}
            QWidget#signPage QPushButton:hover {{ border-color: {accent}; background: {card}; }}
            QWidget#signPage QPushButton[primary="true"] {{
                background: {accent}; color: {accent_text}; border-color: {accent};
                font-family: Georgia; font-size: 12pt; font-weight: 600;
            }}
            QWidget#signPage QPushButton[primary="true"]:hover {{ background: {accent_hover}; }}
            QWidget#signPage QPlainTextEdit, QWidget#signPage QLineEdit, QWidget#signPage QComboBox {{
                background: {inner}; color: {text}; border: 1px solid {border};
                border-radius: 10px; padding: 6px 9px;
            }}
            QWidget#signPage QComboBox {{ padding-right: 36px; }}
            QWidget#signPage QComboBox::drop-down {{
                width: 36px; border: 0; background: transparent;
            }}
            QWidget#signPage QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
            QWidget#signPage QPlainTextEdit:focus, QWidget#signPage QLineEdit:focus,
            QWidget#signPage QComboBox:focus {{ border: 2px solid {accent}; }}
            QWidget#signPage QRadioButton {{ color: {text}; spacing: 7px; }}
            QScrollBar:vertical {{ background: {page}; width: 12px; margin: 2px; }}
            QScrollBar::handle:vertical {{ background: {border}; min-height: 32px; border-radius: 5px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            """
        )

    def changeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Refresh the local colours after the app switches theme."""
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange):
            if hasattr(self, "page_content"):
                self._apply_visual_style()

    # ------------------------------------------------------------- tab API
    def set_curve(self, curve) -> None:
        """Clear results that belonged to the previous curve."""
        changed = self._curve is not None and curve != self._curve
        self._curve = curve
        self._update_curve_controls()
        self._clear_result()
        self._refresh_key_state()
        if changed:
            set_message(self.status, "The curve changed, so the previous signature was cleared.", "info")

