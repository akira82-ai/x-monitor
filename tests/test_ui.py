"""Smoke tests for user-visible UI status text."""

from datetime import datetime, timedelta, timezone

from src.types import AppState
from src.ui import get_status_text


def test_get_status_text_includes_current_instance_domain():
    """The status bar should expose the active instance domain for diagnostics."""
    state = AppState()
    state.current_instance = "https://nitter.poast.org"
    state.last_poll = datetime.now(timezone.utc) - timedelta(seconds=5)

    status = get_status_text(state)

    assert "nitter.poast.org" in status


def test_get_status_text_prefers_error_message():
    """Errors should remain more prominent than the normal status summary."""
    state = AppState()
    state.current_instance = "https://nitter.net"
    state.error_message = "本轮拉取失败"
    state.error_timestamp = datetime.now(timezone.utc)

    status = get_status_text(state)

    assert status == "❌ 错误: 本轮拉取失败"
