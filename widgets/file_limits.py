"""The one size limit for files that are signed or verified (Sign and Verify pages).

Any file type is allowed; only the size is limited, so hashing stays quick and
the app stays responsive.
"""
from __future__ import annotations

import os

__all__ = ["MAX_FILE_BYTES", "FILE_LIMIT_TEXT", "format_size", "file_size_problem"]

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
FILE_LIMIT_TEXT = "Any file type · max 10 MB"


def format_size(size: int) -> str:
    """A file size in words people read easily: 512 bytes, 3.4 KB, 12.6 MB."""
    if size < 1024:
        return f"{size} bytes"
    value, unit = (size / 1024, "KB") if size < 1024 * 1024 else (size / (1024 * 1024), "MB")
    return f"{value:.1f}".rstrip("0").rstrip(".") + f" {unit}"


def file_size_problem(path: str | os.PathLike[str]) -> str:
    """'' if the file can be used, otherwise a sentence explaining why not."""
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        return f"The file could not be read: {exc.strerror or exc}."
    if size > MAX_FILE_BYTES:
        return (f"This file is {format_size(size)}, which is more than the limit of "
                f"{format_size(MAX_FILE_BYTES)}. Please choose a smaller file.")
    return ""
