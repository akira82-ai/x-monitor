"""Nitter instance management with automatic failover."""

import logging
import random
from typing import Optional
from urllib.parse import urlparse

import httpx


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
        http_client: httpx.AsyncClient = None
    ):
        self.current_instance = primary_instance.rstrip("/")
        self.failure_threshold = failure_threshold
        self.failure_count = 0
        self._http_client = http_client

    async def record_failure(self, error: Exception) -> Optional[str]:
        """记录失败，达到阈值时返回新实例 URL."""
        self.failure_count += 1
        logger.debug(
            f"Instance failure recorded: {self.failure_count}/{self.failure_threshold} "
            f"for {self.current_instance}"
        )

        if self.failure_count >= self.failure_threshold:
            return await self._select_next_instance()
        return None

    async def record_success(self) -> None:
        """记录成功，重置失败计数."""
        if self.failure_count > 0:
            logger.debug(
                f"Instance success recorded, resetting failure count "
                f"({self.failure_count} -> 0) for {self.current_instance}"
            )
        self.failure_count = 0

    async def _select_next_instance(self) -> Optional[str]:
        """选择下一个可用实例."""
        instances = self.DEFAULT_INSTANCES
        available = [inst for inst in instances if inst != self.current_instance]

        if not available:
            logger.warning("No alternative instances available")
            return None

        new_instance = random.choice(available)
        logger.info(
            f"Switching instance from {self.current_instance} to {new_instance} "
            f"after {self.failure_count} failures"
        )
        return new_instance

    def update_terminal_title(self, instance_url: str) -> None:
        """更新终端标题，显示当前实例."""
        domain = urlparse(instance_url).netloc
        title = f"x-monitor [{domain}]"
        print(f"\033]0;{title}\007", end="", flush=True)
        logger.debug(f"Terminal title updated: {title}")
