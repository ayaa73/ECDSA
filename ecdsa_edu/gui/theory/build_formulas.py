"""Regenerate the formula images used by P4's Theory pages (08-10).

Run from the repo root:  python -m ecdsa_edu.gui.theory.build_formulas
Images go to gui/theory/pages/img/ and are committed, so the app never
renders formulas at startup.
"""
from __future__ import annotations

from ecdsa_edu.gui.theory.formula import render_formula
from ecdsa_edu.gui.theory.toc import PAGES_DIR

FORMULAS: dict[str, str] = {
    "p4_sign_s": r"s = k^{-1}\,(e + r\,d) \bmod n",
    "p4_verify_w": r"w = s^{-1} \bmod n",
    "p4_verify_u": r"u_1 = e\,w \bmod n \qquad u_2 = r\,w \bmod n",
    "p4_verify_x": r"X = u_1 G + u_2 Q, \qquad \mathrm{valid} \Leftrightarrow x_X \bmod n = r",
    "p4_verify_proof": r"u_1 G + u_2 Q = e w\,G + r w\,(d G) = w\,(e + r d)\,G = k\,G = R",
    "p4_nonce_k": r"k = \dfrac{e_1 - e_2}{s_1 - s_2} \bmod n",
    "p4_nonce_d": r"d = \dfrac{s_1 k - e_1}{r} \bmod n",
    "p4_malleable": r"(r,\ s) \ \mathrm{valid} \ \Rightarrow\ (r,\ n - s) \ \mathrm{valid}",
}


def main() -> None:
    out_dir = PAGES_DIR / "img"
    for name, tex in FORMULAS.items():
        path = render_formula(tex, out_dir / f"{name}.png", fontsize=15)
        print("wrote", path)


if __name__ == "__main__":
    main()
