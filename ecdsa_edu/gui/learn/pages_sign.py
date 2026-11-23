"""Learn walkthrough steps 3-5 (owner: P4): how Alice signs.

  Step 3  Hash the message and keep only as many bits as n has.
  Step 4  The secret nonce k (RFC 6979 by default, like the Sign page), R = k·G, r = x(R) mod n.
  Step 5  Compute s = k⁻¹ (e + r·d) mod n, with the Euclid steps for k⁻¹.

All values come from the real core functions and their traces (hash_message,
sign, inv_mod); nothing is recomputed here. By default k is the one RFC 6979
derives (sign() without k, read back from its trace); students may also try
their own k to see how r changes. Results are stored
in the shared LearnState (e, k, R, r, s) for step 6 (verification).

Before step 2 (Keys, P2) is merged, step 3 makes a practice key itself.
"""
from __future__ import annotations

import html
import secrets
from typing import Any

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSpinBox

from ecdsa_edu.core.field import inv_mod
from ecdsa_edu.core.hashing import hash_message
from ecdsa_edu.core.keys import generate_keypair
from ecdsa_edu.core.sign import sign
from ecdsa_edu.core.types import PrivateKey
from ecdsa_edu.gui.learn.wizard import LearnPage, LearnState

__all__ = ["HashPage", "NoncePage", "SPage", "PAGES"]

HASH = "sha256"


def _values(trace: list, title_start: str) -> dict[str, str]:
    """Values of the first trace step whose title starts with `title_start`."""
    for step in trace:
        if step.title.startswith(title_start):
            return dict(step.values)
    return {}


def _ensure_keys(st: LearnState) -> str:
    """Make a practice key when step 2 hasn't run (or isn't merged yet). Returns a note for the page."""
    if st.d is not None and st.Q is not None:
        return ""
    priv, pub = generate_keypair(st.curve)
    st.d, st.Q = priv.d, pub.Q
    return ("<i>(Step 2 didn't run, so a practice key was made for this walkthrough.)</i><br><br>")


def _first_int(text: str) -> int:
    """Trace values look like "123" or "123 (0x7b)"; return 123."""
    return int(text.split()[0])


def _sign_with_k(st: LearnState) -> list:
    """Sign st.msg with the real sign() and store k, R, r, s. Returns the trace.

    If st["k_source"] is "chosen", the student's st.k is used. Otherwise sign()
    picks k itself with RFC 6979 (the app's default), and st.k is read back from
    the trace: the accepted candidate is the last "Compute the point R" step.
    Raises ValueError when a chosen k is unusable (r = 0 or s = 0 on toy curves).
    """
    trace: list = []
    chosen = st.get("k_source") == "chosen" and st.k is not None
    priv = PrivateKey(st.d, st.curve)
    sig = sign(priv, st.msg, HASH, k=st.k, trace=trace) if chosen else sign(priv, st.msg, HASH, trace=trace)
    point = [step for step in trace if step.title.startswith("Compute the point R")][-1].values
    st.k = _first_int(point["k"])
    st.R = (_first_int(point["Rx"]), _first_int(point["Ry"]))
    st.r, st.s = sig.r, sig.s
    st["k_source"] = "chosen" if chosen else "rfc6979"
    st["sign_trace"] = trace
    return trace


# ================================================================== step 3
class HashPage(LearnPage):
    title = "Step 3: Alice hashes her message"
    HELP = ("Step 3 turns the message into a number e. SHA-256 makes a 256-bit fingerprint of the message, and "
            "then only as many bits are kept as the group order n has. The table shows the fingerprint, how many "
            "bits were dropped, and the final e that the signature uses.")

    def enter(self, st: LearnState) -> None:
        if st.curve is None:
            self.set_text("<i>This step needs a curve (step 1).</i>")
            return
        note = _ensure_keys(st)
        trace: list = []
        st.e = hash_message(st.msg, st.curve, HASH, trace)
        digest = _values(trace, "Hash the")
        cut = _values(trace, "Convert the digest")
        n_bits = st.curve.n.bit_length()
        removed = int(cut.get("removed_bits", "0"))
        keep_text = (f"Our curve's n has only <b>{n_bits} bits</b>, so Alice keeps just the leftmost {n_bits} bits "
                     f"of the 256-bit fingerprint and drops the other {removed}."
                     if removed else
                     f"n has {n_bits} bits, so the whole 256-bit fingerprint is used.")
        self.set_text(
            f"{note}A signature should not depend on how long the message is, so Alice first turns it into a "
            f"fixed-size fingerprint with SHA-256. Changing even one letter changes the fingerprint completely. "
            f"{keep_text} The result is the number <b>e</b>.")
        self.set_formula("e = leftmost bits of SHA-256(message)")
        self.set_values({
            "message": st.msg,
            "SHA-256 fingerprint (hex)": digest.get("digest", ""),
            "bits in n": n_bits,
            "bits dropped": removed,
            "e": st.e,
        })


