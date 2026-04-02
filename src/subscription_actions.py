"""Application actions for managing monitored subscriptions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from .config import Config
from .monitor import Monitor
from .types import AppState


HANDLE_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,15}$")


@dataclass(frozen=True)
class AddSubscriptionResult:
    """Outcome of adding a new monitored handle."""

    handle: str
    tweet_count: int
    fetch_succeeded: bool


def normalize_handle(raw_handle: str) -> str:
    """Normalize a user-supplied X handle."""
    return raw_handle.strip().lstrip("@").strip()


def validate_handle(raw_handle: str, existing_handles: list[str]) -> str:
    """Validate a new handle and return its normalized value."""
    handle = normalize_handle(raw_handle)
    if not handle:
        raise ValueError("请输入账号名")
    if handle.lower() in {item.lower() for item in existing_handles}:
        raise ValueError(f"@{handle} 已订阅")
    if not HANDLE_PATTERN.fullmatch(handle):
        raise ValueError("账号名格式无效")
    return handle


class SubscriptionActions:
    """Owns mutating application actions around monitored handles."""

    def __init__(self, config: Config, state: AppState, monitor: Monitor):
        self.config = config
        self.state = state
        self.monitor = monitor

    async def add_handle(self, raw_handle: str) -> AddSubscriptionResult:
        """Validate, persist, select, and immediately fetch a new handle."""
        handle = validate_handle(raw_handle, self.config.users.handles)
        self.config.users.handles.append(handle)
        try:
            self.config.save(self.config.get_save_path())
        except Exception:
            self.config.users.handles = [item for item in self.config.users.handles if item.lower() != handle.lower()]
            raise

        self.state.set_monitored_handles(self.config.users.handles)
        self.state.select_user(handle)

        poll_result = await self.monitor.fetch_handle_now(handle, notify=False)
        tweet_count = poll_result.handle_results[0].tweet_count if poll_result.handle_results else 0

        if poll_result.successful_handles > 0:
            message = f"已订阅 @{handle}，首次拉取成功"
            if tweet_count == 0:
                message += "但暂无推文"
            self.state.set_status(message, datetime.now(timezone.utc))
            self.state.clear_error()
            return AddSubscriptionResult(handle=handle, tweet_count=tweet_count, fetch_succeeded=True)

        self.state.set_error(
            f"已订阅 @{handle}，但首次拉取失败",
            datetime.now(timezone.utc),
        )
        return AddSubscriptionResult(handle=handle, tweet_count=0, fetch_succeeded=False)
