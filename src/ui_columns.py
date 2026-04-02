"""Shared three-column layout constants and formatting helpers."""

import shutil
from dataclasses import dataclass
from typing import Optional


COLUMN_PADDING = 1
COLUMN_SEPARATOR = "│"
USER_COLUMN_RATIO = 0.18
POSTS_COLUMN_RATIO = 0.32


@dataclass(frozen=True)
class ColumnLayout:
    """Resolved widths for the three-column TUI layout."""

    total_width: int
    user_width: int
    posts_width: int
    details_width: int


def resolve_column_layout(total_width: Optional[int] = None) -> ColumnLayout:
    """Resolve absolute widths for the current terminal."""
    width = total_width or shutil.get_terminal_size().columns
    separator_total = 2
    usable_width = max(30, width - separator_total)

    user_width = max(16, int(usable_width * USER_COLUMN_RATIO))
    posts_width = max(24, int(usable_width * POSTS_COLUMN_RATIO))
    details_width = max(30, usable_width - user_width - posts_width)

    return ColumnLayout(
        total_width=width,
        user_width=user_width,
        posts_width=posts_width,
        details_width=details_width,
    )


def pad_column_text(text: str, width: int) -> str:
    """Pad text inside a column with left/right breathing room."""
    inner_width = max(1, width - (COLUMN_PADDING * 2))
    clipped = text[:inner_width]
    return f"{' ' * COLUMN_PADDING}{clipped:<{inner_width}}{' ' * COLUMN_PADDING}"
