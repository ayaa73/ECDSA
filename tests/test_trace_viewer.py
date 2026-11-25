"""Focused GUI tests for P3's TraceViewer."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication

from ecdsa_edu.core.trace import TraceStep
from ecdsa_edu.gui.widgets.trace_viewer import TraceViewer


def sample_trace():
    return [
        TraceStep("Hash", "e = H(message)", {"e": "26", "bits": "5"}),
        TraceStep("Point", "R = kG", {"k": "10", "R": "(7, 11)"}),
        TraceStep("Signature", "s = k^-1(e + r*d) mod n", {"d": "7", "s": "17"}),
    ]


def test_empty_state_then_set_trace(qtbot):
    viewer = TraceViewer()
    qtbot.addWidget(viewer)
    assert viewer.empty_label.isVisibleTo(viewer)
    assert not viewer.copy_button.isEnabled()

    viewer.set_trace(sample_trace())
    viewer.show()
    qtbot.wait(20)
    assert len(viewer._panels) == 3
    assert viewer.step_label.text() == "3 steps"
    assert viewer.scroll.verticalScrollBar().value() == 0
    assert viewer.copy_button.isEnabled()
    assert all(panel.isVisibleTo(viewer) for panel in viewer._panels)


def test_step_through_navigation_and_show_all(qtbot):
    viewer = TraceViewer()
    qtbot.addWidget(viewer)
    viewer.set_trace(sample_trace())

    viewer.step_through_button.click()
    assert viewer.step_label.text() == "Step 1 of 3"
    assert viewer._panels[0].isVisibleTo(viewer)
    assert not viewer._panels[1].isVisibleTo(viewer)
    assert not viewer.previous_button.isEnabled()
    assert viewer.next_button.isEnabled()

    viewer.next_button.click()
    assert viewer.step_label.text() == "Step 2 of 3"
    assert viewer.previous_button.isEnabled()
    viewer.previous_button.click()
    assert viewer.step_label.text() == "Step 1 of 3"

    viewer.show_all_button.click()
    assert viewer.step_label.text() == "3 steps"
    assert all(panel.isVisibleTo(viewer) for panel in viewer._panels)


def test_panels_expand_and_long_values_wrap(qtbot):
    viewer = TraceViewer()
    qtbot.addWidget(viewer)
    long_value = "9" * 180
    viewer.resize(520, 500)
    viewer.set_trace([TraceStep("Long number", "value = result", {"value": long_value})])
    viewer.show()
    qtbot.wait(20)
    panel = viewer._panels[0]
    assert panel.values_table.wordWrap()
    assert panel.values_table.item(0, 1).text().replace("\u200b", "") == long_value
    assert panel.values_table.rowHeight(0) > 24

    panel.toggle.click()
    assert not panel.details.isVisibleTo(viewer)
    panel.toggle.click()
    assert panel.details.isVisibleTo(viewer)


def test_decimal_hex_toggle_and_private_key_redaction(qtbot):
    viewer = TraceViewer()
    qtbot.addWidget(viewer)
    viewer.set_trace([TraceStep("Values", "r = x mod n", {"r": "17", "d": "7", "point": "(7, 11)"})])
    panel = viewer._panels[0]
    assert panel.values_table.item(0, 1).text() == "17"
    assert panel.values_table.item(1, 1).text() == "(hidden)"

    viewer.hex_toggle.click()
    assert panel.values_table.item(0, 1).text() == "0x11"
    assert panel.values_table.item(1, 1).text() == "(hidden)"
    assert panel.values_table.item(2, 1).text() == "(7, 11)"


def test_variable_names_use_teaching_font_and_values_stay_fixed_width(qtbot):
    viewer = TraceViewer()
    qtbot.addWidget(viewer)
    viewer.set_trace([TraceStep("Values", "r = x mod n", {"r": "17"})])

    name_item = viewer._panels[0].values_table.item(0, 0)
    value_item = viewer._panels[0].values_table.item(0, 1)
    assert name_item.font().bold()
    assert name_item.font().family() == QApplication.font().family()
    assert value_item.font().fixedPitch()
    assert viewer.hex_toggle.objectName() == "numberFormatToggle"


def test_number_format_button_explains_the_next_action(qtbot):
    viewer = TraceViewer()
    qtbot.addWidget(viewer)
    viewer.set_trace([TraceStep("Values", "r = x mod n", {"r": "17"})])

    assert viewer.hex_toggle.text() == "Show numbers in hex"
    viewer.hex_toggle.click()
    assert viewer.hex_toggle.text() == "Show numbers in decimal"
    assert viewer._panels[0].values_table.item(0, 1).text() == "0x11"
    viewer.hex_toggle.click()
    assert viewer.hex_toggle.text() == "Show numbers in hex"
    assert viewer._panels[0].values_table.item(0, 1).text() == "17"


def test_copy_as_text_uses_visible_number_base_and_hides_d(qtbot):
    viewer = TraceViewer()
    qtbot.addWidget(viewer)
    viewer.set_trace(sample_trace())
    viewer.hex_toggle.setChecked(True)
    viewer.copy_button.click()

    copied = QApplication.clipboard().text()
    assert "Step 1: Hash" in copied
    assert "e: 0x1a" in copied
    assert "d: (hidden)" in copied
    assert "d: 7" not in copied
    assert viewer.copy_button.text().startswith("Copied")


def test_replacing_trace_removes_old_panels(qtbot):
    viewer = TraceViewer()
    qtbot.addWidget(viewer)
    viewer.set_trace(sample_trace())
    viewer.set_trace([TraceStep("Only step", "x = 1", {"x": "1"})])
    assert len(viewer._panels) == 1
    assert viewer._panels[0].title_label.text() == "Only step"
    assert viewer._panels[0].toggle.text() == "Hide details"


def test_internal_digest_name_is_student_friendly(qtbot):
    viewer = TraceViewer()
    qtbot.addWidget(viewer)
    viewer.set_trace([
        TraceStep("Hash", "digest = HASH(data)", {"digest": "abcd", "digest_bits": "256"})
    ])

    assert viewer._panels[0].display_rows() == [
        ("Hash output", "abcd"),
        ("Hash output size (bits)", "256"),
    ]
    assert viewer._panels[0].title_label.text() == "Hash"


def test_digest_word_is_rewritten_in_visible_explanation(qtbot):
    viewer = TraceViewer()
    qtbot.addWidget(viewer)
    viewer.set_trace([
        TraceStep(
            "Convert the digest to an integer",
            "e = the leftmost bits of the digest",
            {},
        )
    ])

    panel = viewer._panels[0]
    assert panel.title_label.text() == "Convert the hash output to an integer"
    assert panel.formula_label.text() == "e = the leftmost bits of the hash output"
