"""Key binding helpers for the TUI."""

from datetime import datetime, timezone
from typing import Callable

from prompt_toolkit.key_binding import KeyBindings

from .config import Config
from .time_utils import format_local_datetime
from .types import AppState, Tweet


def format_tweet_as_markdown(tweet: Tweet) -> str:
    """Format tweet as Markdown for clipboard."""
    url = f"https://x.com/{tweet.author}/status/{tweet.id}"
    timestamp = format_local_datetime(tweet.timestamp)

    badges = []
    if tweet.is_retweet:
        badges.append("🔁")
    if tweet.is_reply:
        badges.append("💬")
    badge_str = " " + " ".join(badges) if badges else ""

    markdown = f"**[@{tweet.author}]({url})**{badge_str}\n"
    markdown += f"📅 {timestamp}\n\n"
    markdown += tweet.content
    return markdown


def _mark_selected_as_read(state: AppState, monitor) -> None:
    """Mark the selected tweet as read and clear the badge when nothing is unread."""
    if state.selected_tweet and state.selected_tweet.is_new:
        state.selected_tweet.is_new = False
        state.recalculate_new_count()
    if state.new_tweets_count == 0 and monitor:
        monitor.notifier.clear_badge()
        monitor.save_state()


def _set_status(state: AppState, message: str) -> None:
    """Set a short-lived status message."""
    state.set_status(message, datetime.now(timezone.utc))


def create_key_bindings(
    state: AppState,
    monitor,
    search_overlay,
    layout_factory: Callable[[AppState, Config], object],
) -> KeyBindings:
    """Create keyboard shortcuts."""
    kb = KeyBindings()
    not_searching_filter = search_overlay.not_searching_filter

    @kb.add("j", filter=not_searching_filter)
    @kb.add("down", filter=not_searching_filter)
    def _(event):
        state.select_next()
        state.details_scroll_offset = 0
        _mark_selected_as_read(state, monitor)
        event.app.invalidate()

    @kb.add("k", filter=not_searching_filter)
    @kb.add("up", filter=not_searching_filter)
    def _(event):
        state.select_previous()
        state.details_scroll_offset = 0
        _mark_selected_as_read(state, monitor)
        event.app.invalidate()

    @kb.add("right", filter=not_searching_filter)
    @kb.add("pagedown", filter=not_searching_filter)
    def _(event):
        state.next_page()
        state.details_scroll_offset = 0
        _mark_selected_as_read(state, monitor)
        event.app.invalidate()

    @kb.add("left", filter=not_searching_filter)
    @kb.add("pageup", filter=not_searching_filter)
    def _(event):
        state.prev_page()
        state.details_scroll_offset = 0
        _mark_selected_as_read(state, monitor)
        event.app.invalidate()

    @kb.add("q", filter=not_searching_filter)
    @kb.add("c-c", filter=not_searching_filter)
    def _(event):
        event.app.exit()

    @kb.add("/", filter=not_searching_filter)
    def _(event):
        app = event.app
        state.search_visible = True

        search_overlay.buffer.text = ""
        search_overlay.buffer.state = state
        search_overlay.buffer.cursor_position = 0

        config = search_overlay.current_config
        if config:
            app.layout = layout_factory(state, config)

        focused = False
        for container in app.layout.find_all_windows():
            if hasattr(container, "content") and container.content == search_overlay.control:
                try:
                    app.layout.focus(container)
                    focused = True
                    break
                except ValueError:
                    pass
        if not focused:
            try:
                app.layout.focus_next()
            except Exception:
                pass
        app.invalidate()

    @kb.add("u", filter=not_searching_filter)
    def _(event):
        if state.filter_user:
            state.clear_filters()
            _set_status(state, "已清除用户过滤")
        elif state.selected_tweet:
            target_user = state.selected_tweet.author
            state.apply_user_filter(target_user)
            _set_status(state, f"仅显示 @{target_user} 的推文")

        event.app.invalidate()

    @kb.add("o", filter=not_searching_filter)
    def _(event):
        import webbrowser

        if state.selected_tweet:
            url = f"https://x.com/{state.selected_tweet.author}/status/{state.selected_tweet.id}"
            webbrowser.open(url)
            _set_status(state, f"已打开: {url}")
        event.app.invalidate()

    @kb.add("c", filter=not_searching_filter)
    def _(event):
        if state.selected_tweet:
            try:
                import pyperclip

                markdown = format_tweet_as_markdown(state.selected_tweet)
                pyperclip.copy(markdown)
                _set_status(state, "已复制到剪贴板 (Markdown)")
            except ImportError:
                _set_status(state, "错误: 未安装 pyperclip 库")
            except Exception as exc:
                _set_status(state, f"复制失败: {str(exc)}")
        event.app.invalidate()

    @kb.add("escape", "down", filter=not_searching_filter)
    def _(event):
        state.details_scroll_offset += 1
        event.app.invalidate()

    @kb.add("escape", "up", filter=not_searching_filter)
    def _(event):
        state.details_scroll_offset = max(0, state.details_scroll_offset - 1)
        event.app.invalidate()

    @kb.add("escape", "r", filter=not_searching_filter)
    def _(event):
        if monitor:
            state.mark_all_as_read()
            monitor.notifier.clear_badge()
            monitor.save_state()
            _set_status(state, "已标记所有推文为已读")
        event.app.invalidate()

    return kb
