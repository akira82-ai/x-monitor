"""Tests for monitor recovery behavior."""

from argparse import Namespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from src.config import Config
from src.monitor import Monitor
from src.types import AppState, Tweet


def make_tweet(tweet_id: str = "1") -> Tweet:
    """Create a minimal tweet for monitor tests."""
    from datetime import datetime, timezone

    return Tweet(
        id=tweet_id,
        author="testuser",
        author_name="TESTUSER",
        content="hello",
        timestamp=datetime.now(timezone.utc),
        url=f"https://x.com/testuser/status/{tweet_id}",
        is_retweet=False,
        is_reply=False,
    )


def make_config() -> Config:
    """Create a config with one monitored handle."""
    config = Config()
    config.users.handles = ["testuser"]
    return config


@pytest.mark.asyncio
async def test_poll_once_does_not_mark_request_error_as_success():
    """Request failures should increment failure handling without resetting as success."""
    monitor = Monitor(make_config(), AppState())
    request = httpx.Request("GET", "https://nitter.net/testuser/rss")

    monitor.fetcher.fetch_tweets = AsyncMock(side_effect=httpx.RequestError("offline", request=request))
    monitor.fetcher.rebuild_client = AsyncMock()
    monitor.instance_manager.record_failure = AsyncMock(return_value=None)
    monitor.instance_manager.record_success = AsyncMock()

    total_new = await monitor.poll_once()

    assert total_new == 0
    assert monitor.instance_manager.record_success.await_count == 0
    assert monitor.instance_manager.record_failure.await_count == 2
    assert monitor.fetcher.rebuild_client.await_count == 2
    assert monitor.state.error_message is not None


@pytest.mark.asyncio
async def test_poll_once_switches_instance_and_recovers():
    """A failover retry should switch instance, rebuild the client, and recover on success."""
    monitor = Monitor(make_config(), AppState())
    request = httpx.Request("GET", "https://nitter.net/testuser/rss")

    monitor.fetcher.fetch_tweets = AsyncMock(
        side_effect=[
            httpx.RequestError("offline", request=request),
            [make_tweet("42")],
        ]
    )
    monitor.fetcher.rebuild_client = AsyncMock()
    monitor.fetcher.update_instance = AsyncMock()
    monitor.instance_manager.record_failure = AsyncMock(return_value="https://nitter.poast.org")
    monitor.instance_manager.record_success = AsyncMock()
    monitor.instance_manager.update_terminal_title = Mock()

    total_new = await monitor.poll_once()

    assert total_new == 1
    assert monitor.fetcher.rebuild_client.await_count == 1
    monitor.fetcher.update_instance.assert_awaited_once_with("https://nitter.poast.org")
    monitor.instance_manager.record_success.assert_awaited_once()
    monitor.instance_manager.update_terminal_title.assert_called_once_with("https://nitter.poast.org")
    assert monitor.state.current_instance == "https://nitter.poast.org"
    assert monitor.state.error_message is None
    assert monitor.state.status_message == "实例已切换: https://nitter.poast.org"


@pytest.mark.asyncio
async def test_poll_once_clears_previous_error_after_recovery():
    """A successful poll after a failure should announce recovery and clear the sticky error."""
    state = AppState(error_message="本轮拉取失败", error_timestamp=None)
    monitor = Monitor(make_config(), state)

    monitor.fetcher.fetch_tweets = AsyncMock(return_value=[])
    monitor.instance_manager.record_failure = AsyncMock()
    monitor.instance_manager.record_success = AsyncMock()

    total_new = await monitor.poll_once()

    assert total_new == 0
    assert monitor.state.error_message is None
    assert monitor.state.status_message == "网络恢复后已重新连接"


@pytest.mark.asyncio
async def test_main_async_uses_monitor_poll_once(monkeypatch):
    """Startup should share the same monitor polling path instead of duplicating fetch logic."""
    from src import main as main_module

    config = make_config()
    fake_tracker = Mock()
    fake_tracker.add_step.side_effect = [f"step_{i}" for i in range(10)]
    fake_monitor = Mock()
    fake_monitor.poll_once = AsyncMock(return_value=0)
    fake_monitor.instance_manager = Mock()
    fake_monitor.instance_manager.update_terminal_title = Mock()
    fake_monitor.notifier = Mock()
    fake_monitor.stop = AsyncMock()
    fake_monitor.save_state = Mock()

    monkeypatch.setattr(
        main_module.argparse.ArgumentParser,
        "parse_args",
        lambda self: Namespace(config=None, create_config=False),
    )
    monkeypatch.setattr(main_module.Config, "load", Mock(return_value=config))
    monkeypatch.setattr(main_module, "StateManager", Mock(return_value=Mock(load=Mock(return_value=None))))
    monkeypatch.setattr(main_module, "StartupTracker", Mock(return_value=fake_tracker))
    monkeypatch.setattr(main_module, "Monitor", Mock(return_value=fake_monitor))

    async def fake_run_ui(config, state, refresh_callback, monitor=None):
        return None

    monkeypatch.setattr(main_module, "run_ui", fake_run_ui)

    await main_module.main_async()

    fake_monitor.poll_once.assert_awaited_once()
