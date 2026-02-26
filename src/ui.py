"""TUI interface for x-monitor using prompt_toolkit."""

import asyncio
import shutil
from datetime import datetime
from typing import Callable
from wcwidth import wcswidth

from prompt_toolkit.application import Application
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window, Dimension as D
from prompt_toolkit.layout.controls import UIControl, UIContent, FormattedTextControl
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.layout.screen import Point

from .config import Config
from .types import AppState, Tweet


class TweetTableControl(UIControl):
    """Custom control for displaying tweet table."""

    def __init__(self, state: AppState):
        self.state = state

    def create_content(self, width: int, height: int) -> UIContent:
        """Generate table content for display."""
        lines = []

        # 更新页面大小
        self.state.update_page_size(height)

        # 固定列宽：User(16) + Date(9) + Separator(3) + 空格(2) = 30
        # Content 列自适应填充剩余空间
        user_width = 16
        date_width = 9
        separator_width = 3  # │ with spacing
        fixed_width = user_width + date_width + separator_width + 2  # 包括空格
        content_width = max(width - fixed_width, 20)  # 使用实际可用宽度

        # 计算当前页的推文范围
        start_idx = self.state.current_page * self.state.page_size
        end_idx = min(start_idx + self.state.page_size, len(self.state.tweets))
        visible_tweets = self.state.tweets[start_idx:end_idx]

        for i, tweet in enumerate(visible_tweets):
            actual_index = start_idx + i
            # Determine style based on selection
            style = 'class:selected' if actual_index == self.state.selected_index else ''

            # Format tweet row - 动态内容宽度
            prefix = ""
            if tweet.is_new:
                prefix = "🔔 "
            elif tweet.is_retweet:
                prefix = "🔁 "
            # 使用 wcswidth 计算 emoji 的实际显示宽度
            prefix_display_width = wcswidth(prefix) if prefix and wcswidth(prefix) > 0 else 0
            # 从 content_width 中减去 prefix 的显示宽度
            available_content_width = content_width - prefix_display_width

            # 获取截断后的内容
            tweet_preview = tweet.preview(available_content_width)

            # 计算实际显示宽度（考虑中文字符）
            preview_display_width = wcswidth(tweet_preview) if wcswidth(tweet_preview) > 0 else len(tweet_preview)

            # 计算需要填充的空格数（确保 Content 列总宽度为 content_width）
            content_padding = content_width - prefix_display_width - preview_display_width
            if content_padding < 0:
                content_padding = 0

            # 格式化各列
            user_col = f"@{tweet.author}"
            # 计算 user_col 的显示宽度并填充到 user_width
            user_col_width = wcswidth(user_col) if wcswidth(user_col) > 0 else len(user_col)
            user_padding = user_width - user_col_width
            if user_padding < 0:
                user_padding = 0

            content_col = f"{prefix}{tweet_preview}{' ' * content_padding}"

            date_col = tweet.format_timestamp()
            date_col_width = wcswidth(date_col) if wcswidth(date_col) > 0 else len(date_col)
            date_padding = date_width - date_col_width
            if date_padding < 0:
                date_padding = 0

            # 组合行：User + 空格 + Content + 空格 + Date + Separator
            separator_col = " │"  # Space + vertical bar
            row_text = f"{user_col}{' ' * user_padding} {content_col} {date_col}{' ' * date_padding}{separator_col}"
            lines.append(FormattedText([(style, row_text)]))

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
            lines.append(FormattedText([('bold', f'@{tweet.author}')]))
            lines.append(FormattedText([('', '')]))

            # 徽章
            badges = []
            if tweet.is_retweet:
                badges.append('🔁 转推')
            if tweet.is_reply:
                badges.append('💬 回复')
            if badges:
                lines.append(FormattedText([('', ' '.join(badges))]))
                lines.append(FormattedText([('', '')]))

            # 时间 - 转换为本地时区
            local_time = tweet.timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            lines.append(FormattedText([('', f'发布时间: {local_time}')]))

            # URL - 紧跟在时间戳后面
            x_url = f'https://x.com/{tweet.author}/status/{tweet.id}'
            lines.append(FormattedText([('dim', f'URL: {x_url}')]))
            lines.append(FormattedText([('', '')]))
            lines.append(FormattedText([('', '---')]))
            lines.append(FormattedText([('', '')]))

            # 内容（自动换行）
            content_lines = []
            words = tweet.content.split()
            current_line = ''
            max_width = width - 2  # 留出边距

            for word in words:
                if len(current_line) + len(word) + 1 <= max_width:
                    current_line += (' ' if current_line else '') + word
                else:
                    if current_line:
                        content_lines.append(current_line)
                    current_line = word
            if current_line:
                content_lines.append(current_line)

            for line in content_lines:
                lines.append(FormattedText([('', ' ' + line)]))

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
    status_icon = "⏸" if state.paused else "▶"

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

    return f"{status_icon} • {new_count}{total}{page_info}{last_update}"


