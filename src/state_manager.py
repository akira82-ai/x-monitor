"""State persistence manager for x-monitor."""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

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

    def __init__(self, max_tweets: int = 1000):
        """初始化 StateManager.

        Args:
            max_tweets: 最大保存推文数量，默认 1000
        """
        self.max_tweets = max_tweets
        self.state_path = self._get_state_path()

    @staticmethod
    def _get_state_path() -> Path:
        """Get state file path."""
        # Prefer XDG config directory
        config_dir = Path.home() / ".config" / "x-monitor"
        if config_dir.exists():
            return config_dir / "state.json"

        # Fallback to current directory
        return Path("state.json")

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

    def load(self) -> Optional[AppState]:
        """Load state from file.

        Returns:
            Loaded AppState, or None if file doesn't exist or loading failed
        """
        if not self.state_path.exists():
            return None

        try:
            data = json.loads(self.state_path.read_text())
            state = AppState.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to load state file: {e}")
            return None

        # Limit tweet count (only trim tweets list, don't affect known_ids)
        if len(state.tweets) > self.max_tweets:
            state.tweets = state.tweets[:self.max_tweets]

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
