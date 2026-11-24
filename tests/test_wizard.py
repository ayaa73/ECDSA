"""Tests for the Learn wizard (P4).

The model tests are pure Python. The Qt tests need PySide6 + pytest-qt and
are skipped without them.
"""
from __future__ import annotations

import importlib.util
import types

import pytest

from ecdsa_edu.gui.learn.model import (
    LEARN_KEYS,
    PAGE_MODULES,
    LearnState,
    load_page_modules,
    step_count,
)


# --- LearnState --------------------------------------------------------------
def test_state_has_all_contract_keys():
    st = LearnState("toy")
    assert set(LEARN_KEYS) <= set(st)
    assert st["curve"] == "toy" and st["msg"] == b"Hello, ECDSA!"
    assert st["d"] is None


def test_state_attribute_access():
    st = LearnState()
    st.d = 7
    assert st["d"] == 7 and st.d == 7
    with pytest.raises(AttributeError):
        _ = st.not_a_key


def test_state_reset_keeps_message():
    st = LearnState("toy", msg=b"hi", d=7, r=3)
    st.reset("real")
    assert st.curve == "real" and st.msg == b"hi" and st.d is None and st.r is None


# --- module loading ------------------------------------------------------------
def fake_importer(available: dict[str, object]):
    def imp(name: str):
        short = name.rsplit(".", 1)[-1]
        if short in available:
            obj = available[short]
            if isinstance(obj, Exception):
                raise obj
            return obj
        err = ModuleNotFoundError(f"No module named {name!r}")
        err.name = name
        raise err
    return imp


def test_all_missing_gives_seven_coming_soon_steps():
    loaded = load_page_modules(importer=fake_importer({}))
    assert [m.spec.module for m in loaded] == ["pages_curve", "pages_keys", "pages_sign", "pages_verify"]
    assert all(m.pages is None for m in loaded)
    assert step_count(loaded) == 7
    assert "not written yet" in loaded[0].error


def test_loaded_module_uses_real_page_count():
    keys_mod = types.SimpleNamespace(PAGES=[object, object])  # 2 pages instead of the expected 1
    loaded = load_page_modules(importer=fake_importer({"pages_keys": keys_mod}))
    assert loaded[1].pages == [object, object]
    assert step_count(loaded) == 8


def test_missing_dependency_and_broken_module_are_reported():
    dep = ModuleNotFoundError("No module named 'ecdsa_edu.core.sign'")
    dep.name = "ecdsa_edu.core.sign"
    loaded = load_page_modules(importer=fake_importer({
        "pages_sign": dep,
        "pages_verify": RuntimeError("boom"),
        "pages_curve": types.SimpleNamespace(),  # no PAGES
    }))
    assert "ecdsa_edu.core.sign" in loaded[2].error
    assert "boom" in loaded[3].error
    assert "no PAGES" in loaded[0].error


def test_page_modules_order_matches_contract():
    assert sum(m.expected_steps for m in PAGE_MODULES) == 7


# --- Qt: the real tab ---------------------------------------------------------
HAS_QT = all(importlib.util.find_spec(m) for m in ("PySide6", "pytestqt"))
needs_qt = pytest.mark.skipif(not HAS_QT, reason="needs PySide6 and pytest-qt")


@needs_qt
def test_learn_tables_scroll_without_squeezing(qtbot):
    from ecdsa_edu.gui.learn.wizard import LearnTab

    tab = LearnTab(None)
    qtbot.addWidget(tab)
    tab.resize(900, 600)
    tab.show()
    qtbot.waitUntil(lambda: tab._page_scrolls[tab.pages[0]].verticalScrollBar().maximum() > 0)
    page = tab.pages[0]
    assert page.values_table.height() >= 180
    assert page.table.height() >= 180
    page.set_values({"large value": "a" * 300})
    qtbot.waitUntil(lambda: page.values_table.horizontalScrollBar().maximum() > 0)


@needs_qt
def test_wizard_opens_and_navigates(qtbot):
    from ecdsa_edu.gui.learn.wizard import LearnTab

    tab = LearnTab(None)
    qtbot.addWidget(tab)
    assert tab.index == 0
    assert tab.step_label.text().startswith(f"Step 1 of {tab.total}")
    assert not tab.back_btn.isEnabled()

    tab.next_btn.click()
    assert tab.index == 1 and tab.step_label.text().startswith("Step 2 of")
    tab.back_btn.click()
    assert tab.index == 0

    for _ in range(20):
        tab.next_btn.click()
    assert tab.index == len(tab.pages) - 1
    assert not tab.next_btn.isEnabled()


@needs_qt
def test_wizard_curve_toggle_does_not_crash(qtbot):
    from ecdsa_edu.gui.learn.wizard import LearnTab

    tab = LearnTab(None)
    qtbot.addWidget(tab)
    tab.next_btn.click()
    tab.real_size.setChecked(True)
    assert tab.index == 1
    tab.real_size.setChecked(False)
    assert tab.index == 1


# --- Step 7 quiz content (pure) ------------------------------------------------
from ecdsa_edu.gui.learn.quiz import QUIZ, check_answer  # noqa: E402


def test_quiz_has_three_questions_each_with_one_answer():
    assert len(QUIZ) == 3
    for q in QUIZ:
        assert sum(c.correct for c in q.choices) == 1
        assert all(c.feedback for c in q.choices)


def test_check_answer():
    q = QUIZ[0]
    ok, text = check_answer(q, q.answer_index)
    assert ok and text
    wrong = next(i for i in range(len(q.choices)) if i != q.answer_index)
    assert check_answer(q, wrong)[0] is False


# --- Steps 6-7 in Qt -------------------------------------------------------------
@needs_qt
def test_quiz_page_feedback_and_score(qtbot):
    from ecdsa_edu.gui.learn.pages_verify import QuizPage

    page = QuizPage()
    qtbot.addWidget(page)
    for qi, q in enumerate(QUIZ):
        page.groups[qi].button(q.answer_index).click()
    assert "Score: 3 / 3" in page.score_label.text()
    assert "Correct" in page.feedback[0].text()


@needs_qt
def test_verify_page_valid(qtbot):
    pytest.importorskip("ecdsa_edu.core.curves_registry")
    pytest.importorskip("ecdsa_edu.core.sign")
    pytest.importorskip("ecdsa_edu.core.keys")
    from ecdsa_edu.core.curves_registry import get_curve
    from ecdsa_edu.gui.learn.pages_verify import VerifyPage

    page = VerifyPage()
    qtbot.addWidget(page)
    st = LearnState(get_curve("toy-17"))
    page.enter(st)
    assert st.valid is True and st.w is not None and st.u1 is not None
