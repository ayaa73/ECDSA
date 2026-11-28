"""Let labels wrap long numbers instead of growing wider than the window.

A QLabel with word wrap only breaks lines at spaces, so one 64-digit hex key
or 78-digit coordinate sets the label's minimum width and can push a whole
page sideways. ``soft_wrap`` inserts invisible break points (zero-width
spaces) into every long run of characters without spaces.
"""
from __future__ import annotations

import re

__all__ = ["ZWSP", "soft_wrap", "unwrap"]

ZWSP = "​"  # zero-width space: an invisible place where a line may break


def soft_wrap(text: str, width: int = 16) -> str:
    """Break every run of more than ``2 * width`` non-space characters every ``width`` characters."""
    def split(match: re.Match[str]) -> str:
        word = match.group(0)
        return ZWSP.join(word[index:index + width] for index in range(0, len(word), width))
    return re.sub(r"[^\s<>]{%d,}" % (width * 2 + 1), split, text)


def unwrap(text: str) -> str:
    """Remove the break points again (e.g. before copying)."""
    return text.replace(ZWSP, "")
