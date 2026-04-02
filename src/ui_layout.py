"""Layout and styling helpers for the prompt-toolkit TUI."""

from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
from prompt_toolkit.layout import Dimension as D
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style

from .config import Config
from .types import AppState
from .ui_columns import COLUMN_SEPARATOR, pad_column_text, resolve_column_layout
from .ui_controls import TweetDetailsControl, TweetTableControl, UserListControl
from .ui_status import get_status_text

_STATUS_HIGHLIGHT_KEYWORDS = (
    "已复制",
    "已打开",
    "配置已重载",
    "错误:",
)


def create_layout(
    state: AppState,
    config: Config,
    search_overlay=None,
) -> Layout:
    """Create the three-column application layout."""
    state.set_monitored_handles(config.users.handles)

    def get_header_line():
        status = get_status_text(state)
        is_status_msg = any(keyword in status for keyword in _STATUS_HIGHLIGHT_KEYWORDS)
        if is_status_msg:
            return FormattedText(
                [
                    ("class:header", "x-monitor | "),
                    ("class:status.highlight", status),
                ]
            )
        return f"x-monitor | {status}"

    header = Window(
        content=FormattedTextControl(get_header_line),
        height=D.exact(1),
        style="class:header",
        dont_extend_height=True,
    )

    def get_column_headers():
        column_layout = resolve_column_layout()
        return (
            f"{pad_column_text('Users (A-Z)', column_layout.user_width)}"
            f"{COLUMN_SEPARATOR}"
            f"{pad_column_text('Posts', column_layout.posts_width)}"
            f"{COLUMN_SEPARATOR}"
            f"{pad_column_text('Details', column_layout.details_width)}"
        )

    table_header = Window(
        content=FormattedTextControl(get_column_headers),
        height=D.exact(1),
        style="class:table_header",
        dont_extend_height=True,
    )

    separator = Window(
        content=FormattedTextControl(lambda: "─" * resolve_column_layout().total_width),
        height=D.exact(1),
        style="class:separator",
        dont_extend_height=True,
    )

    column_layout = resolve_column_layout()

    content_area = VSplit(
        [
            Window(content=UserListControl(state), width=D(preferred=column_layout.user_width), wrap_lines=False),
            Window(
                content=FormattedTextControl([("class:vseparator", COLUMN_SEPARATOR)]),
                width=D.exact(1),
                dont_extend_height=False,
            ),
            Window(content=TweetTableControl(state), width=D(preferred=column_layout.posts_width), wrap_lines=False),
            Window(
                content=FormattedTextControl([("class:vseparator", COLUMN_SEPARATOR)]),
                width=D.exact(1),
                dont_extend_height=False,
            ),
            Window(content=TweetDetailsControl(state), width=D(preferred=column_layout.details_width), wrap_lines=False),
        ]
    )

    footer = Window(
        content=FormattedTextControl(
            lambda: (
                "Tab左中切栏  ↑↓选择  ←→翻页  Alt+↑↓滚动详情  "
                "o打开URL  c复制  Esc+R全部已读  q退出"
            )
        ),
        height=D.exact(1),
        style="class:footer",
        dont_extend_height=True,
    )

    return Layout(HSplit([header, table_header, separator, content_area, footer]))


def create_style() -> Style:
    """Create the color scheme."""
    return Style.from_dict(
        {
            "header": "fg:#5F87AF bold",
            "status.highlight": "fg:#00FF00 bold",
            "table_header": "fg:#888888",
            "separator": "fg:#444444",
            "footer": "fg:#606060",
            "selected": "reverse",
            "vseparator": "fg:#444444",
            "details.title": "fg:#5F87AF bold",
            "details.label": "fg:#606060",
        }
    )
