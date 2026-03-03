"""TUI interface for x-monitor using prompt_toolkit."""

import asyncio
import shutil
from datetime import datetime
from typing import Callable
from prompt_toolkit.utils import get_cwidth as _pt_cwidth


def _w(s: str) -> int:
    """Display width matching prompt_toolkit's internal rendering."""
    return _pt_cwidth(s)

from prompt_toolkit.application import Application, run_in_terminal
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window, Dimension as D, FloatContainer, Float
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.controls import UIControl, UIContent, FormattedTextControl, BufferControl
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.layout.screen import Point

from .config import Config
from .types import AppState, Tweet


# ============================================================================
# Search Overlay Components
# ============================================================================

# 搜索缓冲区
_search_buffer = Buffer(
    name='search',
    multiline=False,
)

# 用于追踪当前 state 和 config（用于重建 layout）
_search_state_ref = [None]
_search_config_ref = [None]


# 搜索模式过滤器 - 用于禁用主应用快捷键
def _not_in_search_mode():
    """检查是否不在搜索模式"""
    if _search_state_ref[0] is not None:
        return not _search_state_ref[0].search_visible
    return True


_not_searching_filter = Condition(_not_in_search_mode)

# 搜索框专用快捷键
_search_kb = KeyBindings()


@_search_kb.add('escape')
def _cancel_search(event):
    """取消搜索"""
    app = event.app
    state = _search_buffer.state
    if state is None:
        # 如果 state 未设置，使用引用
        state = _search_state_ref[0]
    if state is None:
        return  # 无法继续

    state.search_visible = False
    _search_buffer.text = ""

    # 重建 layout 以隐藏搜索浮层
    config = _search_config_ref[0]
    if config:
        app.layout = create_layout(state, config)
    app.invalidate()


@_search_kb.add('enter')
def _confirm_search(event):
    """确认搜索"""
    from datetime import datetime, timezone
    app = event.app
    state = _search_buffer.state
    keyword = _search_buffer.text.strip()

    if keyword:
        state.apply_keyword_filter(keyword)
        state.status_message = f"关键词: {keyword}"
        state.status_message_timestamp = datetime.now(timezone.utc)
    else:
        state.clear_filters()
        state.status_message = "已清除过滤"
        state.status_message_timestamp = datetime.now(timezone.utc)

    state.search_visible = False

    # 重建 layout 以隐藏搜索浮层
    config = _search_config_ref[0]
    if config:
        app.layout = create_layout(state, config)
    app.invalidate()


# 搜索控制器
_search_control = BufferControl(
    buffer=_search_buffer,
    key_bindings=_search_kb,
    focusable=True,  # 确保可聚焦
)

# 搜索窗口（用于焦点管理）
_search_window = Window(
    content=_search_control,
    style='class:search.box',
)


