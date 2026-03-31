"""User-visible status text helpers for the TUI."""

from urllib.parse import urlparse

from .types import AppState


def get_status_text(state: AppState) -> str:
    """Generate status bar text."""
    if state.status_message and state.status_message != "Initializing..." and state.status_message_timestamp:
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        if (now - state.status_message_timestamp) < timedelta(seconds=3):
            return f"▶ • {state.status_message}"
        state.clear_status()

    if state.error_message and state.error_timestamp:
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        if (now - state.error_timestamp) < timedelta(seconds=5):
            return f"❌ 错误: {state.error_message}"
        state.clear_error()

    if state.is_loading:
        return "⏳ 加载中..."

    new_count = f"🔔 {state.new_tweets_count} 条新 • " if state.new_tweets_count > 0 else ""
    total = f"{len(state.tweets)} 条"

    page_info = ""
    if state.total_pages > 0:
        page_info = f" • {state.current_page + 1}/{state.total_pages} 页"

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

    instance_info = ""
    if state.current_instance:
        domain = urlparse(state.current_instance).netloc
        if domain:
            instance_info = f" • {domain}"

    filter_info = ""
    if state.filter_keyword:
        filter_info += f" [过滤关键词: {state.filter_keyword}]"
    if state.filter_user:
        filter_info += f" [用户: @{state.filter_user}]"

    return f"▶ • {new_count}{total}{page_info}{last_update}{instance_info}{filter_info}"
