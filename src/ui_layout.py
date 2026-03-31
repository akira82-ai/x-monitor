"""Layout and styling helpers for the prompt-toolkit TUI."""

import shutil

from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import Float, FloatContainer, HSplit, Layout, VSplit, Window
from prompt_toolkit.layout import Dimension as D
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style

from .config import Config
from .types import AppState
from .ui_controls import TweetDetailsControl, TweetTableControl
from .ui_status import get_status_text

_STATUS_HIGHLIGHT_KEYWORDS = (
    "已复制",
    "已打开",
    "已清除",
    "配置已重载",
    "关键词:",
    "仅显示",
    "错误:",
)


def create_layout(
    state: AppState,
    config: Config,
    search_overlay,
) -> Layout:
    """Create the application layout."""

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

    def get_table_header_line():
        term_width = shutil.get_terminal_size().columns
        main_width = term_width // 2
        user_width = 16
        date_width = 9
        fixed_width = user_width + date_width + 2
        content_width = max(main_width - fixed_width, 20)

        user_col = "User"
        user_padding = user_width - len(user_col)

        content_col = "Content"
        content_padding = content_width - len(content_col)

        date_col = "Date"
        date_padding = date_width - len(date_col)

        return (
            f"{user_col}{' ' * user_padding} "
            f"{content_col}{' ' * content_padding} "
            f"{date_col}{' ' * date_padding}"
        )

    table_header = Window(
        content=FormattedTextControl(get_table_header_line),
        height=D.exact(1),
        style="class:table_header",
        dont_extend_height=True,
    )

    separator = Window(
        content=FormattedTextControl(lambda: "─" * shutil.get_terminal_size().columns),
        height=D.exact(1),
        style="class:separator",
        dont_extend_height=True,
    )

    term_width = shutil.get_terminal_size().columns
    main_width = term_width // 2
    details_width = term_width - main_width

    main_content = Window(
        content=TweetTableControl(state),
        width=D(preferred=main_width),
        wrap_lines=False,
        always_hide_cursor=False,
        dont_extend_height=False,
    )

    details_panel = Window(
        content=TweetDetailsControl(state),
        width=D(preferred=details_width),
        wrap_lines=False,
    )

    content_area = VSplit([main_content, details_panel])

    footer = Window(
        content=FormattedTextControl(
            lambda: (
                "Q:退出  ↑↓:选择  ←→:翻页  /:搜索  u:用户过滤  "
                "o:打开URL  c:复制  Alt+↑↓:滚动详情  Alt+R:全部已读"
            )
        ),
        height=D.exact(1),
        style="class:footer",
        dont_extend_height=True,
    )

    main_container = HSplit([header, table_header, separator, content_area, footer])

    search_dialog = HSplit(
        [
            Window(height=1),
            Window(
                content=FormattedTextControl([("class:search.title", "─── 搜索 ───")]),
                height=1,
            ),
            Window(height=1),
            Window(content=FormattedTextControl([("class:search.prompt", "> ")])),
            search_overlay.window,
            Window(height=1),
            Window(
                content=FormattedTextControl([("", "Enter 确认  Esc 取消")]),
                height=1,
                style="class:search.hint",
            ),
            Window(height=1),
        ],
        style="class:search.background",
    )

    search_overlay.attach(state, config)

    floats = [Float(content=search_dialog)] if state.search_visible else []
    root_container = FloatContainer(content=main_container, floats=floats, modal=True)
    return Layout(root_container)


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
            "author": "fg:#5F87AF",
            "date": "fg:#606060",
            "vseparator": "fg:#444444",
            "details.title": "fg:#5F87AF bold",
            "details.label": "fg:#606060",
            "float-background": "bg:#1a1a1a",
            "search.title": "fg:#5F87AF bold",
            "search.background": "bg:#1a1a1a noinherit",
            "search.prompt": "fg:#5F87AF",
            "search.box": "bg:#ffffff fg:#000000",
            "search.hint": "fg:#666666",
        }
    )