class TweetTableControl(UIControl):
    """Custom control for displaying tweet table."""

    def __init__(self, state: AppState):
        self.state = state

    def create_content(self, width: int, height: int) -> UIContent:
        """Generate table content for display."""
        lines = []

        # 更新页面大小
        self.state.update_page_size(height)

        # state.tweets is already filtered, no need to filter here
        visible_tweets_all = self.state.tweets

        # 固定列宽：User(16) + Date(9) + Separator(3) + 空格(2) = 30
        # Content 列自适应填充剩余空间
        user_width = 16
        date_width = 9
        separator_width = 3  # │ with spacing
        fixed_width = user_width + date_width + separator_width + 2  # 包括空格
        content_width = max(width - fixed_width, 20)  # 使用实际可用宽度

        # 计算当前页的推文范围
        total_filtered = len(visible_tweets_all)
        start_idx = self.state.current_page * self.state.page_size
        end_idx = min(start_idx + self.state.page_size, total_filtered)
        visible_tweets = visible_tweets_all[start_idx:end_idx]

        for i, tweet in enumerate(visible_tweets):
            # Since tweets are already filtered, use the absolute index (start_idx + i)
            absolute_index = start_idx + i

            # Format tweet row - 动态内容宽度
            prefix = ""
            if tweet.is_new:
                prefix = "🔔 "
            elif tweet.is_retweet:
                prefix = "🔁 "
            # 使用 wcswidth 计算 emoji 的实际显示宽度
            prefix_display_width = _w(prefix) if prefix else 0
            # 从 content_width 中减去 prefix 的显示宽度
            available_content_width = content_width - prefix_display_width

            # 获取截断后的内容
            tweet_preview = tweet.preview(available_content_width)

            # 计算实际显示宽度（考虑中文字符）
            preview_display_width = _w(tweet_preview)

            # 计算需要填充的空格数（确保 Content 列总宽度为 content_width）
            content_padding = content_width - prefix_display_width - preview_display_width
            if content_padding < 0:
                content_padding = 0

            # 格式化各列
            user_col = f"@{tweet.author}"
            # 计算 user_col 的显示宽度并填充到 user_width
            user_col_width = _w(user_col)
            user_padding = user_width - user_col_width
            if user_padding < 0:
                user_padding = 0

            content_col = f"{prefix}{tweet_preview}{' ' * content_padding}"

            date_col = tweet.format_timestamp()
            date_col_width = _w(date_col)
            date_padding = date_width - date_col_width
            if date_padding < 0:
                date_padding = 0

            # 组合行：User + 空格 + Content + 空格 + Date + Separator
            separator_col = " │"  # Space + vertical bar
            is_selected = absolute_index == self.state.selected_index
            if is_selected:
                row_text = f"{user_col}{' ' * user_padding} {content_col} {date_col}{' ' * date_padding}{separator_col}"
                lines.append(FormattedText([('class:selected', row_text)]))
            else:
                lines.append(FormattedText([
                    ('class:author', f"{user_col}{' ' * user_padding}"),
                    ('', f" {content_col} "),
                    ('class:date', f"{date_col}{' ' * date_padding}"),
                    ('class:vseparator', separator_col),
                ]))

        # Fill remaining space with empty lines
        while len(lines) < height:
            lines.append(FormattedText([('', '')]))

        return UIContent(
            get_line=lambda i: lines[i] if i < len(lines) else FormattedText([('', '')]),
            line_count=len(lines),
            cursor_position=Point(0, self.state.selected_index - start_idx)
        )

    def is_focusable(self) -> bool:
        """This control can receive focus."""
        return True

    def get_key_bindings(self):
        """No specific key bindings for this control."""
        return None


class TweetDetailsControl(UIControl):
    """显示选中推文的详细信息"""

    def __init__(self, state: AppState):
        self.state = state

    def create_content(self, width: int, height: int) -> UIContent:
        """生成详情内容"""
        lines = []

        tweet = self.state.selected_tweet
        if not tweet:
            lines.append(FormattedText([('', '没有选中的推文')]))
        else:
            # 标题
            lines.append(FormattedText([('class:details.title', f'@{tweet.author}')]))
            lines.append(FormattedText([('', '')]))

            # 徽章
            badges = []
            if tweet.is_retweet:
                badges.append('🔁 转推')
            if tweet.is_reply:
                badges.append('💬 回复')
            if badges:
                lines.append(FormattedText([('class:details.label', ' '.join(badges))]))
                lines.append(FormattedText([('', '')]))

            # 时间
            local_time = tweet.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(FormattedText([
                ('class:details.label', '发布时间: '),
                ('', local_time),
            ]))

            # URL - 紧跟在时间戳后面
            x_url = f'https://x.com/{tweet.author}/status/{tweet.id}'
            lines.append(FormattedText([
                ('class:details.label', 'URL: '),
                ('class:details.label', x_url),
            ]))
            lines.append(FormattedText([('', '')]))
            lines.append(FormattedText([('class:details.label', '---')]))
            lines.append(FormattedText([('', '')]))

            # 内容（自动换行）
            content_lines = []
            words = tweet.content.split()
            current_line = ''
            current_width = 0
            max_width = width - 2  # 留出边距

            for word in words:
                word_width = _w(word)
                space_width = 1 if current_line else 0
                if current_width + space_width + word_width <= max_width:
                    current_line += (' ' if current_line else '') + word
                    current_width += space_width + word_width
                else:
                    if current_line:
                        content_lines.append(current_line)
                    if word_width <= max_width:
                        current_line = word
                        current_width = word_width
                    else:
                        # Word itself too wide (e.g. long CJK with no spaces): split by char
                        chunk_chars = []
                        chunk_w = 0
                        for ch in word:
                            cw = _w(ch)
                            if chunk_w + cw > max_width and chunk_chars:
                                content_lines.append(''.join(chunk_chars))
                                chunk_chars = [ch]
                                chunk_w = cw
                            else:
                                chunk_chars.append(ch)
                                chunk_w += cw
                        if chunk_chars:
                            content_lines.append(''.join(chunk_chars))
                        current_line = ''
                        current_width = 0

            if current_line:
                content_lines.append(current_line)

            for line in content_lines:
                lines.append(FormattedText([('', ' ' + line)]))

        # Apply scroll offset
        offset = self.state.details_scroll_offset
        if offset > 0:
            # Skip lines from the top based on offset
            lines = lines[offset:]

        # 填充剩余空间
        while len(lines) < height:
            lines.append(FormattedText([('', '')]))

        return UIContent(
            get_line=lambda i: lines[i] if i < len(lines) else FormattedText([('', '')]),
            line_count=len(lines),
        )

    def is_focusable(self) -> bool:
        return False