# ================================================================== step 4
class NoncePage(LearnPage):
    title = "Step 4: Alice picks a secret k and computes r"
    HELP = ("Step 4 shows the secret nonce k and the first half of the signature, r = x(k·G) mod n. By default k "
            "comes from RFC 6979, exactly as on the Sign page. To experiment, type your own k or press \"Try a "
            "random k\" and watch r change; \"Back to the RFC 6979 k\" restores the real one.")

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.k_box = QSpinBox()
        self.k_box.setPrefix("k = ")
        self.k_box.setToolTip("Choose the secret nonce k yourself (1 to n-1)")
        self.k_box.valueChanged.connect(self._k_typed)
        self.random_button = QPushButton("Try a random k")
        self.random_button.clicked.connect(self._new_random_k)
        self.rfc_button = QPushButton("Back to the RFC 6979 k")
        self.rfc_button.setToolTip("The k the app really uses: derived from the private key and the message")
        self.rfc_button.clicked.connect(self._use_rfc6979)
        self.k_note = QLabel()
        self.k_note.setWordWrap(True)
        row = QHBoxLayout()
        row.addWidget(QLabel("Experiment:"))
        row.addWidget(self.k_box)
        row.addWidget(self.random_button)
        row.addWidget(self.rfc_button)
        row.addStretch(1)
        self.layout().addLayout(row)
        self.layout().addWidget(self.k_note)
        self.st: LearnState | None = None

    def enter(self, st: LearnState) -> None:
        self.st = st
        if st.curve is None:
            self.set_text("<i>This step needs a curve (step 1).</i>")
            return
        _ensure_keys(st)
        n = st.curve.n
        small = n < 2**31
        self.k_box.setVisible(small)
        if small:
            self.k_box.blockSignals(True)
            self.k_box.setRange(1, n - 1)
            self.k_box.blockSignals(False)
        if st.get("k_source") != "chosen" or st.k is None or not 1 <= st.k < n:
            st["k_source"] = "rfc6979"  # default: the same k the Sign page would use
        self._show()

    def _k_typed(self, value: int) -> None:
        if self.st is not None and value != self.st.k:
            self.st.k = value
            self.st["k_source"] = "chosen"
            self._show()

    def _new_random_k(self, *_: Any) -> None:
        if self.st is not None and self.st.curve is not None:
            self.st.k = 1 + secrets.randbelow(self.st.curve.n - 1)
            self.st["k_source"] = "chosen"
            self._show()

    def _use_rfc6979(self, *_: Any) -> None:
        if self.st is not None and self.st.curve is not None:
            self.st["k_source"] = "rfc6979"
            self._show()

    def _show(self) -> None:
        st = self.st
        try:
            _sign_with_k(st)
        except ValueError:
            st.R = st.r = st.s = None
            st["sign_trace"] = None
            self.k_note.setText(f"<span style='color:#b00020'>With k = {st.k} the signature would have r = 0 or "
                                "s = 0, which is not allowed. Pick another k.</span>")
            self.set_values({"k": st.k})
            return
        if st.curve.n < 2**31:  # the spin box only exists for small curves
            self.k_box.blockSignals(True)
            self.k_box.setValue(st.k)
            self.k_box.blockSignals(False)
        rfc = st["k_source"] == "rfc6979"
        self.rfc_button.setEnabled(not rfc)
        self.k_note.setText("" if rfc else
                            "<i>You chose this k yourself. Real signing uses the RFC 6979 k: press "
                            "\"Back to the RFC 6979 k\".</i>")
        self.set_text(
            "Every signature needs a secret number <b>k</b>, the <i>nonce</i>. Alice computes the point R = k·G "
            "and keeps its x-coordinate, reduced mod n, as <b>r</b>, the first half of the signature. "
            "<b>k must stay secret and must never repeat for different messages</b>: the Attack Demo shows what "
            "happens otherwise. That is why our app uses <b>RFC 6979</b>: k is computed from the private key and "
            "the message hash, so the same message always gets the same k and different messages get unrelated "
            "ones, with no random-number generator to go wrong. Try your own k to see how r changes.")
        self.set_formula("k = RFC 6979(d, e)      R = k·G      r = x(R) mod n")
        self.set_values({"k (secret)": st.k, "where k comes from": "RFC 6979 (as in the Sign page)" if rfc
                         else "chosen by you", "R = k·G": st.R, "r = x(R) mod n": st.r})


# ================================================================== step 5
class SPage(LearnPage):
    title = "Step 5: Alice computes s and the signature is ready"
    HELP = ("Step 5 computes the second half of the signature, s = k⁻¹ (e + r·d) mod n. The table shows how k⁻¹ "
            "is found with the extended Euclidean algorithm, then every value that goes into s. The pair (r, s) "
            "is the finished signature that step 6 checks.")

    def enter(self, st: LearnState) -> None:
        if st.curve is None:
            self.set_text("<i>This step needs a curve (step 1).</i>")
            return
        _ensure_keys(st)
        if st.get("sign_trace") is None:
            if st.k is None:
                st["k_source"] = "rfc6979"
            try:
                _sign_with_k(st)
            except ValueError:
                self.set_text("<i>The k from step 4 can't be used. Go back and pick another k.</i>")
                self.set_values({})
                return
        n = st.curve.n
        euclid: list = []
        k_inv = inv_mod(st.k, n, euclid)
        rows = {"k": st.k, "n": n}
        if n < 2**31:  # the Euclid table is only readable for small numbers
            for i, step in enumerate(s for s in euclid if s.title == "Euclidean division"):
                v = step.values
                rows[f"Euclid step {i + 1}"] = f"{v['old_r']} = {v['q']}·{v['r']} + {v['remainder']}"
        rows.update({"k⁻¹ mod n": k_inv, "e (step 3)": st.e, "r (step 4)": st.r, "d (private key)": st.d,
                     "s = k⁻¹ (e + r·d) mod n": st.s, "signature (r, s)": (st.r, st.s)})
        self.set_text(
            "Now Alice mixes everything together: the message fingerprint <b>e</b>, her <b>private key d</b> and "
            "the secret <b>k</b>. First she finds k⁻¹, the number that undoes multiplication by k mod n (found with "
            "the extended Euclidean algorithm). Then she computes <b>s</b>. The pair <b>(r, s)</b> is the signature: "
            f"she sends it together with the message \"{html.escape(st.msg.decode('utf-8', 'replace'))}\".")
        self.set_formula("s = k⁻¹ · (e + r·d) mod n")
        self.set_values(rows)


PAGES = [HashPage, NoncePage, SPage]
