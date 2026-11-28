"""Attack Demo tab (owner: P4): why the nonce k must never be reused.

Step 1 makes a victim sign two different messages with the same secret k
(core.attacks.demo_nonce_reuse). Both signatures then share the same r, which
is the giveaway. Step 2 runs core.attacks.recover_from_nonce_reuse on the two
public signatures, shows every algebra step, and compares the recovered
private key with the real one: MATCH.

The real d is shown only because this is a throw-away demo key.
No math here: values come from the core functions and their traces.
"""
from __future__ import annotations

import html
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ecdsa_edu.core.attacks import demo_nonce_reuse, recover_from_nonce_reuse
from ecdsa_edu.gui.tabs.p4_logic import attack_result, fmt_number, fmt_point
from ecdsa_edu.gui.tabs.p4_widgets import (
    ResultBanner, explanation, heading, make_trace_view,
)
from ecdsa_edu.gui.widgets.worker import run_in_background
from ecdsa_edu.gui.widgets.cards import Card, make_page_header

__all__ = ["AttackTab"]

STORY = (
    "To sign, Alice picks a secret random number <b>k</b> every time. If she ever uses the <b>same k</b> for two "
    "different messages, anyone who sees the two signatures can work out her <b>private key</b> with a few lines of "
    "school algebra. Then they can sign anything in her name.")

INCIDENT = (
    "<b>This really happened.</b> In 2010 the fail0verflow group showed that Sony signed PlayStation 3 software "
    "with the same k every time. Two signed files were enough to compute Sony's private key. "
    "<b>How to prevent it:</b> RFC 6979 derives k from the private key and the message, so it never repeats for "
    "different messages. Our Sign page uses it by default.")


def _value_label() -> QLabel:
    label = QLabel()
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setProperty("mono", True)
    return label


