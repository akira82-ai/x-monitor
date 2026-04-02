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


def _set_status(state: AppState, message: str) -> None:
    state.set_status(message, datetime.now(timezone.utc))


def _mark_selected_as_read(state: AppState, monitor) -> None:
    """Mark the selected post as read and persist badge changes if needed."""
    tweet = state.selected_tweet
    if tweet and tweet.is_new:
        state.mark_selected_as_read()
        if monitor:
            if state.new_tweets_count == 0:
                monitor.notifier.clear_badge()
            monitor.save_state()


def create_key_bindings(
    state: AppState,
    monitor,
    search_overlay,
    layout_factory: Callable[[AppState, Config], object],
) -> KeyBindings:
    """Create keyboard shortcuts for the three-column UI."""
    kb = KeyBindings()
    focusable_columns = ["users", "posts"]

    def _cycle_focus(step: int) -> None:
        current_column = state.ui.focus_column
        if current_column not in focusable_columns:
            state.ui.focus_column = "posts"
            return
        current_index = focusable_columns.index(current_column)
        state.ui.focus_column = focusable_columns[(current_index + step) % len(focusable_columns)]

    @kb.add("tab")
    def _(event):
        _cycle_focus(1)
        event.app.invalidate()

    @kb.add("s-tab")
    def _(event):
        _cycle_focus(-1)
        event.app.invalidate()

    @kb.add("j")
    @kb.add("down")
    def _(event):
        if state.ui.focus_column == "users":
            state.select_next_user()
            state.current_user_details_scroll_offset = 0
        elif state.ui.focus_column == "posts":
            state.select_next()
            state.current_user_details_scroll_offset = 0
            _mark_selected_as_read(state, monitor)
        event.app.invalidate()

    @kb.add("k")
    @kb.add("up")
    def _(event):
        if state.ui.focus_column == "users":
            state.select_previous_user()
            state.current_user_details_scroll_offset = 0
        elif state.ui.focus_column == "posts":
            state.select_previous()
            state.current_user_details_scroll_offset = 0
            _mark_selected_as_read(state, monitor)
        event.app.invalidate()

    @kb.add("right")
    @kb.add("pagedown")
    def _(event):
        if state.ui.focus_column == "posts":
            state.next_page()
            state.current_user_details_scroll_offset = 0
            _mark_selected_as_read(state, monitor)
            event.app.invalidate()

    @kb.add("left")
    @kb.add("pageup")
    def _(event):
        if state.ui.focus_column == "posts":
            state.prev_page()
            state.current_user_details_scroll_offset = 0
            _mark_selected_as_read(state, monitor)
            event.app.invalidate()

    @kb.add("q")
    @kb.add("c-c")
    def _(event):
        event.app.exit()

    @kb.add("o")
    def _(event):
        import webbrowser

        tweet = state.selected_tweet
        if tweet:
            url = f"https://x.com/{tweet.author}/status/{tweet.id}"
            webbrowser.open(url)
            _set_status(state, f"已打开: {url}")
        event.app.invalidate()

    @kb.add("c")
    def _(event):
        tweet = state.selected_tweet
        if tweet:
            try:
                import pyperclip

                pyperclip.copy(format_tweet_as_markdown(tweet))
                _set_status(state, "已复制到剪贴板 (Markdown)")
            except ImportError:
                _set_status(state, "错误: 未安装 pyperclip 库")
            except Exception as exc:
                _set_status(state, f"复制失败: {str(exc)}")
        event.app.invalidate()

    @kb.add("escape", "down")
    def _(event):
        if state.selected_tweet:
            state.current_user_details_scroll_offset += 1
            event.app.invalidate()

    @kb.add("escape", "up")
    def _(event):
        if state.selected_tweet:
            state.current_user_details_scroll_offset = max(0, state.current_user_details_scroll_offset - 1)
            event.app.invalidate()

    @kb.add("escape", "r")
    def _(event):
        if monitor:
            state.mark_all_as_read()
            monitor.notifier.clear_badge()
            monitor.save_state()
            _set_status(state, "已标记所有推文为已读")
        event.app.invalidate()

    return kb