def get_status_text(state: AppState) -> str:
    """Generate status bar text."""
    # Status message (display for 3 seconds)
    if state.status_message and state.status_message != "Initializing..." and state.status_message_timestamp:
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        if (now - state.status_message_timestamp) < timedelta(seconds=3):
            return f"▶ • {state.status_message}"
        else:
            # Clear status message after 3 seconds
            state.status_message = "Initializing..."
            state.status_message_timestamp = None

    # Error message (display for 5 seconds)
    if state.error_message and state.error_timestamp:
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        if (now - state.error_timestamp) < timedelta(seconds=5):
            return f"❌ 错误: {state.error_message}"
        else:
            # Clear error after 5 seconds
            state.error_message = None
            state.error_timestamp = None

    # Loading indicator
    if state.is_loading:
        return "⏳ 加载中..."

    new_count = f"🔔 {state.new_tweets_count} 条新 • " if state.new_tweets_count > 0 else ""
    total = f"{len(state.tweets)} 条"

    # 页码信息
    page_info = ""
    if state.total_pages > 0:
        page_info = f" • {state.current_page + 1}/{state.total_pages} 页"

    # 相对时间
    last_update = ""
    if state.last_poll:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        delta = now - state.last_poll

        if delta.total_seconds() < 10:
            last_update = " • 刚刚"
        elif delta.total_seconds() < 60:
            last_update = f" • {int(delta.total_seconds())}秒前"
        elif delta.total_seconds() < 3600:
            minutes = int(delta.total_seconds() / 60)
            last_update = f" • {minutes}分钟前"
        else:
            hours = int(delta.total_seconds() / 3600)
            last_update = f" • {hours}小时前"

    # Filter indicators
    filter_info = ""
    if state.filter_keyword:
        filter_info += f" [过滤关键词: {state.filter_keyword}]"
    if state.filter_user:
        filter_info += f" [用户: @{state.filter_user}]"

    return f"▶ • {new_count}{total}{page_info}{last_update}{filter_info}"


