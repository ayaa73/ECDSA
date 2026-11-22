"""Theory tab (P4): a table of contents on the left, the selected page on the right.

Pages live in gui/theory/pages/NN_slug.html and are picked up automatically,
so teammates only drop in an HTML file. Images (e.g. formulas made with
formula.render_formula) are resolved relative to the pages folder, so
<img src="img/sign.png"> works.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ecdsa_edu.gui.theory.toc import PAGES_DIR, TheoryPage, discover_pages

PAGE_CSS = """
body  { font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; font-size: 11pt; color: #222; }
h1    { font-size: 20pt; color: #1f3a5f; margin-bottom: 6px; }
h2    { font-size: 14pt; color: #1f3a5f; margin-top: 18px; }
code, pre { font-family: Consolas, 'Courier New', monospace; background: #f3f5f8; }
pre   { padding: 8px; }
.note { background: #fff8e1; border-left: 4px solid #f2b705; padding: 6px 10px; }
.warn { background: #fdecea; border-left: 4px solid #d93025; padding: 6px 10px; }
table { border-collapse: collapse; }
td, th { border: 1px solid #ccd; padding: 4px 8px; }
th    { background: #e8edf4; }
"""

EMPTY_HTML = """
<h1>Theory</h1>
<p>No theory pages yet. Add a file named <code>NN_slug.html</code> to
<code>gui/theory/pages/</code> (with an &lt;h1&gt; title) and it will appear here.</p>
"""


class TheoryTab(QWidget):
    """Read-only ECDSA theory notes. Does not depend on the selected curve."""

    HELP = ("Short reading pages on the ideas behind the app: elliptic curves, keys, signing, why verification "
            "works, the classic mistakes and a glossary. Pick a page from the list on the left.")

    def __init__(self, state=None, pages_dir: Path | str = PAGES_DIR) -> None:
        super().__init__()
        self.state = state
        self.pages_dir = Path(pages_dir)
        self.pages: list[TheoryPage] = []

        self.toc = QListWidget()
        self.toc.setMinimumWidth(200)
        self.toc.currentRowChanged.connect(self._show_row)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.document().setDefaultStyleSheet(PAGE_CSS)
        self.browser.setSearchPaths([str(self.pages_dir)])

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        heading = QLabel("<b>Contents</b>")
        left_layout.addWidget(heading)
        left_layout.addWidget(self.toc)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(self.browser)
        splitter.setStretchFactor(1, 1)

        layout = QHBoxLayout(self)
        layout.addWidget(splitter)

        self.reload()

    def reload(self) -> None:
        """Re-scan the pages folder (handy while teammates are writing pages)."""
        self.pages = discover_pages(self.pages_dir)
        self.toc.blockSignals(True)
        self.toc.clear()
        for page in self.pages:
            item = QListWidgetItem(f"{page.number:02d}. {page.title}")
            item.setToolTip(page.path.name)
            self.toc.addItem(item)
        self.toc.blockSignals(False)

        if self.pages:
            self.toc.setCurrentRow(0)
            self._show_row(0)
        else:
            self.browser.setHtml(EMPTY_HTML)

    def _show_row(self, row: int) -> None:
        if 0 <= row < len(self.pages):
            html = self.pages[row].path.read_text(encoding="utf-8", errors="replace")
            self.browser.setHtml(html)

    def set_curve(self, curve) -> None:
        """Part of the tab contract. Theory pages don't change with the curve."""
