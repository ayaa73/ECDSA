"""Learn walkthrough, step 2: Alice makes a key pair (owner: P2).

This file plugs into P4's Learn wizard (gui/learn/wizard.py). The wizard
imports it, builds every class listed in PAGES, and calls page.enter(st)
each time the student arrives on the page. `st` is P4's LearnState: a
dictionary shared by all steps (st["curve"], st["d"], st["Q"], ...).

What the page does:
  - shows the private key d (random at first; the student can type another);
  - computes the public key Q = d * G by calling the core (no math here);
  - shows the double-and-add steps underneath;
  - stores d and Q in st, so the signing steps can use them.

P4's LearnPage base class already gives us a title, a text area, a big
formula and a table of values (set_text, set_formula, set_values). We add
one row with the d box and two buttons, and the list of steps.
"""
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ecdsa_edu.core.curves_registry import get_curve
from ecdsa_edu.core.key_io import point_to_hex
from ecdsa_edu.core.keys import generate_keypair, public_from_private
from ecdsa_edu.core.types import PrivateKey
from ecdsa_edu.gui.learn.wizard import LearnPage
from ecdsa_edu.gui.tabs.keys_tab import make_trace_view, set_message
from ecdsa_edu.gui.widgets.bigint_field import BigIntField

EXPLANATION = (
    "Alice's <b>private key</b> is just a secret whole number <b>d</b>, picked at random "
    "from 1 to n - 1. Her <b>public key</b> is the point <b>Q = d · G</b>: the base point G "
    "added to itself d times.<br><br>"
    "Computing Q from d is fast, even for huge numbers. Going back from Q to d is the "
    "<i>discrete logarithm problem</i>, and nobody knows a fast way to do it. That is why "
    "Alice can publish Q and keep d secret."
)


class KeysPage(LearnPage):
    """Step 2: choose d (random or typed) and compute Q = d * G."""

    title = "Step 2: Alice makes a key pair"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.st = None  # the walkthrough state, set in enter()
        self.curve = None  # the curve of the walkthrough

        # A row with the d box and two buttons.
        self.d_field = BigIntField(minimum=1)
        self.d_field.setAccessibleName("Private key d")
        self.use_button = QPushButton("Use this d")
        self.random_button = QPushButton("Randomize")
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(QLabel("d ="))
        row_layout.addWidget(self.d_field, 1)
        row_layout.addWidget(self.use_button)
        row_layout.addWidget(self.random_button)

        # One line under the row for hints and errors.
        self.hint = QLabel()
        self.hint.setWordWrap(True)

        # The list of double-and-add steps.
        self.trace_view = make_trace_view()

        # P4's base class already made a vertical layout:
        #   0 title, 1 text, 2 formula, 3 values table.
        # We put our row and hint after the text, and the steps at the end.
        layout = self.layout()
        layout.insertWidget(2, row)
        layout.insertWidget(3, self.hint)
        layout.addWidget(self.trace_view, 1)

        self.use_button.clicked.connect(self.use_typed_d)
        self.d_field.returnPressed.connect(self.use_typed_d)
        self.random_button.clicked.connect(self.randomize)

    def enter(self, st) -> None:
        """Called by the wizard when the page is shown."""
        self.st = st
        self.curve = st["curve"]
        if self.curve is None:  # the curve step did not set one: use the toy curve
            self.curve = get_curve("toy-17")
            st["curve"] = self.curve

        self.set_text(EXPLANATION)
        self.set_formula("Q = d · G")
        self.d_field.set_range(1, self.curve.n - 1)
        self.d_field.set_display_hex(self.curve.n.bit_length() > 64)

        # Keep the d from earlier if it still fits this curve; otherwise pick a new one.
        d = st["d"]
        if isinstance(d, int) and 1 <= d <= self.curve.n - 1:
            self.show_key(d)
        else:
            self.randomize()

    def randomize(self) -> None:
        """Let the core pick a random d (it uses the secure `secrets` module)."""
        if self.curve is None:
            return
        trace = []
        private_key, public_key = generate_keypair(self.curve, trace)
        self.store_and_show(private_key.d, public_key.Q, trace)
        set_message(self.hint, "A new random d was picked. Try typing your own, too.", "info")

    def use_typed_d(self) -> None:
        """Compute the key pair for the number the student typed."""
        if self.curve is None:
            return
        d = self.d_field.value()
        if d is None:
            reason = self.d_field.error() or "type a number first"
            set_message(self.hint, "Not a valid private key: " + reason + ".", "error")
            return
        self.show_key(d)
        set_message(self.hint, "Key pair computed from your d.", "ok")

    def show_key(self, d: int) -> None:
        """Compute Q for this d with the core, then store and display it."""
        trace = []
        public_key = public_from_private(PrivateKey(d, self.curve), trace)
        self.store_and_show(d, public_key.Q, trace)

    def store_and_show(self, d: int, Q: tuple[int, int], trace: list) -> None:
        """Save d and Q for the next steps and fill the page."""
        self.st["d"] = d
        self.st["Q"] = Q
        self.d_field.set_value(d)
        self.set_values({
            "n (order of G)": self.curve.n,
            "G (base point)": self.curve.G,
            "d (private key, secret)": d,
            "Q = d · G (public key)": Q,
            "Q in compressed hex": point_to_hex(self.curve, Q, compressed=True),
        })
        self.trace_view.set_trace(trace)


# The wizard reads this list. One page for the keys topic.
PAGES = [KeysPage]
