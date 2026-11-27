"""Learn walkthrough steps 6-7 (P4): Bob verifies, then a short quiz.

Step 6 reads curve, Q, msg, r, s from the shared LearnState (set by the keys
and signing steps). If those steps aren't available yet, it makes its own key
and signature with the core functions so the step still works on its own.
No math is done here: everything comes from core.verify and its trace.
"""
from __future__ import annotations

import html

from PySide6.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
)

from ecdsa_edu.gui.learn.quiz import QUIZ, check_answer
from ecdsa_edu.gui.learn.wizard import LearnPage, LearnState


def _int(s: str) -> int:
    """Trace values are decimal or 0x-hex strings."""
    return int(s, 0)


def _point(s: str) -> tuple[int, int] | None:
    """Parse "(x, y)" from the trace; anything else (e.g. the point at infinity) -> None."""
    s = s.strip()
    if not (s.startswith("(") and s.endswith(")")):
        return None
    x, y = s[1:-1].split(",")
    return _int(x), _int(y)


def _proof_html(proof: str) -> str:
    """Keep explanatory prose in Georgia and only indented equations monospace."""
    parts: list[str] = ["<div style='font-family:Georgia; margin-top:10px'>"]
    code: list[str] = []

    def flush_code() -> None:
        if code:
            parts.append(
                "<pre style=\"font-family:'JetBrains Mono',Consolas,monospace; font-size:9pt;\">"
                + html.escape("\n".join(code)) + "</pre>")
            code.clear()

    for index, line in enumerate(proof.splitlines()):
        if line.startswith("    ") or (code and line.startswith("                ")):
            code.append(line)
            continue
        flush_code()
        if not line:
            continue
        escaped = html.escape(line)
        parts.append(f"<p><b>{escaped}</b></p>" if index == 0 else f"<p>{escaped}</p>")
    flush_code()
    parts.append("</div>")
    return "".join(parts)


class VerifyPage(LearnPage):
    title = "Step 6: Bob verifies the signature"
    short_title = "Verify"
    reading = "verify.html"
    reading_title = "Go deeper: every check, a worked example and why the checks matter"
    HELP = ("Step 6 checks the signature the way Bob would, using only the public key Q, the message and (r, s). "
            "Bob computes w = s⁻¹, then u1 and u2, then the point u1·G + u2·Q. If its x-coordinate mod n equals "
            "r, the signature is VALID. The box below the table explains why this always works.")

    def enter(self, st: LearnState) -> None:
        if st.curve is None:
            self._unavailable("the curve registry (P1) isn't merged yet")
            return
        try:
            from ecdsa_edu.core.types import PublicKey, Signature
            from ecdsa_edu.core.verify import explain_verify_math, verify
        except ImportError as exc:
            self._unavailable(f"{exc.name or 'a core module'} isn't merged yet")
            return

        note = ""
        if st.Q is None or st.r is None or st.s is None:
            note = self._fill_missing_earlier_steps(st)
            if st.r is None:
                return

        trace: list = []
        ok = verify(PublicKey(st.Q, st.curve), st.msg, Signature(st.r, st.s), trace=trace)
        values = {k: v for step in trace for k, v in step.values.items()}
        st.valid = ok
        for key in ("e", "w", "u1", "u2"):
            if key in values:
                st[key] = _int(values[key])
        X = _point(values["X"]) if "X" in values else None

        verdict = ("<span style='color:#1e7e34'><b>VALID</b></span>" if ok
                   else f"<span style='color:#b00020'><b>INVALID</b></span> ({html.escape(trace[-1].title)})")
        self.set_text(
            f"{note}Bob knows only the public key <b>Q</b>, the message and the signature "
            f"<b>(r, s)</b>. He turns s into w, builds two scalars u1 and u2, and adds two points. "
            f"If the x-coordinate of that point (mod n) equals r, the signature is {verdict}."
            f"{_proof_html(explain_verify_math())}")
        self.set_formula("w = s⁻¹ mod n    u1 = e·w    u2 = r·w    X = u1·G + u2·Q    x(X) mod n = r ?")
        shown = {"message": st.msg, "Q": st.Q, "r": st.r, "s": st.s,
                 "e = H(m)": st.e, "w = s⁻¹ mod n": st.w, "u1 = e·w mod n": st.u1,
                 "u2 = r·w mod n": st.u2}
        if X is not None:
            shown["X = u1·G + u2·Q"] = X
            shown["x(X) mod n"] = X[0] % st.curve.n
        shown["valid?"] = ok
        self.set_values(shown)

    def _fill_missing_earlier_steps(self, st: LearnState) -> str:
        """Make a key and signature with core functions when steps 2-5 aren't merged."""
        try:
            from ecdsa_edu.core.keys import generate_keypair
            from ecdsa_edu.core.sign import sign
        except ImportError as exc:
            self._unavailable(f"steps 2-5 aren't available yet ({exc.name or 'keys/sign'} isn't merged)")
            return ""
        priv, pub = generate_keypair(st.curve)
        sig = sign(priv, st.msg)
        st.d, st.Q, st.r, st.s = priv.d, pub.Q, sig.r, sig.s
        return "<i>(The signing steps aren't in the walkthrough yet, so a fresh key and signature were made for this step.)</i><br><br>"

    def _unavailable(self, why: str) -> None:
        self.set_text(f"<i>This step will work once {html.escape(why)}.</i>")
        self.set_formula("")
        self.set_values({})


