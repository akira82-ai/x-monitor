"""Monitoring logic for x-monitor."""

import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

import httpx

from .config import Config
from .fetcher import RSSParseError, TweetFetcher
from .types import AppState
from .notifier import Notifier
from .instance_manager import NitterInstanceManager


logger = logging.getLogger(__name__)


# Import StateManager for type hints
try:
    from .state_manager import StateManager
except ImportError:
    StateManager = None  # type: ignore


@dataclass
class HandlePollResult:
    """Polling result for a single monitored handle."""

    handle: str
    outcome: str
    message: str
    tweet_count: int = 0
    new_count: int = 0


@dataclass
class PollResult:
    """Aggregated result for a polling cycle."""

    total_new: int = 0
    successful_handles: int = 0
    failed_handles: int = 0
    switched_instance: bool = False
    recovered: bool = False
    handle_results: list[HandlePollResult] = field(default_factory=list)

    @property
    def total_handles(self) -> int:
        """Get the number of handles processed in this poll."""
        return len(self.handle_results)

    @property
    def has_failures(self) -> bool:
        """Whether this poll had any failures."""
        return self.failed_handles > 0


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
        )
        self.state.current_instance = config.general.nitter_instance

    def _set_status_message(self, message: str) -> None:
        """Set a transient status message visible in the UI."""
        self.state.set_status(message, datetime.now(timezone.utc))

    async def _resolve_maybe_async(self, value):
        """Await values only when the collaborator returns an awaitable."""
        if inspect.isawaitable(value):
            return await value
        return value

    def _set_error_message(self, message: str) -> None:
        """Set a persistent error message until a successful poll clears it."""
        self.state.set_error(message, datetime.now(timezone.utc))

    def _emit_progress(
        self,
        progress_callback,
        handle_result: HandlePollResult,
    ) -> None:
        """Forward a structured progress event when a caller is observing polling."""
        if progress_callback:
            progress_callback(handle_result)

    def _append_handle_result(
        self,
        result: PollResult,
        progress_callback,
        handle_result: HandlePollResult,
    ) -> HandlePollResult:
        """Record and publish a per-handle polling result."""
        result.handle_results.append(handle_result)
        self._emit_progress(progress_callback, handle_result)
        return handle_result

    def _mark_successful_poll(self, total_new: int, successful_handles: int, had_error: bool, switched_instance: bool) -> None:
        """Update success state after at least one handle was fetched successfully."""
        self.state.last_poll = datetime.now(timezone.utc)
        self.state.clear_error()

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

    def _trim_and_sort_tweets(self) -> None:
        """Keep the timeline bounded while preserving the selected tweet when possible."""
        max_tweets = self.config.general.max_tweets
        if len(self.state.tweets) > max_tweets:
            selected_id = self.state.selected_tweet.id if self.state.selected_tweet else None
            self.state.tweets = self.state.tweets[:max_tweets]
            self.state.recalculate_new_count()
            if selected_id:
                for index, tweet in enumerate(self.state.tweets):
                    if tweet.id == selected_id:
                        self.state.selected_index = index
                        break
                else:
                    self.state.selected_index = 0

        selected_id = self.state.selected_tweet.id if self.state.selected_tweet else None
        self.state.tweets.sort(key=lambda tweet: tweet.timestamp, reverse=True)
        if selected_id:
            for index, tweet in enumerate(self.state.tweets):
                if tweet.id == selected_id:
                    self.state.selected_index = index
                    break
            else:
                self.state.selected_index = 0

    def _is_retryable_http_error(self, error: httpx.HTTPStatusError) -> bool:
        """Only retry or fail over for transient HTTP failures."""
        status_code = error.response.status_code
        return status_code == 429 or 500 <= status_code <= 599

    async def _switch_instance(self, handle: str, new_instance: str) -> None:
        """Switch to a new instance and refresh the HTTP client."""
        await self.fetcher.set_instance(new_instance, rebuild_client=False)
        self.state.current_instance = new_instance
        self.instance_manager.update_terminal_title(new_instance)
        logger.info("Failover activated for %s, new instance=%s", handle, new_instance)

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
        new_instance = await self._resolve_maybe_async(self.instance_manager.record_failure(error))
        switched_instance = False

        if new_instance:
            await self._switch_instance(handle, new_instance)
            switched_instance = True

        if retry_count < max_retries:
            logger.info("Retrying %s after transport failure", handle)
            return True, switched_instance

        self._set_error_message(f"本轮拉取失败: @{handle} ({type(error).__name__})")
        return False, switched_instance

    def _handle_parse_error(self, handle: str, error: RSSParseError) -> HandlePollResult:
        """Handle malformed RSS without forcing transport recovery behavior."""
        logger.warning("RSS parse failed for %s via %s: %s", handle, self.fetcher.nitter_instance, error)
        self._set_error_message(f"RSS 解析失败: @{handle}")
        return HandlePollResult(handle=handle, outcome="failure", message=str(error))

    def _filter_fetched_tweets(self, tweets):
        """Apply fetch-time content filters before tweets hit application state."""
        if not self.config.general.filter_replies:
            return tweets
        return [tweet for tweet in tweets if not tweet.is_reply]

    def _ingest_tweets(self, tweets) -> int:
        """Add fetched tweets into state and return the number that were newly seen."""
        new_count = 0
        for tweet in tweets:
            if self.state.add_tweet(tweet):
                new_count += 1
        return new_count

    async def _handle_successful_fetch(
        self,
        handle: str,
        tweets,
        result: PollResult,
        progress_callback,
    ) -> None:
        """Record a successful fetch for one handle."""
        await self._resolve_maybe_async(self.instance_manager.record_success())
        result.successful_handles += 1

        filtered_tweets = self._filter_fetched_tweets(tweets)
        new_count = self._ingest_tweets(filtered_tweets)
        result.total_new += new_count

        self._append_handle_result(
            result,
            progress_callback,
            HandlePollResult(
                handle=handle,
                outcome="success",
                message=f"{len(filtered_tweets)} 条推文" if filtered_tweets else "无推文",
                tweet_count=len(filtered_tweets),
                new_count=new_count,
            ),
        )

    def _record_handle_failure(
        self,
        result: PollResult,
        progress_callback,
        handle: str,
        message: str,
    ) -> None:
        """Record a terminal failure outcome for one handle."""
        result.failed_handles += 1
        self._append_handle_result(
            result,
            progress_callback,
            HandlePollResult(
                handle=handle,
                outcome="failure",
                message=message,
            ),
        )

    async def _handle_fetch_exception(
        self,
        handle: str,
        error: Exception,
        retry_count: int,
        max_retries: int,
        result: PollResult,
        progress_callback,
    ) -> bool:
        """Handle one fetch exception and return whether the handle should retry."""
        if isinstance(error, httpx.HTTPStatusError) and not self._is_retryable_http_error(error):
            self._set_error_message(f"HTTP 错误: @{handle} ({error.response.status_code})")
            self._record_handle_failure(result, progress_callback, handle, str(error))
            return False

        if isinstance(error, (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError)):
            result.failed_handles += 1
            should_retry, did_switch = await self._handle_transport_error(
                handle=handle,
                error=error,
                retry_count=retry_count,
                max_retries=max_retries,
            )
            result.switched_instance = result.switched_instance or did_switch
            if should_retry:
                return True
            self._append_handle_result(
                result,
                progress_callback,
                HandlePollResult(handle=handle, outcome="failure", message=str(error)),
            )
            return False

        if isinstance(error, RSSParseError):
            result.failed_handles += 1
            handle_result = self._handle_parse_error(handle, error)
            self._append_handle_result(result, progress_callback, handle_result)
            return False

        if isinstance(error, (OSError, IOError)):
            logger.error("File system error for %s: %s", handle, error)
            self._set_error_message(f"文件系统错误: @{handle}")
            self._record_handle_failure(result, progress_callback, handle, str(error))
            return False

        logger.exception("Unexpected error fetching %s", handle)
        self._set_error_message(f"本轮拉取失败: @{handle}")
        self._record_handle_failure(result, progress_callback, handle, str(error))
        return False

    async def _poll_handle(self, handle: str, result: PollResult, progress_callback) -> None:
        """Poll a single handle, including one retry for retryable transport failures."""
        retry_count = 0
        max_retries = 1

        while retry_count <= max_retries:
            self._emit_progress(
                progress_callback,
                HandlePollResult(handle=handle, outcome="start", message="获取中..."),
            )
            try:
                tweets = await self.fetcher.fetch_tweets(handle)
                await self._handle_successful_fetch(handle, tweets, result, progress_callback)
                return
            except Exception as error:
                should_retry = await self._handle_fetch_exception(
                    handle=handle,
                    error=error,
                    retry_count=retry_count,
                    max_retries=max_retries,
                    result=result,
                    progress_callback=progress_callback,
                )
                if not should_retry:
                    return
                retry_count += 1

    @property
    def is_running(self) -> bool:
        """Check if the monitor is running."""
        return self._running

    async def poll_once(self, progress_callback=None) -> PollResult:
        """Perform a single poll and return a structured result."""
        result = PollResult()
        had_error = self.state.error_message is not None

        for handle in self.config.users.handles:
            await self._poll_handle(handle, result, progress_callback)

        self._trim_and_sort_tweets()

        if result.successful_handles > 0:
            result.recovered = had_error
            self._mark_successful_poll(
                total_new=result.total_new,
                successful_handles=result.successful_handles,
                had_error=had_error,
                switched_instance=result.switched_instance,
            )
        elif result.failed_handles > 0:
            logger.warning("Poll failed for all handles; preserving error state")

        # 更新标题和徽章（批量通知）
        if result.total_new > 0:
            self.notifier.notify_batch(
                new_count=result.total_new,
                total_unread=self.state.new_tweets_count,
            )

        return result

    async def fetch_handle_now(self, handle: str, notify: bool = False, progress_callback=None) -> PollResult:
        """Immediately fetch one handle using the same recovery chain as background polling."""
        result = PollResult()
        had_error = self.state.error_message is not None

        await self._poll_handle(handle, result, progress_callback)
        self._trim_and_sort_tweets()

        if result.successful_handles > 0:
            self.state.last_poll = datetime.now(timezone.utc)
            if had_error:
                logger.info("Connectivity recovered during direct fetch for %s", handle)
            self.state.clear_error()

        if notify and result.total_new > 0:
            self.notifier.notify_batch(
                new_count=result.total_new,
                total_unread=self.state.new_tweets_count,
            )
        elif self.config.notification.title_badge:
            self.notifier.notify_batch(
                new_count=0,
                total_unread=self.state.new_tweets_count,
            )

        return result

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

    async def refresh(self) -> PollResult:
        """Manually trigger a refresh."""
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
        )
        self.state.current_instance = new_config.general.nitter_instance
        self._set_status_message("配置已重载")

    def save_state(self) -> None:
        """Save current state to file."""
        if not self.state_manager or not self.config.general.persist_state:
            return
        self.state_manager.save(self.state)