def create_layout(state: AppState, config: Config) -> Layout:
    """Create the application layout."""

    # Combined header and status bar
    def get_header_line():
        status = get_status_text(state)
        # 检查是否是状态消息（包含特定关键词）
        status_keywords = ["已复制", "已打开", "已清除", "配置已重载", "关键词:", "仅显示", "错误:"]
        is_status_msg = any(keyword in status for keyword in status_keywords)

        if is_status_msg:
            # 状态消息使用醒目的样式
            return FormattedText([
                ('class:header', 'x-monitor | '),
                ('class:status.highlight', status)
            ])
        else:
            # 普通状态使用默认样式
            return f"x-monitor | {status}"

    header = Window(
        content=FormattedTextControl(get_header_line),
        height=D.exact(1),
        style='class:header',
        dont_extend_height=True
    )

    # Table header (column names)
    def get_table_header_line():
        # 固定列宽：User(16) + Date(9) + Separator(3) + 空格(2) = 30
        # Content 列自适应填充剩余空间
        term_width = shutil.get_terminal_size().columns
        main_width = term_width // 2
        user_width = 16
        date_width = 9
        fixed_width = user_width + date_width + 2  # 2 spaces
        content_width = max(main_width - fixed_width, 20)

        # 使用与内容行相同的格式化方式
        user_col = "User"
        user_col_width = len(user_col)
        user_padding = user_width - user_col_width

        content_col = "Content"
        content_col_width = len(content_col)
        content_padding = content_width - content_col_width

        date_col = "Date"
        date_col_width = len(date_col)
        date_padding = date_width - date_col_width

        return f"{user_col}{' ' * user_padding} {content_col}{' ' * content_padding} {date_col}{' ' * date_padding}"

    table_header = Window(
        content=FormattedTextControl(get_table_header_line),
        height=D.exact(1),
        style='class:table_header',
        dont_extend_height=True
    )

    # Separator line
    def get_separator():
        term_width = shutil.get_terminal_size().columns
        return "─" * term_width

    separator = Window(
        content=FormattedTextControl(get_separator),
        height=D.exact(1),
        style='class:separator',
        dont_extend_height=True
    )

    # 计算布局宽度：主内容 1/2，详情面板 1/2
    term_width = shutil.get_terminal_size().columns
    main_width = term_width // 2
    details_width = term_width - main_width  # 剩余宽度给详情面板

    # Main content (tweet table) - 占据 3/4 屏幕
    main_content = Window(
        content=TweetTableControl(state),
        width=D(preferred=main_width),
        wrap_lines=False,
        always_hide_cursor=False,
        dont_extend_height=False
    )

    # Details panel (永久显示在右侧，占 1/2 屏幕)
    details_panel = Window(
        content=TweetDetailsControl(state),
        width=D(preferred=details_width),
        wrap_lines=False,
    )

    # Combine main content and details in horizontal split
    content_area = VSplit([
        main_content,
        details_panel,
    ])

    # Footer (keybindings)
    footer = Window(
        content=FormattedTextControl(
            lambda: "Q:退出  ↑↓:选择  ←→:翻页  /:搜索  u:用户过滤  o:打开URL  c:复制  Alt+↑↓:滚动详情"
        ),
        height=D.exact(1),
        style='class:footer',
        dont_extend_height=True
    )

    # Combine into vertical layout
    main_container = HSplit([
        header,
        table_header,
        separator,
        content_area,
        footer,
    ])

    # 搜索弹窗内容
    search_dialog = HSplit([
        Window(height=1),  # 上边距
        Window(
            content=FormattedTextControl([
                ('class:search.title', '─── 搜索 ───'),
            ]),
            height=1,
        ),
        Window(height=1),  # 标题与输入框之间的间距
        Window(
            content=FormattedTextControl([
                ('class:search.prompt', '> '),
            ]),
        ),
        _search_window,  # 搜索输入框
        Window(height=1),  # 输入框与提示之间的间距
        Window(
            content=FormattedTextControl([('', 'Enter 确认  Esc 取消')]),
            height=1,
            style='class:search.hint',
        ),
        Window(height=1),  # 下边距
    ], style='class:search.background')

    # 将 state 和 config 附加到全局引用（用于搜索浮层的 layout 重建）
    _search_buffer.state = state
    _search_state_ref[0] = state
    _search_config_ref[0] = config

    # 搜索弹窗（居中浮层）
    # Float 组件的样式通过全局样式类控制
    search_float = Float(content=search_dialog)

    # 用 FloatContainer 包装（modal=True 实现热键屏蔽）
    # 根据 state.search_visible 决定是否显示搜索浮层
    floats = [search_float] if state.search_visible else []
    root_container = FloatContainer(
        content=main_container,
        floats=floats,
        modal=True,
    )

    return Layout(root_container)


def format_tweet_as_markdown(tweet: Tweet) -> str:
    """Format tweet as Markdown for clipboard."""
    url = f'https://x.com/{tweet.author}/status/{tweet.id}'
    timestamp = tweet.timestamp.strftime("%Y-%m-%d %H:%M:%S")

    # 添加徽章
    badges = []
    if tweet.is_retweet:
        badges.append("🔁")
    if tweet.is_reply:
        badges.append("💬")
    badge_str = " " + " ".join(badges) if badges else ""

    # 生成 Markdown
    markdown = f"**[@{tweet.author}]({url})**{badge_str}\n"
    markdown += f"📅 {timestamp}\n\n"
    markdown += tweet.content

    return markdown


