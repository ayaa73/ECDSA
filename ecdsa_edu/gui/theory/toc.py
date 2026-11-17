"""Table of contents for the Theory tab (P4). Pure Python, no Qt, so it is easy to test.

Each Theory page is ``pages/NN_slug.html``. Pages are sorted by their NN
prefix and titled by their first <h1>. Ownership: 01-03 P1, 04-05 P2,
06-07 P3, 08-10 P4.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

PAGES_DIR = Path(__file__).parent / "pages"

_NAME_RE = re.compile(r"^(\d+)_([\w-]+)\.html?$", re.IGNORECASE)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class TheoryPage:
    number: int
    slug: str
    title: str
    path: Path


def page_title(path: Path) -> str:
    """Text of the first <h1>, or a title made from the slug if there is none."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    m = _H1_RE.search(text)
    if m:
        title = html.unescape(_TAG_RE.sub("", m.group(1))).strip()
        if title:
            return " ".join(title.split())
    slug = _NAME_RE.match(path.name)
    base = slug.group(2) if slug else path.stem
    return base.replace("_", " ").replace("-", " ").capitalize()


def discover_pages(pages_dir: Path | str = PAGES_DIR) -> list[TheoryPage]:
    """All NN_slug.html files in ``pages_dir``, sorted by NN. Other files are ignored."""
    d = Path(pages_dir)
    if not d.is_dir():
        return []
    pages = []
    for p in d.iterdir():
        m = _NAME_RE.match(p.name)
        if p.is_file() and m:
            pages.append(TheoryPage(int(m.group(1)), m.group(2), page_title(p), p))
    pages.sort(key=lambda pg: (pg.number, pg.slug))
    return pages
