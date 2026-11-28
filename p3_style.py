"""Shared SignTab and TraceViewer styling added to the app theme once.

Keeping these rules in the application stylesheet avoids reparsing the same
large stylesheet for every TraceViewer whenever the theme changes.
"""

P3_STYLE = """

/* P3 Sign page */
QWidget#signTab, QWidget#signPage {{ background: {window}; color: {text}; font-family: Georgia; }}
QLabel#signHeading {{ color: {text}; font-size: 20pt; font-weight: 600; padding: 4px 2px; }}
QLabel#signIntro {{ color: {muted}; font-size: 11pt; padding-bottom: 4px; }}
QWidget#signPage QGroupBox {{
    background: {panel}; color: {text}; border: 1px solid {border}; border-radius: 14px;
    margin-top: 18px; padding: 16px 14px 14px 14px; font-weight: 600;
}}
QWidget#signPage QGroupBox#advancedCard {{ background: {pink}; color: {pastel_text}; }}
QWidget#signPage QGroupBox#resultCard {{ background: {lilac}; color: {pastel_text}; }}
QWidget#signPage QGroupBox#traceCard {{ background: {panel}; }}
QWidget#signPage QGroupBox#emptyCard {{ background: {peach}; color: {pastel_text}; }}
QWidget#signPage QGroupBox::title {{
    subcontrol-origin: margin; left: 18px; padding: 0 7px; color: {text}; background: transparent;
    font-family: Georgia;
}}
QWidget#signPage QGroupBox#encodingCard {{
    background: {panel}; border-radius: 12px; margin-top: 0; padding: 8px;
}}
QLabel#encodingHeading {{ color: {pastel_text}; font-family: Georgia; font-size: 11pt; font-weight: 700; padding: 3px 0 0 8px; }}
QWidget#signPage QPushButton {{
    border: 1px solid {border}; border-radius: 10px; padding: 7px 16px; background: {input}; color: {text};
}}
QWidget#signPage QPushButton:hover {{ border-color: {accent}; background: {hover}; }}
QWidget#signPage QPushButton[primary="true"] {{
    background: {accent}; color: {accent_text}; border-color: {accent};
    font-size: 12pt; font-weight: 600;
}}
QWidget#signPage QPushButton[primary="true"]:hover {{ background: {accent_hover}; }}
QWidget#signPage QPlainTextEdit, QWidget#signPage QLineEdit, QWidget#signPage QComboBox {{
    background: {surface}; color: {text}; border: 1px solid {border}; border-radius: 10px; padding: 6px 9px;
}}
QWidget#signPage QPlainTextEdit#signMessageInput {{ background: {input}; color: {text}; }}
QWidget#signPage QLabel, QWidget#signPage QRadioButton {{ background: transparent; font-family: Georgia; }}
QWidget#signPage QPushButton, QWidget#signPage QComboBox {{ font-family: Georgia; }}
QWidget#signPage QComboBox {{ padding-right: 36px; }}
QWidget#signPage QComboBox::drop-down {{ width: 36px; border: 0; background: transparent; }}
QWidget#signPage QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
QWidget#signPage QPlainTextEdit:focus, QWidget#signPage QLineEdit:focus,
QWidget#signPage QComboBox:focus {{ border: 2px solid {accent}; }}
QWidget#signPage QRadioButton {{ color: {text}; spacing: 7px; }}

/* P3 TraceViewer */
QWidget#traceViewer {{ background: transparent; color: {p3_text}; font-family: Georgia; }}
QWidget#traceViewer QLabel, QWidget#traceViewer QPushButton,
QWidget#traceViewer QToolButton {{ font-family: Georgia; }}
QScrollArea#traceScroll, QScrollArea#traceScroll > QWidget > QWidget {{ background: transparent; border: 0; }}
QFrame#traceStepCard {{ background: {p3_card}; border: 1px solid {p3_border}; border-radius: 13px; }}
QLabel#stepNumberBadge {{
    background: {accent}; color: {accent_text}; border: 0; border-radius: 15px;
    font-size: 11pt; font-weight: 700;
}}
QLabel#stepTitle {{ color: {pastel_text}; font-size: 11pt; font-weight: 600; }}
QToolButton#stepDetailsButton {{
    color: {heading}; background: transparent; border: 0; padding: 6px 8px;
    font-weight: 600;
}}
QToolButton#stepDetailsButton:hover {{ background: {hover}; border-radius: 8px; }}
QLabel#traceFormula {{
    color: {p3_value}; background: {p3_inner}; border: 1px solid {p3_border}; border-radius: 9px; padding: 11px 13px;
}}
QFrame#traceValues {{ background: {p3_inner}; border: 1px solid {p3_border}; border-radius: 9px; padding: 3px; }}
QLabel#traceValueHeader {{
    color: {p3_muted}; background: {p3_inner}; border: 0; border-bottom: 1px solid {p3_border};
    padding: 7px; font-family: Georgia; font-weight: 600;
}}
QLabel[variableName="true"] {{
    color: {p3_variable}; background: {p3_inner}; border: 0; border-top: 1px solid {p3_border};
}}
QLabel[traceValue="true"] {{
    color: {p3_value}; background: {p3_inner}; border: 0; border-top: 1px solid {p3_border};
}}
QLabel[alternate="true"] {{ background: {p3_row}; }}
QWidget#traceViewer QPushButton {{
    color: {text}; background: {panel}; border: 1px solid {border};
    border-radius: 9px; padding: 7px 13px;
}}
QWidget#traceViewer QPushButton:hover {{ color: {heading}; border-color: {accent}; background: {hover}; }}
QWidget#traceViewer QPushButton#tracePrimaryButton {{ background: {accent}; color: {accent_text}; border-color: {accent}; }}
QWidget#traceViewer QPushButton:disabled {{ color: {disabled_text}; background: {disabled}; }}
QWidget#traceViewer QPushButton#numberFormatToggle:checked {{
    color: {accent_text}; background: {accent}; border-color: {accent};
}}
QLabel#traceStepCount {{ color: {muted}; }}

/* Modern scrollbars for the Sign page and every TraceViewer instance. */
QWidget#signTab QScrollBar:vertical, QWidget#traceViewer QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 3px; border: 0;
}}
QWidget#signTab QScrollBar::handle:vertical, QWidget#traceViewer QScrollBar::handle:vertical {{
    background: {p3_border}; min-height: 36px; border-radius: 4px;
}}
QWidget#signTab QScrollBar::add-line:vertical, QWidget#signTab QScrollBar::sub-line:vertical,
QWidget#traceViewer QScrollBar::add-line:vertical, QWidget#traceViewer QScrollBar::sub-line:vertical {{
    height: 0; border: 0; background: transparent;
}}
QWidget#signTab QScrollBar::add-page:vertical, QWidget#signTab QScrollBar::sub-page:vertical,
QWidget#traceViewer QScrollBar::add-page:vertical, QWidget#traceViewer QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QWidget#signTab QScrollBar::up-arrow:vertical, QWidget#signTab QScrollBar::down-arrow:vertical,
QWidget#traceViewer QScrollBar::up-arrow:vertical, QWidget#traceViewer QScrollBar::down-arrow:vertical {{
    width: 0; height: 0; image: none;
}}
"""

__all__ = ["P3_STYLE"]