def create_key_bindings(state: AppState, monitor=None) -> KeyBindings:
    """Create keyboard shortcuts."""
    kb = KeyBindings()

    @kb.add('j', filter=_not_searching_filter)
    @kb.add('down', filter=_not_searching_filter)
    def _(event):
        """Move down."""
        state.select_next()
        state.details_scroll_offset = 0  # Reset scroll offset
        state.mark_selected_as_read()
        if state.new_tweets_count == 0 and monitor:
            monitor.notifier.clear_badge()
        event.app.invalidate()

    @kb.add('k', filter=_not_searching_filter)
    @kb.add('up', filter=_not_searching_filter)
    def _(event):
        """Move up."""
        state.select_previous()
        state.details_scroll_offset = 0  # Reset scroll offset
        state.mark_selected_as_read()
        if state.new_tweets_count == 0 and monitor:
            monitor.notifier.clear_badge()
        event.app.invalidate()

    @kb.add('right', filter=_not_searching_filter)
    @kb.add('pagedown', filter=_not_searching_filter)
    def _(event):
        """Next page."""
        state.next_page()
        state.details_scroll_offset = 0  # Reset scroll offset
        state.mark_selected_as_read()
        if state.new_tweets_count == 0 and monitor:
            monitor.notifier.clear_badge()
        event.app.invalidate()

    @kb.add('left', filter=_not_searching_filter)
    @kb.add('pageup', filter=_not_searching_filter)
    def _(event):
        """Previous page."""
        state.prev_page()
        state.details_scroll_offset = 0  # Reset scroll offset
        state.mark_selected_as_read()
        if state.new_tweets_count == 0 and monitor:
            monitor.notifier.clear_badge()
        event.app.invalidate()

    @kb.add('q', filter=_not_searching_filter)
    @kb.add('c-c', filter=_not_searching_filter)  # Ctrl+C
    def _(event):
        """Quit."""
        event.app.exit()

    @kb.add('/', filter=_not_searching_filter)
    def _(event):
        """显示搜索浮层"""
        app = event.app
        state.search_visible = True

        # 每次打开搜索框时清空输入
        _search_buffer.text = ""
        _search_buffer.state = state
        _search_buffer.cursor_position = 0

        # 确保 state 引用已设置
        _search_state_ref[0] = state

        # 重建 layout 以显示搜索浮层
        config = _search_config_ref[0]
        if config:
            app.layout = create_layout(state, config)

        # 将焦点移动到搜索框
        # 通过遍历 layout 中的可聚焦元素来找到搜索框
        focused = False
        for container in app.layout.find_all_windows():
            if hasattr(container, 'content') and container.content == _search_control:
                try:
                    app.layout.focus(container)
                    focused = True
                    break
                except ValueError:
                    pass
        # 如果还是找不到，尝试 focus_next
        if not focused:
            try:
                app.layout.focus_next()
            except Exception:
                pass
        app.invalidate()

    @kb.add('u', filter=_not_searching_filter)
    def _(event):
        """Filter by current user."""
        from datetime import datetime, timezone
        if state.filter_user:
            # Clear all filters
            state.clear_filters()
            state.status_message = "已清除用户过滤"
            state.status_message_timestamp = datetime.now(timezone.utc)
        else:
            # Set filter to current user
            if state.selected_tweet:
                target_user = state.selected_tweet.author
                state.apply_user_filter(target_user)
                state.status_message = f"仅显示 @{target_user} 的推文"
                state.status_message_timestamp = datetime.now(timezone.utc)

        event.app.invalidate()

    @kb.add('o', filter=_not_searching_filter)
    def _(event):
        """Open URL in browser."""
        import webbrowser
        from datetime import datetime, timezone
        if state.selected_tweet:
            url = f'https://x.com/{state.selected_tweet.author}/status/{state.selected_tweet.id}'
            webbrowser.open(url)
            state.status_message = f"已打开: {url}"
            state.status_message_timestamp = datetime.now(timezone.utc)
        event.app.invalidate()

    @kb.add('c', filter=_not_searching_filter)
    def _(event):
        """Copy tweet details to clipboard as Markdown."""
        if state.selected_tweet:
            try:
                import pyperclip
                from datetime import datetime, timezone
                markdown = format_tweet_as_markdown(state.selected_tweet)
                pyperclip.copy(markdown)
                state.status_message = "已复制到剪贴板 (Markdown)"
                state.status_message_timestamp = datetime.now(timezone.utc)
            except ImportError:
                state.status_message = "错误: 未安装 pyperclip 库"
                state.status_message_timestamp = datetime.now(timezone.utc)
            except Exception as e:
                state.status_message = f"复制失败: {str(e)}"
                state.status_message_timestamp = datetime.now(timezone.utc)
        event.app.invalidate()

    @kb.add('escape', 'down', filter=_not_searching_filter)
    def _(event):
        """Scroll details panel down."""
        state.details_scroll_offset += 1
        event.app.invalidate()

    @kb.add('escape', 'up', filter=_not_searching_filter)
    def _(event):
        """Scroll details panel up."""
        state.details_scroll_offset = max(0, state.details_scroll_offset - 1)
        event.app.invalidate()

    return kb