class AttackTab(QWidget):
    """Nonce-reuse attack: make two signatures with the same k, then recover d."""

    HELP = ("This page shows the most famous ECDSA mistake. Step 1 signs two messages with the same secret number "
            "k, and you can see that both signatures have the same r. Step 2 uses only those public signatures to "
            "compute the private key, and checks it against the real one.")

    def __init__(self, state: Any) -> None:
        super().__init__()
        self.state = state
        self.demo: dict | None = None

        # ---- step 1: the mistake
        self.make_button = QPushButton("Sign two messages with the same k")
        self.make_button.setMinimumHeight(36)
        self.make_button.clicked.connect(self.make_signatures)
        self.msg1, self.sig1, self.msg2, self.sig2 = (_value_label() for _ in range(4))
        self.same_r = QLabel()
        self.same_r.setWordWrap(True)
        self.k_label = _value_label()
        grid = QGridLayout()
        for row, (name, widget) in enumerate((("Message 1", self.msg1), ("Signature 1", self.sig1),
                                              ("Message 2", self.msg2), ("Signature 2", self.sig2))):
            grid.addWidget(QLabel(f"<b>{name}</b>"), row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(widget, row, 1)
        grid.setColumnStretch(1, 1)
        left = Card("The mistake", "pink", "1")
        left_layout = left.body
        left_layout.addWidget(explanation("The victim signs two <i>different</i> messages but reuses the secret k."))
        left_layout.addWidget(self.make_button)
        left_layout.addLayout(grid)
        left_layout.addWidget(self.same_r)
        left_layout.addWidget(self.k_label)
        left_layout.addStretch(1)

        # ---- step 2: the attack
        self.attack_button = QPushButton("Recover the private key")
        self.attack_button.setMinimumHeight(36)
        self.attack_button.setEnabled(False)
        self.attack_button.clicked.connect(self.run_attack)
        self.banner = ResultBanner()
        self.compare = QLabel()
        self.compare.setWordWrap(True)
        self.compare.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.show_math = QPushButton("Show calculations")
        self.show_math.setCheckable(True)
        self.show_math.setEnabled(False)
        self.trace_view = make_trace_view(paginated=False)
        self.trace_view.hide()
        self.show_math.toggled.connect(lambda on: self._toggle_trace(on))
        right = Card("The attack", "yellow", "2")
        right_layout = right.body
        right_layout.addWidget(explanation(
            "The attacker sees only the two messages and the two public signatures. Same r means same k, so:<br>"
            "<span style='font-family:monospace'>k = (e1 − e2) / (s1 − s2) mod n<br>"
            "d = (s1·k − e1) / r mod n</span>"))
        right_layout.addWidget(self.attack_button)
        right_layout.addWidget(self.banner)
        right_layout.addWidget(self.compare)
        right_layout.addWidget(self.show_math)
        right_layout.addWidget(self.trace_view, 1)

        columns = QHBoxLayout()
        columns.addWidget(left, 1)
        columns.addWidget(right, 1)

        content = QWidget()
        page = QVBoxLayout(content)
        page.addWidget(make_page_header("Why k must never repeat", "See how reusing a nonce can reveal a private key."))
        page.addLayout(columns, 1)
        page.addWidget(explanation(INCIDENT))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        if hasattr(self.trace_view, "use_page_scrolling"):
            self.trace_view.use_page_scrolling(scroll)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._reset()

    # ------------------------------------------------------------ tab contract
    def set_curve(self, curve: Any) -> None:
        self._reset()
        name = getattr(curve, "name", "the new curve")
        self.banner.show_message("info", f"Curve changed to {name}", "Press step 1 to run the demo on this curve.")

    def _curve(self) -> Any:
        curve = getattr(self.state, "curve", None)
        if curve is None:
            from ecdsa_edu.core.curves_registry import get_curve
            curve = get_curve("toy-17")
        return curve

    def _toggle_trace(self, visible: bool) -> None:
        """Let the student open the attack algebra when ready."""
        self.show_math.setText("Hide calculations" if visible else "Show calculations")
        self.trace_view.setVisible(visible)

    # ------------------------------------------------------------ step 1
    def _reset(self) -> None:
        self.demo = None
        for label in (self.msg1, self.sig1, self.msg2, self.sig2, self.same_r, self.k_label, self.compare):
            label.setText("")
        self.trace_view.set_trace([])
        self.show_math.setChecked(False)
        self.show_math.setEnabled(False)
        self.banner.show_message("info", "", "")
        self.attack_button.setEnabled(False)

    def make_signatures(self, *_: Any) -> None:
        self._reset()
        self.make_button.setEnabled(False)
        run_in_background(demo_nonce_reuse, self._curve(), on_done=self._show_signatures, on_error=self._failed)

    def _show_signatures(self, demo: dict) -> None:
        self.make_button.setEnabled(True)
        self.demo = demo
        curve = demo["curve"]
        s1, s2 = demo["sig1"], demo["sig2"]
        self.msg1.setText(html.escape(demo["msg1"].decode("utf-8", errors="replace")))
        self.msg2.setText(html.escape(demo["msg2"].decode("utf-8", errors="replace")))
        hl = "<span style='background:#fff3b0'>"
        self.sig1.setText(f"r = {hl}{fmt_number(s1.r, curve)}</span><br>s = {fmt_number(s1.s, curve)}")
        self.sig2.setText(f"r = {hl}{fmt_number(s2.r, curve)}</span><br>s = {fmt_number(s2.s, curve)}")
        self.same_r.setText("<span style='color:#b00020; font-weight:bold'>⚠ Both signatures have the same r.</span> "
                            "r comes from k·G, so the victim reused k. That is the attacker's way in.")
        self.k_label.setText(f"The secret k that was reused: {fmt_number(demo['k'], curve)}")
        self.attack_button.setEnabled(True)
        self.attack_button.setFocus()

    # ------------------------------------------------------------ step 2
    def run_attack(self, *_: Any) -> None:
        if self.demo is None:
            return
        demo = self.demo
        trace: list = []
        self.attack_button.setEnabled(False)
        run_in_background(recover_from_nonce_reuse, demo["curve"], demo["msg1"], demo["sig1"], demo["msg2"],
                          demo["sig2"], demo["hash_name"], trace,
                          on_done=lambda found: self._show_attack(found, trace), on_error=self._failed)

    def _show_attack(self, found: tuple[int, int], trace: list) -> None:
        self.attack_button.setEnabled(True)
        demo = self.demo
        result = attack_result(demo, found)
        curve = demo["curve"]
        self.banner.show_message("good" if result.match else "bad", "MATCH" if result.match else "NO MATCH",
                                 result.headline)
        self.compare.setText(
            "<table cellpadding='3'>"
            f"<tr><td><b>Private key found by the attacker</b></td><td style='font-family:monospace'>"
            f"{fmt_number(result.recovered_d, curve)}</td></tr>"
            f"<tr><td><b>Victim's real private key</b></td><td style='font-family:monospace'>"
            f"{fmt_number(result.real_d, curve)}</td></tr>"
            f"<tr><td><b>Victim's public key</b></td><td style='font-family:monospace'>"
            f"{fmt_point(demo['Q'], curve)}</td></tr></table>")
        self.trace_view.set_trace(trace)
        self.show_math.setEnabled(bool(trace))

    def _failed(self, exc: Exception) -> bool:
        self.make_button.setEnabled(True)
        self.attack_button.setEnabled(self.demo is not None)
        self.banner.show_message("bad", "Something went wrong", str(exc))
        return True
