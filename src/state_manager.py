"""State persistence manager for x-monitor."""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

from .types import AppState, Tweet


logger = logging.getLogger(__name__)


def atomic_write(path: Path, content: str) -> None:
    """Write to file atomically.

    Write to a temporary file first, then atomically rename to ensure the
    write process doesn't corrupt the original file.

    Args:
        path: Target file path
        content: Content to write
    """
    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Create temporary file
    fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        # Write content
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        # Atomic rename (overwrite original file)
        os.replace(temp_path, str(path))
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


class StateManager:
    """Manage application state persistence."""

    # Tweet ID expiry time (days), IDs older than this are removed from known_ids
    KNOWN_IDS_EXPIRY_DAYS = 7

    def __init__(self, max_tweets: int = 1000, merge_threshold: int = 50):
        """初始化 StateManager.

        Args:
            max_tweets: 最大保存推文数量，默认 1000
            merge_threshold: 增量文件达到此数量时合并，默认 50
        """
        self.max_tweets = max_tweets
        self.merge_threshold = merge_threshold
        self.state_path = self._get_state_path()
        self.incremental_path = self._get_incremental_path()

    @staticmethod
    def _get_state_path() -> Path:
        """Get state file path."""
        # Prefer XDG config directory
        config_dir = Path.home() / ".config" / "x-monitor"
        if config_dir.exists():
            return config_dir / "state.json"

        # Fallback to current directory
        return Path("state.json")

    @staticmethod
    def _get_incremental_path() -> Path:
        """Get incremental file path."""
        config_dir = Path.home() / ".config" / "x-monitor"
        if config_dir.exists():
            return config_dir / "state.incremental.json"
        return Path("state.incremental.json")

    def save(self, state: AppState) -> None:
        """Save state to file.

        Args:
            state: AppState to save
        """
        # Limit tweet count (only trim tweets list, don't affect known_ids)
        if len(state.tweets) > self.max_tweets:
            state.tweets = state.tweets[:self.max_tweets]
            # Don't rebuild known_ids, keep trimmed tweet IDs
            # This allows these tweets to reappear in future polls
            # Recalculate counter to ensure consistency with actual is_new flags
            state.recalculate_new_count()

        # Clean up expired known_ids: only keep IDs in current tweets list
        # This allows trimmed tweets to reappear, avoiding permanent loss
        self._cleanup_known_ids(state)

        try:
            # Serialize and save (using atomic write)
            data = state.to_dict()
            atomic_write(self.state_path, json.dumps(data, indent=2, ensure_ascii=False))
        except (OSError, IOError) as e:
            # Log save failure
            logger.warning(f"Failed to save state to {self.state_path}: {e}")

    def clear(self) -> None:
        """清除保存的状态."""
        if self.state_path.exists():
            self.state_path.unlink()

    def _get_expiry_threshold(self) -> datetime:
        """计算过期时间阈值.

        Returns:
            当前时间减去 KNOWN_IDS_EXPIRY 天后的时间戳
        """
        return datetime.now(timezone.utc) - timedelta(days=self.KNOWN_IDS_EXPIRY_DAYS)

    def _cleanup_known_ids(self, state: AppState) -> None:
        """Clean up known_ids to maintain consistency.

        Strategy: Only keep IDs in the current tweet list.
        This allows trimmed tweets to reappear as "new tweets", avoiding permanent loss.

        Args:
            state: Current AppState
        """
        if not state.tweets:
            # If no tweets, clear all known_ids
            state.known_ids.clear()
            return

        # Get all IDs in current tweet list
        current_tweet_ids = {tweet.id for tweet in state.tweets}

        # Only keep IDs in current tweet list
        # This allows trimmed tweets to reappear, avoiding permanent loss
        state.known_ids = state.known_ids & current_tweet_ids

    def save_incremental(self, state: AppState, new_tweets: List[Tweet]) -> None:
        """增量保存：只保存新增的推文.

        Args:
            state: 当前的 AppState
            new_tweets: 新增的推文列表
        """
        if not new_tweets:
            return

        try:
            # 读取现有增量文件
            existing = []
            if self.incremental_path.exists():
                existing = json.loads(self.incremental_path.read_text()).get("tweets", [])

            # 追加新推文
            all_tweets = existing + [t.to_dict() for t in new_tweets]

            # 写回增量文件（使用原子写入）
            data = {
                "tweets": all_tweets,
                "last_update": datetime.now(timezone.utc).isoformat()
            }
            atomic_write(
                self.incremental_path,
                json.dumps(data, indent=2, ensure_ascii=False)
            )

            # 检查是否需要合并
            if len(all_tweets) >= self.merge_threshold:
                self.merge_incremental(state)

        except (OSError, IOError) as e:
            logger.warning(f"Failed to save incremental state: {e}")

    def merge_incremental(self, state: AppState) -> None:
        """Merge incremental file into main file.

        Args:
            state: Current AppState
        """
        try:
            # Load main file
            main_data = {}
            if self.state_path.exists():
                main_data = json.loads(self.state_path.read_text())

            # Load incremental file
            incremental_data = {}
            if self.incremental_path.exists():
                incremental_data = json.loads(self.incremental_path.read_text())

            # Merge tweets (deduplicate)
            main_tweets = {t["id"]: t for t in main_data.get("tweets", [])}
            for t in incremental_data.get("tweets", []):
                main_tweets[t["id"]] = t

            # Override with current memory state's is_new values to ensure read state persists correctly
            if state:
                for tweet in state.tweets:
                    if tweet.id in main_tweets:
                        main_tweets[tweet.id]["is_new"] = tweet.is_new

                # Clean up expired known_ids (before merge)
                self._cleanup_known_ids(state)

            # Sort and limit count
            tweets_list = sorted(
                main_tweets.values(),
                key=lambda x: x["timestamp"],
                reverse=True
            )[:self.max_tweets]

            # Update main file
            main_data["tweets"] = tweets_list
            # Save other state fields
            if state:
                main_data["selected_index"] = state.selected_index
                main_data["current_page"] = state.current_page
                main_data["page_size"] = state.page_size
                main_data["paused"] = state.paused
                main_data["last_poll"] = state.last_poll.isoformat() if state.last_poll else None
                main_data["status_message"] = state.status_message
                main_data["new_tweets_count"] = state.new_tweets_count
                main_data["filter_keyword"] = state.filter_keyword
                main_data["filter_user"] = state.filter_user
                main_data["details_scroll_offset"] = state.details_scroll_offset
                main_data["known_ids"] = list(state.known_ids)

            # Update main file (using atomic write)
            atomic_write(
                self.state_path,
                json.dumps(main_data, indent=2, ensure_ascii=False)
            )

            # Only delete incremental file after main file is written successfully
            # This ensures no incremental data is lost even on failure
            if self.incremental_path.exists():
                try:
                    self.incremental_path.unlink()
                    logger.debug("Incremental file merged and deleted successfully")
                except OSError as e:
                    logger.warning(f"Failed to delete incremental file: {e}")

        except (OSError, IOError, json.JSONDecodeError) as e:
            logger.error(f"Failed to merge incremental file: {e}")
            # If merge fails, keep incremental file for retry on next startup

    def load(self) -> Optional[AppState]:
        """Load state (main file + incremental file).

        Returns:
            Loaded AppState, or None if files don't exist or loading failed
        """
        if not self.state_path.exists() and not self.incremental_path.exists():
            return None

        state = AppState()

        # Load main file
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text())
                state = AppState.from_dict(data)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Failed to load main state file: {e}")

        # Apply incremental file
        if self.incremental_path.exists():
            try:
                data = json.loads(self.incremental_path.read_text())
                for t_dict in data.get("tweets", []):
                    tweet = Tweet.from_dict(t_dict)
                    if tweet.id not in state.known_ids:
                        # Add directly, don't use add_tweet (avoid overwriting is_new)
                        state.known_ids.add(tweet.id)
                        state.tweets.insert(0, tweet)
                        if tweet.is_new:
                            state.new_tweets_count += 1

                # Clear applied incremental file
                self.incremental_path.unlink()
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Failed to load incremental file: {e}")

        # Limit tweet count (only trim tweets list, don't affect known_ids)
        if len(state.tweets) > self.max_tweets:
            state.tweets = state.tweets[:self.max_tweets]
            # Don't rebuild known_ids, keep trimmed tweet IDs
            # This allows these tweets to reappear in future polls

        # Clean up old tweets' new flags (tweets older than 7 days shouldn't be marked as new)
        self._cleanup_old_new_tweets(state)

        # Recalculate to ensure new_tweets_count matches actual is_new flags
        state.recalculate_new_count()

        return state

    def _cleanup_old_new_tweets(self, state: AppState) -> None:
        """Clean up new flags from old tweets.

        Set is_new to False for tweets older than 7 days.

        Args:
            state: Current AppState
        """
        if not state.tweets:
            return

        # Calculate expiry time (7 days ago)
        expiry_threshold = self._get_expiry_threshold()

        # Clean up new flags from old tweets
        for tweet in state.tweets:
            if tweet.is_new and tweet.timestamp < expiry_threshold:
                tweet.is_new = False