def create_style() -> Style:
    """Create color scheme."""
    return Style.from_dict({
        'header':         'fg:#5F87AF bold',   # App title + status bar
        'status.highlight': 'fg:#00FF00 bold', # 状态消息高亮（亮绿色）
        'table_header':   'fg:#888888',        # Column labels
        'separator':      'fg:#444444',        # Horizontal rule
        'footer':         'fg:#606060',        # Key hint bar
        'selected':       'reverse',           # Selected row highlight
        'author':         'fg:#5F87AF',        # @username column
        'date':           'fg:#606060',        # Date column
        'vseparator':     'fg:#444444',        # │ between list and details
        'details.title':  'fg:#5F87AF bold',   # Author name in details panel
        'details.label':  'fg:#606060',        # Field labels in details panel
        'float-background': 'bg:#1a1a1a',     # Float 组件背景色（覆盖默认黄色）
        'search.title':     'fg:#5F87AF bold',   # Search dialog title (与 header 一致)
        'search.background':'bg:#1a1a1a noinherit',  # 弹窗内容背景（深灰）
        'search.prompt':    'fg:#5F87AF',        # 搜索提示符 >
        'search.box':       'bg:#ffffff fg:#000000',  # 白色背景，黑色文字
        'search.hint':      'fg:#666666',        # Search dialog hints (柔和灰色)
    })


async def poll_tweets_background(state: AppState, config: Config, app: Application, refresh_callback: Callable):
    """Background task for polling tweets."""
    import time
    from datetime import datetime, timezone
    last_poll_time = time.time() - config.general.poll_interval_sec  # 立即触发一次轮询

    while True:
        try:
            current_time = time.time()
            time_since_last_poll = current_time - last_poll_time
            time_until_next_poll = config.general.poll_interval_sec - time_since_last_poll

            # 等待到下一次轮询时间
            if time_until_next_poll > 0:
                await asyncio.sleep(time_until_next_poll)

            # Set loading state
            state.is_loading = True
            app.invalidate()

            # Clear any previous error
            state.error_message = None
            state.error_timestamp = None

            try:
                # Call the refresh callback
                await refresh_callback()
            except Exception as e:
                # Set error state
                state.error_message = str(e)
                state.error_timestamp = datetime.now(timezone.utc)
            finally:
                # Clear loading state
                state.is_loading = False

            # Trigger UI refresh
            app.invalidate()

            # 更新上次轮询时间
            last_poll_time = time.time()

        except asyncio.CancelledError:
            break
        except Exception as e:
            # Silent error handling - continue polling
            state.error_message = str(e)
            state.error_timestamp = datetime.now(timezone.utc)
            state.is_loading = False
            await asyncio.sleep(5)  # Wait before retry
            last_poll_time = time.time() - config.general.poll_interval_sec  # 立即重试


async def update_ui_background(app: Application):
    """Background task to update UI every second (for relative time)."""
    while True:
        try:
            await asyncio.sleep(1)  # 每秒刷新一次 UI
            app.invalidate()
        except asyncio.CancelledError:
            break


async def run_ui(config: Config, state: AppState, refresh_callback: Callable, monitor=None) -> None:
    """Run the TUI application."""

    # Create application
    app = Application(
        layout=create_layout(state, config),
        key_bindings=create_key_bindings(state, monitor),
        style=create_style(),
        full_screen=True,
        mouse_support=False,  # Keyboard only
    )

    # Start background polling
    poll_task = asyncio.create_task(
        poll_tweets_background(state, config, app, refresh_callback)
    )

    # 启动时恢复标题状态（如果有未读推文）
    if state.new_tweets_count > 0 and monitor:
        monitor.notifier.notify_batch(0, state.new_tweets_count)

    # Start UI update task (for relative time)
    ui_update_task = asyncio.create_task(
        update_ui_background(app)
    )

    try:
        # Run application
        await app.run_async()
    finally:
        # Cleanup
        poll_task.cancel()
        ui_update_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass
        try:
            await ui_update_task
        except asyncio.CancelledError:
            pass