class PitfallsPage(LearnPage):
    title = "Step 7: The classic ECDSA pitfalls"
    short_title = "Pitfalls"
    reading = "pitfalls.html"
    reading_open = True
    HELP = ("Step 7 lists the mistakes behind almost every real-world break of ECDSA: reusing or leaking the "
            "nonce k, code that is not constant-time, signature malleability and missing input checks. The Attack "
            "Demo page lets you try the first one yourself.")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.set_text("The math of ECDSA is sound, but small implementation mistakes have broken it many times. "
                      "These are the classic ones, each with a real incident.")
        self.set_formula("")
        self.values_table.hide()

    def enter(self, st: LearnState) -> None:
        """Plain reading: nothing to compute."""


class QuizPage(LearnPage):
    title = "Step 8: Quiz"
    short_title = "Quiz"
    HELP = ("Three questions on what you just saw. Click an answer to see right away whether it's correct and "
            "why. You can change your answers; the score at the bottom updates.")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.set_text("Three questions on what you just saw. Pick an answer to get feedback.")
        self.set_formula("")
        self.values_table.hide()

        self.groups: list[QButtonGroup] = []
        self.feedback: list[QLabel] = []
        layout = self.layout()
        for qi, q in enumerate(QUIZ):
            box = QGroupBox(f"{qi + 1}. {q.prompt}")
            box_layout = QVBoxLayout(box)
            group = QButtonGroup(box)
            for ci, choice in enumerate(q.choices):
                rb = QRadioButton(choice.text)
                group.addButton(rb, ci)
                box_layout.addWidget(rb)
            fb = QLabel()
            fb.setWordWrap(True)
            box_layout.addWidget(fb)
            group.idClicked.connect(lambda ci, qi=qi: self.answer(qi, ci))
            self.groups.append(group)
            self.feedback.append(fb)
            layout.addWidget(box)
        self.score_label = QLabel()
        layout.addWidget(self.score_label)
        layout.addStretch(1)
        self.answers: dict[int, bool] = {}

    def answer(self, question_index: int, choice_index: int) -> None:
        ok, text = check_answer(QUIZ[question_index], choice_index)
        self.answers[question_index] = ok
        color, mark = ("#1e7e34", "✔ Correct.") if ok else ("#b00020", "✘ Not quite.")
        self.feedback[question_index].setText(
            f"<span style='color:{color}'><b>{mark}</b></span> {html.escape(text)}")
        right = sum(self.answers.values())
        self.score_label.setText(f"<b>Score: {right} / {len(QUIZ)}</b>"
                                 + ("  🎉" if right == len(QUIZ) else ""))

    def enter(self, st: LearnState) -> None:
        """The quiz keeps its answers when the student goes Back and Next again."""


class GlossaryPage(LearnPage):
    title = "Step 9: Glossary"
    short_title = "Glossary"
    reading = "glossary.html"
    reading_open = True
    HELP = "Every term used in the walkthrough and in the app, with a one-line meaning."

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.set_text("Every term used in this walkthrough and in the rest of the app, in one place.")
        self.set_formula("")
        self.values_table.hide()

    def enter(self, st: LearnState) -> None:
        """Plain reading: nothing to compute."""


PAGES = [VerifyPage, PitfallsPage, QuizPage, GlossaryPage]
