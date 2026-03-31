"""Nitter instance management with automatic failover."""

import logging
from typing import Optional
from urllib.parse import urlparse


logger = logging.getLogger(__name__)


class NitterInstanceManager:
    """管理 Nitter 实例列表并处理自动切换."""

    DEFAULT_INSTANCES = [
        "https://nitter.net",
        "https://nitter.poast.org",
        "https://nitter.privacydev.net",
        "https://nitter.mint.lgbt",
    ]

    def __init__(
        self,
        primary_instance: str,
        failure_threshold: int = 3,
    ):
        self.current_instance = primary_instance.rstrip("/")
        self.failure_threshold = failure_threshold
        self.failure_count = 0

    def record_failure(self, error: Exception) -> Optional[str]:
        """记录失败，达到阈值时返回新实例 URL."""
        self.failure_count += 1
        logger.warning(
            "Instance failure recorded: %s/%s for %s (%s)",
            self.failure_count,
            self.failure_threshold,
            self.current_instance,
            type(error).__name__,
        )

        if self.failure_count >= self.failure_threshold:
            return self._select_next_instance()
        return None

    def record_success(self) -> None:
        """记录成功，重置失败计数."""
        if self.failure_count > 0:
            logger.debug(
                "Instance success recorded, resetting failure count (%s -> 0) for %s",
                self.failure_count,
                self.current_instance,
            )
        self.failure_count = 0

    def _select_next_instance(self) -> Optional[str]:
        """选择下一个可用实例."""
        instances = self.DEFAULT_INSTANCES
        if self.current_instance in instances:
            current_index = instances.index(self.current_instance)
            available = instances[current_index + 1:] + instances[:current_index]
        else:
            available = instances[:]

        if not available:
            logger.warning("No alternative instances available")
            return None

        new_instance = available[0]
        logger.info(
            "Switching instance from %s to %s after %s failures",
            self.current_instance,
            new_instance,
            self.failure_count,
        )
        self.current_instance = new_instance
        self.failure_count = 0
        return new_instance

    def update_terminal_title(self, instance_url: str) -> None:
        """更新终端标题，显示当前实例."""
        domain = urlparse(instance_url).netloc
        title = f"x-monitor [{domain}]"
        print(f"\033]0;{title}\007", end="", flush=True)
        logger.debug(f"Terminal title updated: {title}")
