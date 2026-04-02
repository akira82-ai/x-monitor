"""Tests for in-app subscription actions."""

from unittest.mock import AsyncMock, Mock

import pytest

from src.config import Config
from src.monitor import PollResult
from src.subscription_actions import SubscriptionActions, normalize_handle, validate_handle
from src.types import AppState


def make_poll_result(successful_handles: int, tweet_count: int = 0) -> PollResult:
    """Build a minimal poll result for add-subscription tests."""
    result = PollResult(successful_handles=successful_handles)
    result.handle_results.append(
        Mock(tweet_count=tweet_count)
    )
    return result


def test_normalize_handle_strips_at_symbol_and_spaces():
    """Raw pasted handles should be normalized before validation."""
    assert normalize_handle("  @dotey  ") == "dotey"


def test_validate_handle_rejects_invalid_inputs():
    """Input validation should block empty, duplicate, and malformed handles."""
    with pytest.raises(ValueError, match="请输入账号名"):
        validate_handle("   ", [])

    with pytest.raises(ValueError, match="已订阅"):
        validate_handle("@dotey", ["dotey"])

    with pytest.raises(ValueError, match="格式无效"):
        validate_handle("bad-handle", [])


@pytest.mark.asyncio
async def test_add_handle_persists_selects_and_fetches():
    """Successful adds should save config, select the new user, and trigger the first fetch."""
    config = Config()
    config.users.handles = ["sama"]
    config.save = Mock()
    state = AppState()
    state.set_monitored_handles(config.users.handles)
    monitor = Mock(fetch_handle_now=AsyncMock(return_value=make_poll_result(1, tweet_count=3)))
    actions = SubscriptionActions(config, state, monitor)

    result = await actions.add_handle("@dotey")

    assert result.handle == "dotey"
    assert result.fetch_succeeded is True
    assert config.users.handles == ["sama", "dotey"]
    config.save.assert_called_once_with("config.toml")
    monitor.fetch_handle_now.assert_awaited_once_with("dotey", notify=False)
    assert state.current_user == "dotey"
    assert state.status_message == "已订阅 @dotey，首次拉取成功"


@pytest.mark.asyncio
async def test_add_handle_keeps_subscription_when_first_fetch_fails():
    """A fetch failure should not roll back the saved subscription."""
    config = Config()
    config.users.handles = ["sama"]
    config.save = Mock()
    state = AppState()
    state.set_monitored_handles(config.users.handles)
    monitor = Mock(fetch_handle_now=AsyncMock(return_value=make_poll_result(0)))
    actions = SubscriptionActions(config, state, monitor)

    result = await actions.add_handle("dotey")

    assert result.fetch_succeeded is False
    assert "dotey" in config.users.handles
    assert state.current_user == "dotey"
    assert state.error_message == "已订阅 @dotey，但首次拉取失败"


@pytest.mark.asyncio
async def test_add_handle_rolls_back_config_when_save_fails():
    """Config persistence failures should not leave unsaved handles in memory."""
    config = Config()
    config.users.handles = ["sama"]
    config.save = Mock(side_effect=OSError("disk full"))
    state = AppState()
    monitor = Mock(fetch_handle_now=AsyncMock())
    actions = SubscriptionActions(config, state, monitor)

    with pytest.raises(OSError, match="disk full"):
        await actions.add_handle("dotey")

    assert config.users.handles == ["sama"]
    monitor.fetch_handle_now.assert_not_called()
