"""Tests for the Theory tab helpers (P4): formula rendering and the table of contents."""
from __future__ import annotations

import pytest

from ecdsa_edu.gui.theory.formula import render_formula
from ecdsa_edu.gui.theory.toc import discover_pages


def test_render_formula_creates_png(tmp_path):
    out = render_formula(r"u_1 G + u_2 Q = (e + r d)\, s^{-1} G = k G", tmp_path / "img" / "v.png")
    assert out.exists()
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_formula_accepts_dollars(tmp_path):
    assert render_formula(r"$w = s^{-1} \bmod n$", tmp_path / "w.png").exists()


@pytest.mark.parametrize("tex", [r"a \mod n", r"s \equiv k^{-1}(e + rd) \pmod{n}", r"x_1 \bmod n = r"])
def test_render_formula_mod_variants(tmp_path, tex):
    assert render_formula(tex, tmp_path / "m.png").exists()


@pytest.mark.parametrize("bad", ["", "   ", r"\frac{1}{", r"x^{"])
def test_render_formula_bad_input(tmp_path, bad):
    with pytest.raises(ValueError):
        render_formula(bad, tmp_path / "bad.png")


def test_discover_pages_sorted_and_titled(tmp_path):
    (tmp_path / "10_glossary.html").write_text("<h1>Glossary</h1>")
    (tmp_path / "02_group_law.html").write_text("<html><h1 class='t'>The <i>group</i> law</h1></html>")
    (tmp_path / "08_why_verify_works.html").write_text("<p>no heading</p>")
    (tmp_path / "notes.txt").write_text("ignored")
    (tmp_path / "img").mkdir()

    pages = discover_pages(tmp_path)
    assert [p.number for p in pages] == [2, 8, 10]
    assert [p.title for p in pages] == ["The group law", "Why verify works", "Glossary"]


def test_discover_pages_missing_dir(tmp_path):
    assert discover_pages(tmp_path / "nope") == []
