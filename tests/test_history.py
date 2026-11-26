"""Tests for the History page (P4): the milestone data (plain Python) and the page (pytest-qt)."""
from __future__ import annotations

import importlib.util

import pytest

from ecdsa_edu.gui.tabs.history_data import CATEGORIES, MILESTONES, filter_milestones

HAS_QT = all(importlib.util.find_spec(m) for m in ("PySide6", "pytestqt"))
needs_qt = pytest.mark.skipif(not HAS_QT, reason="needs PySide6 and pytest-qt")
PAGES = {"Start here", "Keys", "Sign", "Verify", "Curve Explorer", "Learn ECDSA", "Attack Demo", "History"}


def test_every_milestone_is_complete_and_sourced():
    assert 12 <= len(MILESTONES) <= 15
    for m in MILESTONES:
        assert 1970 <= m.year <= 2026
        assert m.category in CATEGORIES
        assert m.title and m.story and m.why_it_matters and m.source_title
        assert m.source_url.startswith("https://")
        assert m.page is None or m.page in PAGES


def test_milestones_are_in_order_and_cover_every_category():
    years = [m.year for m in MILESTONES]
    assert years == sorted(years)
    assert {m.category for m in MILESTONES} == set(CATEGORIES)


def test_filter():
    attacks = filter_milestones({"attack"})
    assert attacks and all(m.category == "attack" for m in attacks)
    assert filter_milestones(set()) == []
    assert filter_milestones(set(CATEGORIES)) == list(MILESTONES)


@needs_qt
def test_history_page(qtbot):
    from ecdsa_edu.gui.tabs.history_tab import HistoryTab
    tab = HistoryTab(None)
    qtbot.addWidget(tab)
    assert len(tab.items) == len(MILESTONES)
    assert str(MILESTONES[0].year) in tab.detail_title.text()

    tab.next_button.click()
    assert tab.index == 1

    for key, box in tab.chips.items():  # show attacks only
        box.setChecked(key == "attack")
    assert tab.items and all(m.category == "attack" for m in tab.items)
    assert tab.current().source_url in tab.source.text()

    ps3 = next(i for i, m in enumerate(tab.items) if m.page == "Attack Demo")
    tab.select(ps3)
    assert "Attack Demo" in tab.see_label.text() and not tab.see_label.isHidden()

    for box in tab.chips.values():
        box.setChecked(False)
    assert tab.current() is None and not tab.next_button.isEnabled()
    tab.strip.grab()  # paints without errors
