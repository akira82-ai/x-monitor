"""Unit tests for prompt-toolkit background runtime helpers."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from src.config import Config
from src.types import AppState
from src.ui_runtime import cancel_background_task, poll_tweets_background, update_ui_background


def make_config() -> Config:
    """Create a config with a short polling interval for tests."""
    config = Config()
    config.general.poll_interval_sec = 10
    return config


@pytest.mark.asyncio
async def test_poll_tweets_background_refreshes_and_clears_loading(monkeypatch):
    """A successful polling cycle should call refresh and leave the UI idle."""
    state = AppState()
    app = Mock()
    refresh_callback = AsyncMock()
    sleep_calls = 0

    async def fake_sleep(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await poll_tweets_background(state, make_config(), app, refresh_callback)

    refresh_callback.assert_awaited_once()
    assert state.is_loading is False
    assert state.error_message is None
    assert sleep_calls == 1
    assert app.invalidate.call_count == 2


@pytest.mark.asyncio
async def test_poll_tweets_background_records_refresh_error(monkeypatch):
    """Refresh failures should surface as sticky UI errors without crashing the loop."""
    state = AppState()
    app = Mock()
    refresh_callback = AsyncMock(side_effect=RuntimeError("boom"))

    async def fake_sleep(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await poll_tweets_background(state, make_config(), app, refresh_callback)

    refresh_callback.assert_awaited_once()
    assert state.is_loading is False
    assert state.error_message == "boom"
    assert state.error_timestamp is not None
    assert app.invalidate.call_count == 2


@pytest.mark.asyncio
async def test_update_ui_background_invalidates_until_cancelled(monkeypatch):
    """The periodic UI updater should invalidate once per successful tick."""
    app = Mock()
    sleep_calls = 0

    async def fake_sleep(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls == 1:
            return None
        raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await update_ui_background(app)

    assert sleep_calls == 2
    app.invalidate.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_background_task_swallows_cancelled_error():
    """Cancellation helper should await the task and treat normal cancellation as clean exit."""

    async def worker():
        await asyncio.sleep(60)

    task = asyncio.create_task(worker())

    await cancel_background_task(task)

    assert task.done() is True
    assert task.cancelled() is True