def create_layout(state: AppState, config: Config) -> Layout:
    """Create the application layout."""

    # Combined header and status bar
    def get_header_line():
        status = get_status_text(state)
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
        main_width = term_width * 3 // 4
        user_width = 16
        date_width = 9
        separator_width = 3  # │ with spacing
        fixed_width = user_width + date_width + separator_width + 2
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
            lambda: "Q:退出  R:刷新  Space:暂停  ↑↓:选择  ←→:翻页  g/G:首尾"
        ),
        height=D.exact(1),
        style='class:footer',
        dont_extend_height=True
    )

    # Combine into vertical layout
    root_container = HSplit([
        header,
        table_header,
        separator,
        content_area,
        footer,
    ])

    return Layout(root_container)


def create_key_bindings(state: AppState, refresh_callback: Callable) -> KeyBindings:
    """Create keyboard shortcuts."""
    kb = KeyBindings()

    @kb.add('j')
    @kb.add('down')
    def _(event):
        """Move down."""
        state.select_next()
        state.mark_selected_as_read()
        event.app.invalidate()

    @kb.add('k')
    @kb.add('up')
    def _(event):
        """Move up."""
        state.select_previous()
        state.mark_selected_as_read()
        event.app.invalidate()

    @kb.add('g')
    def _(event):
        """Jump to top."""
        state.select_first()
        state.mark_selected_as_read()
        event.app.invalidate()

    @kb.add('G')
    def _(event):
        """Jump to bottom."""
        state.select_last()
        state.mark_selected_as_read()
        event.app.invalidate()

    @kb.add('right')
    @kb.add('pagedown')
    def _(event):
        """Next page."""
        state.next_page()
        state.mark_selected_as_read()
        event.app.invalidate()

    @kb.add('left')
    @kb.add('pageup')
    def _(event):
        """Previous page."""
        state.prev_page()
        state.mark_selected_as_read()
        event.app.invalidate()

    @kb.add('q')
    @kb.add('c-c')  # Ctrl+C
    def _(event):
        """Quit."""
        event.app.exit()

    @kb.add('r')
    def _(event):
        """Refresh now."""
        # Trigger immediate poll
        asyncio.create_task(refresh_callback())
        event.app.invalidate()

    @kb.add(' ')  # Space
    def _(event):
        """Pause/Resume."""
        state.paused = not state.paused
        event.app.invalidate()

    return kb


def create_style() -> Style:
    """Create color scheme."""
    return Style.from_dict({
        'header': 'bold',
        'table_header': 'bold',
        'separator': 'dim',
        'footer': 'dim',
        'selected': 'reverse',  # Highlight selected row
        'vseparator': 'fg:white',  # White vertical separator between list and details
    })


async def poll_tweets_background(state: AppState, config: Config, app: Application, refresh_callback: Callable):
    """Background task for polling tweets."""
    import time
    last_poll_time = time.time() - config.general.poll_interval_sec  # 立即触发一次轮询

    while True:
        try:
            current_time = time.time()
            time_since_last_poll = current_time - last_poll_time
            time_until_next_poll = config.general.poll_interval_sec - time_since_last_poll

            # 等待到下一次轮询时间
            if time_until_next_poll > 0:
                await asyncio.sleep(time_until_next_poll)

            # 检查是否暂停，如果暂停则跳过这次轮询但更新时间
            if not state.paused:
                # Call the refresh callback
                await refresh_callback()
                # Trigger UI refresh
                app.invalidate()

            # 更新上次轮询时间
            last_poll_time = time.time()

        except asyncio.CancelledError:
            break
        except Exception as e:
            # Silent error handling - continue polling
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


async def run_ui(config: Config, state: AppState, refresh_callback: Callable) -> None:
    """Run the TUI application."""

    # Create application
    app = Application(
        layout=create_layout(state, config),
        key_bindings=create_key_bindings(state, refresh_callback),
        style=create_style(),
        full_screen=True,
        mouse_support=False,  # Keyboard only
    )

    # Start background polling
    poll_task = asyncio.create_task(
        poll_tweets_background(state, config, app, refresh_callback)
    )

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
