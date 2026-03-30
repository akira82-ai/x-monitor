"""Monitoring logic for x-monitor."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Optional

import httpx

from .config import Config
from .fetcher import TweetFetcher
from .types import AppState
from .notifier import Notifier
from .instance_manager import NitterInstanceManager


logger = logging.getLogger(__name__)


# Import StateManager for type hints
try:
    from .state_manager import StateManager
except ImportError:
    StateManager = None  # type: ignore


class Monitor:
    """Main monitor that coordinates polling and state management."""

    def __init__(self, config: Config, state: AppState, state_manager: Optional["StateManager"] = None):
        """Initialize the monitor with configuration and state."""
        self.config = config
        self.state = state
        self.state_manager = state_manager
        self.fetcher = TweetFetcher(config.general.nitter_instance)
        self.notifier = Notifier(config)
        self._running = False
        self._task: Optional[asyncio.Task] = None

        self.instance_manager = NitterInstanceManager(
            primary_instance=config.general.nitter_instance,
            failure_threshold=3,
            http_client=self.fetcher.client
        )
        self.state.current_instance = config.general.nitter_instance

    def _set_status_message(self, message: str) -> None:
        """Set a transient status message visible in the UI."""
        self.state.status_message = message
        self.state.status_message_timestamp = datetime.now(timezone.utc)

    def _set_error_message(self, message: str) -> None:
        """Set a persistent error message until a successful poll clears it."""
        self.state.error_message = message
        self.state.error_timestamp = datetime.now(timezone.utc)

    def _mark_successful_poll(self, total_new: int, successful_handles: int, had_error: bool, switched_instance: bool) -> None:
        """Update success state after at least one handle was fetched successfully."""
        self.state.last_poll = datetime.now(timezone.utc)
        self.state.error_message = None
        self.state.error_timestamp = None

        if had_error:
            self._set_status_message("网络恢复后已重新连接")
        elif switched_instance:
            self._set_status_message(f"实例已切换: {self.state.current_instance}")
        elif total_new == 0:
            self._set_status_message("拉取成功但无新推文")
        else:
            self._set_status_message(
                f"Last update: {self.state.last_poll.strftime('%H:%M:%S')} | "
                f"{len(self.state.tweets)} tweets"
            )

        logger.info(
            "Poll succeeded for %s handle(s), total_new=%s, instance=%s",
            successful_handles,
            total_new,
            self.state.current_instance,
        )

    async def _handle_transport_error(
        self,
        handle: str,
        error: Exception,
        retry_count: int,
        max_retries: int,
    ) -> tuple[bool, bool]:
        """Handle transport failures, including client rebuild and instance failover."""
        logger.warning(
            "Fetch failed for %s via %s (%s): %s",
            handle,
            self.fetcher.nitter_instance,
            type(error).__name__,
            error,
        )

        await self.fetcher.rebuild_client(reason=type(error).__name__)
        new_instance = await self.instance_manager.record_failure(error)
        switched_instance = False

        if new_instance:
            await self.fetcher.update_instance(new_instance)
            self.state.current_instance = new_instance
            self.instance_manager.update_terminal_title(new_instance)
            switched_instance = True
            logger.info("Failover activated for %s, new instance=%s", handle, new_instance)

        if retry_count < max_retries:
            logger.info("Retrying %s after transport failure", handle)
            return True, switched_instance

        self._set_error_message(f"本轮拉取失败: @{handle} ({type(error).__name__})")
        return False, switched_instance

    @property
    def is_running(self) -> bool:
        """Check if the monitor is running."""
        return self._running

    async def poll_once(self, progress_callback=None) -> int:
        """Perform a single poll for new tweets. Returns new tweet count."""
        total_new = 0
        successful_handles = 0
        failed_handles = 0
        had_error = self.state.error_message is not None
        switched_instance = False

        for i, handle in enumerate(self.config.users.handles):
            retry_count = 0
            max_retries = 1

            while retry_count <= max_retries:
                try:
                    if progress_callback:
                        progress_callback(handle, "start", "获取中...")

                    tweets = await self.fetcher.fetch_tweets(handle)
                    await self.instance_manager.record_success()
                    successful_handles += 1

                    if self.config.general.filter_replies:
                        tweets = [t for t in tweets if not t.is_reply]

                    for tweet in tweets:
                        if self.state.add_tweet(tweet):
                            total_new += 1

                    if progress_callback:
                        if tweets:
                            progress_callback(handle, "success", f"{len(tweets)} 条推文")
                        else:
                            progress_callback(handle, "success", "无推文")

                    break

                except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
                    failed_handles += 1
                    should_retry, did_switch = await self._handle_transport_error(
                        handle=handle,
                        error=e,
                        retry_count=retry_count,
                        max_retries=max_retries,
                    )
                    switched_instance = switched_instance or did_switch
                    if should_retry:
                        retry_count += 1
                        continue
                    if progress_callback:
                        progress_callback(handle, "failure", str(e))
                    break

                except (OSError, IOError) as e:
                    failed_handles += 1
                    logger.error("File system error for %s: %s", handle, e)
                    self._set_error_message(f"文件系统错误: @{handle}")
                    if progress_callback:
                        progress_callback(handle, "failure", str(e))
                    break

                except Exception as e:
                    failed_handles += 1
                    logger.exception("Unexpected error fetching %s", handle)
                    self._set_error_message(f"本轮拉取失败: @{handle}")
                    if progress_callback:
                        progress_callback(handle, "failure", str(e))
                    break

        # Trim to max tweets
        max_tweets = self.config.general.max_tweets
        if len(self.state.tweets) > max_tweets:
            # 保存当前选中推文的 ID
            selected_id = self.state.selected_tweet.id if self.state.selected_tweet else None

            # 裁剪推文列表
            self.state.tweets = self.state.tweets[:max_tweets]

            # 注意：known_ids 的清理由 StateManager._cleanup_known_ids() 负责
            # 该方法会移除不在当前推文列表中的 ID，允许旧推文重新出现

            # 重新计算计数器，确保与实际 is_new 状态一致
            self.state.recalculate_new_count()

            # 恢复选中项
            if selected_id:
                for i, tweet in enumerate(self.state.tweets):
                    if tweet.id == selected_id:
                        self.state.selected_index = i
                        break
                else:
                    # 选中项被删除，选中第一项
                    self.state.selected_index = 0

        # Sort tweets by timestamp (newest first)
        # 保存当前选中推文的 ID
        selected_id = self.state.selected_tweet.id if self.state.selected_tweet else None
        self.state.tweets.sort(key=lambda t: t.timestamp, reverse=True)

        # 恢复选中项的位置
        if selected_id:
            for i, tweet in enumerate(self.state.tweets):
                if tweet.id == selected_id:
                    self.state.selected_index = i
                    break
            else:
                # 选中项不见了（不应该发生），选中第一项
                self.state.selected_index = 0

        if successful_handles > 0:
            self._mark_successful_poll(
                total_new=total_new,
                successful_handles=successful_handles,
                had_error=had_error,
                switched_instance=switched_instance,
            )
        elif failed_handles > 0:
            logger.warning("Poll failed for all handles; preserving error state")

        # 更新标题和徽章（批量通知）
        if total_new > 0:
            self.notifier.notify_batch(
                new_count=total_new,
                total_unread=self.state.new_tweets_count,
            )

        return total_new

    async def _run_loop(self, on_update: Callable[[], None]) -> None:
        """Run the monitoring loop."""
        self._running = True

        # Initial poll
        await self.poll_once()
        on_update()

        interval = self.config.general.poll_interval_sec

        while self._running:
            await asyncio.sleep(interval)
            await self.poll_once()
            on_update()

    def start(self, on_update: Callable[[], None]) -> asyncio.Task:
        """Start the monitoring loop in a background task."""
        if self._task and not self._task.done():
            return self._task

        self._task = asyncio.create_task(self._run_loop(on_update))
        return self._task

    async def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        await self.fetcher.close()

    async def refresh(self) -> int:
        """Manually trigger a refresh. Returns new tweet count."""
        return await self.poll_once()

    def reset(self) -> None:
        """Reset the monitor state."""
        self.state.clear()
        self.state.status_message = "Reset"

    async def reload_config(self, path: Optional[str] = None) -> None:
        """Reload configuration from file.

        Args:
            path: Optional path to config file. If not provided, uses the default paths.
        """
        from .config import Config

        new_config = Config.load(path)

        await self.fetcher.close()

        self.config = new_config

        self.fetcher = TweetFetcher(new_config.general.nitter_instance)

        self.notifier = Notifier(new_config)

        self.instance_manager = NitterInstanceManager(
            primary_instance=new_config.general.nitter_instance,
            failure_threshold=3,
            http_client=self.fetcher.client
        )
        self.state.current_instance = new_config.general.nitter_instance
        self._set_status_message("配置已重载")

    def save_state(self) -> None:
        """Save current state to file."""
        if not self.state_manager or not self.config.general.persist_state:
            return
        self.state_manager.save(self.state)
