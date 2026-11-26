"""Tests for the Learn ECDSA reading (P4): formula rendering, the "Go deeper" pages and the stepper.

The former Theory page was merged into Learn ECDSA; these tests make sure its
content is still reachable there."""
from __future__ import annotations

import pytest

import re

from ecdsa_edu.gui.learn.formula import render_formula
from ecdsa_edu.gui.learn.reading import READING_DIR


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


READING_FILES = ["curve.html", "keys.html", "verify.html", "pitfalls.html", "glossary.html"]


@pytest.mark.parametrize("name", READING_FILES)
def test_reading_files_exist_and_their_images_too(name):
    text = (READING_DIR / name).read_text(encoding="utf-8")
    assert len(text) > 500
    for image in re.findall(r'src="([^"]+)"', text):
        assert (READING_DIR / image).is_file(), image
    assert "Theory" not in text and not re.search(r"tab", text)  # no references to the removed page


def test_private_key_is_never_described_as_saved():
    text = (READING_DIR / "keys.html").read_text(encoding="utf-8")
    assert "never saved" in text


def test_every_reading_file_is_used_by_a_learn_step(qtbot):
    from ecdsa_edu.gui.learn.wizard import LearnTab
    tab = LearnTab(None)
    qtbot.addWidget(tab)
    used = {page.reading for page in tab.pages if page.reading}
    assert used == set(READING_FILES)
    # the merged Theory topics are all present somewhere in the walkthrough
    everything = " ".join((READING_DIR / name).read_text(encoding="utf-8") for name in READING_FILES)
    for topic in ("Point doubling", "Double-and-add", "ECDLP", "SEC 1", "range check", "Reusing the nonce k",
                  "Malleability", "RFC 6979"):
        assert topic.lower() in everything.lower(), topic


def test_stepper_shows_the_reading_order_and_jumps(qtbot):
    from ecdsa_edu.gui.learn.wizard import LearnTab
    tab = LearnTab(None)
    qtbot.addWidget(tab)
    tab.resize(1024, 700)
    tab.show()
    labels = [b.text() for b in tab.stepper.buttons]
    assert len(labels) == len(tab.pages) == tab.total == 9
    assert labels[0].startswith("1") and "curve" in labels[0].lower()
    assert [lab.split("  ", 1)[1] for lab in labels[-3:]] == ["Pitfalls", "Quiz", "Glossary"]
    assert tab.stepper.current() == 0 and tab.stepper.buttons[0].isChecked()

    tab.stepper.buttons[5].click()  # straight to "Verify": the skipped steps run first
    assert tab.index == 5 and tab.stepper.current() == 5
    assert tab.st.valid is True
    tab.next_btn.click()
    assert tab.index == 6 and tab.stepper.buttons[6].isChecked()
    tab.back_btn.click()
    assert tab.index == 5 and tab.back_btn.text().endswith("Previous")
    # the row fits or scrolls sideways; it never makes the page wider than the window
    assert tab.stepper.minimumSizeHint().width() < 1024


def test_go_deeper_section_opens_and_fits_its_text(qtbot):
    from ecdsa_edu.gui.learn.wizard import LearnTab
    tab = LearnTab(None)
    qtbot.addWidget(tab)
    tab.resize(1024, 700)
    tab.show()
    page = tab.pages[0]
    assert page.reading_view.isHidden()
    page.reading_toggle.click()
    qtbot.wait(20)
    assert page.reading_view.isVisible()
    view = page.reading_view
    assert view.verticalScrollBar().maximum() == 0  # no inner scrollbar: it grows instead
    assert view.height() > 400
    pitfalls = tab.pages[6]
    assert getattr(pitfalls, "reading_toggle", None) is None  # reading-only steps show it straight away
