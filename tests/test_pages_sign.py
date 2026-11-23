"""pytest-qt tests for Learn steps 3-5 (P4). Skipped without PySide6 and pytest-qt."""
from __future__ import annotations

import importlib.util

import pytest

HAS_QT = all(importlib.util.find_spec(m) for m in ("PySide6", "pytestqt"))
pytestmark = pytest.mark.skipif(not HAS_QT, reason="needs PySide6 and pytest-qt")


@pytest.mark.parametrize("curve_name", ["toy-17", "secp256k1"])
def test_steps_3_to_5_then_verify(qtbot, curve_name):
    from ecdsa_edu.core.curves_registry import get_curve
    from ecdsa_edu.core.types import PublicKey, Signature
    from ecdsa_edu.core.verify import verify
    from ecdsa_edu.gui.learn.pages_sign import PAGES
    from ecdsa_edu.gui.learn.wizard import LearnState

    st = LearnState(get_curve(curve_name))
    pages = [cls() for cls in PAGES]
    for page in pages:
        qtbot.addWidget(page)
        page.enter(st)  # in walkthrough order, like the wizard

    n = st.curve.n
    assert st.e is not None and st.d is not None and st.Q is not None
    assert 1 <= st.k < n and st.R is not None
    assert 1 <= st.r < n and 1 <= st.s < n
    # the signature the walkthrough built is a real, valid ECDSA signature
    assert verify(PublicKey(st.Q, st.curve), st.msg, Signature(st.r, st.s))


def test_choosing_another_k_changes_r(qtbot):
    from ecdsa_edu.core.curves_registry import get_curve
    from ecdsa_edu.gui.learn.pages_sign import NoncePage
    from ecdsa_edu.gui.learn.wizard import LearnState

    st = LearnState(get_curve("toy-17"))
    page = NoncePage()
    qtbot.addWidget(page)
    page.enter(st)
    seen = set()
    for k in range(1, st.curve.n):
        page.k_box.setValue(k)
        assert st.k == k
        if st.r is not None:
            seen.add(st.r)
    assert len(seen) > 3  # different k give different r


@pytest.mark.parametrize("curve_name", ["toy-17", "secp256k1"])
def test_default_k_is_rfc6979(qtbot, curve_name):
    """By default the walkthrough signs exactly like the Sign page: RFC 6979 k, same (r, s)."""
    from ecdsa_edu.core.curves_registry import get_curve
    from ecdsa_edu.core.sign import sign
    from ecdsa_edu.core.types import PrivateKey
    from ecdsa_edu.gui.learn.pages_sign import PAGES
    from ecdsa_edu.gui.learn.wizard import LearnState

    st = LearnState(get_curve(curve_name))
    for cls in PAGES:
        page = cls()
        qtbot.addWidget(page)
        page.enter(st)
    expected = sign(PrivateKey(st.d, st.curve), st.msg)  # deterministic (RFC 6979) by default
    assert st["k_source"] == "rfc6979"
    assert (st.r, st.s) == (expected.r, expected.s)

    # trying another k and coming back restores the RFC 6979 signature
    nonce = next(p for p in [cls() for cls in PAGES] if type(p).__name__ == "NoncePage")
    qtbot.addWidget(nonce)
    nonce.enter(st)
    nonce.random_button.click()
    assert st["k_source"] == "chosen"
    nonce.rfc_button.click()
    assert st["k_source"] == "rfc6979" and (st.r, st.s) == (expected.r, expected.s)
