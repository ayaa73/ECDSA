"""Regenerate the formula images used by the Learn ECDSA "Go deeper" reading.

Run from the repo root:  python -m ecdsa_edu.gui.learn.build_formulas
Images go to gui/learn/reading/img/ and are committed, so the app never
renders formulas at startup.
"""
from __future__ import annotations

from ecdsa_edu.gui.learn.formula import render_formula
from ecdsa_edu.gui.learn.reading import READING_DIR

FORMULAS: dict[str, str] = {
    "p4_verify_w": r"w = s^{-1} \bmod n",
    "p4_verify_u": r"u_1 = e\,w \bmod n \qquad u_2 = r\,w \bmod n",
    "p4_verify_x": r"X = u_1 G + u_2 Q, \qquad \mathrm{valid} \Leftrightarrow x_X \bmod n = r",
    "p4_nonce_k": r"k = \dfrac{e_1 - e_2}{s_1 - s_2} \bmod n",
    "p4_nonce_d": r"d = \dfrac{s_1 k - e_1}{r} \bmod n",
    "p4_malleable": r"(r,\ s) \ \mathrm{valid} \ \Rightarrow\ (r,\ n - s) \ \mathrm{valid}",
}


def main() -> None:
    out_dir = READING_DIR / "img"
    for name, tex in FORMULAS.items():
        path = render_formula(tex, out_dir / f"{name}.png", fontsize=15)
        print("wrote", path)


if __name__ == "__main__":
    main()
