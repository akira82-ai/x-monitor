"""Monitoring logic for x-monitor."""

import asyncio
from datetime import datetime, timezone
from typing import Callable, Optional

from .config import Config
from .fetcher import TweetFetcher
from .types import AppState
from .notifier import Notifier


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

    @property
    def is_running(self) -> bool:
        """Check if the monitor is running."""
        return self._running

    async def poll_once(self, progress_callback=None) -> int:
        """Perform a single poll for new tweets. Returns new tweet count."""
        total_new = 0
        new_tweets_list = []  # 跟踪新增推文

        for i, handle in enumerate(self.config.users.handles):
            try:
                tweets = await self.fetcher.fetch_tweets(handle)

                # 根据配置过滤推文
                if self.config.general.filter_replies:
                    # 过滤掉回复推文
                    tweets = [t for t in tweets if not t.is_reply]

                # Add tweets and notify for new ones
                for tweet in tweets:
                    if self.state.add_tweet(tweet):
                        total_new += 1
                        new_tweets_list.append(tweet)

            except Exception as e:
                # Silent error handling
                self.state.status_message = f"Error: {e}"
            finally:
                if progress_callback:
                    progress_callback(i + 1, len(self.config.users.handles))

        # Trim to max tweets
        max_tweets = self.config.general.max_tweets
        if len(self.state.tweets) > max_tweets:
            # 保存当前选中推文的 ID
            selected_id = self.state.selected_tweet.id if self.state.selected_tweet else None

            # Count how many new tweets are being removed
            removed_tweets = self.state.tweets[max_tweets:]
            removed_new_count = sum(1 for t in removed_tweets if t.is_new)
            self.state.tweets = self.state.tweets[:max_tweets]

            # 从 known_ids 中移除被裁剪推文的 ID
            removed_ids = {t.id for t in removed_tweets}
            self.state.known_ids -= removed_ids

            # Adjust the counter
            self.state.new_tweets_count = max(0, self.state.new_tweets_count - removed_new_count)

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

        # Update status
        self.state.last_poll = datetime.now(timezone.utc)
        self.state.status_message = (
            f"Last update: {self.state.last_poll.strftime('%H:%M:%S')} | "
            f"{len(self.state.tweets)} tweets"
        )

        # 轮询后自动保存
        if self.state_manager and self.config.general.persist_state:
            if self.config.general.incremental_save:
                # 增量保存模式
                self.state_manager.save_incremental(self.state, new_tweets_list)
            else:
                # 全量保存模式（向后兼容）
                self.state_manager.save(self.state)

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

    def reload_config(self, path: Optional[str] = None) -> None:
        """Reload configuration from file.

        Args:
            path: Optional path to config file. If not provided, uses the default paths.
        """
        from .config import Config

        # Load the new config
        new_config = Config.load(path)

        # Update the config
        self.config = new_config

        # Update the fetcher with new nitter instance
        self.fetcher = TweetFetcher(new_config.general.nitter_instance)

        # Update the notifier with new config
        self.notifier = Notifier(new_config)

    def cleanup_and_save(self) -> None:
        """退出前保存状态（合并增量文件）."""
        if not self.state_manager or not self.config.general.persist_state:
            return

        if self.config.general.incremental_save:
            # 退出时强制合并增量文件
            self.state_manager._merge_incremental(self.state)
        else:
            # 全量保存
            self.state_manager.save(self.state)
