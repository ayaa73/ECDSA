"""Render LaTeX-style formulas to PNG for the Learn ECDSA reading (P4).

Uses matplotlib's built-in mathtext, so it works offline and needs no LaTeX
install. Supports the usual subset: fractions, sub/superscripts, Greek letters,
\\cdot, \\equiv. \\bmod, \\mod and \\pmod{n} are translated automatically
(mathtext doesn't know them natively).

Example:
    render_formula(r"s = k^{-1}(e + r d) \\bmod n", "reading/img/sign.png")
"""
from __future__ import annotations

import re
from os import PathLike
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # render to files only; never open a window

from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.mathtext import math_to_image  # noqa: E402


_PMOD_RE = re.compile(r"\\pmod\s*\{([^{}]*)\}")
_MOD_RE = re.compile(r"\\[bp]?mod(?![a-zA-Z])")


def _translate_mod(tex: str) -> str:
    """mathtext has no \\bmod, \\mod or \\pmod; rewrite them with \\mathrm{mod}."""
    tex = _PMOD_RE.sub(r"\\ (\\mathrm{mod}\\ \1)", tex)
    return _MOD_RE.sub(r"\\ \\mathrm{mod}\\ ", tex)


def render_formula(
    tex: str,
    out_png: str | PathLike,
    *,
    fontsize: int = 16,
    dpi: int = 150,
    color: str = "black",
) -> Path:
    """Render ``tex`` (with or without surrounding $...$) to the PNG ``out_png``.

    Parent folders are created if needed. Returns the output path.
    Raises ValueError if mathtext cannot parse the formula.
    """
    tex = _translate_mod(tex.strip())
    if not tex:
        raise ValueError("empty formula")
    if not (tex.startswith("$") and tex.endswith("$") and len(tex) > 1):
        tex = f"${tex}$"

    out = Path(out_png)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        math_to_image(tex, out, prop=FontProperties(size=fontsize), dpi=dpi,
                      format="png", color=color)
    except Exception as exc:  # mathtext raises ValueError/ParseException variants
        raise ValueError(f"could not render formula {tex!r}: {exc}") from exc
    return out
