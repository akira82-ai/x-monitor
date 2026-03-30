"""Test StateManager functionality."""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

from src.state_manager import StateManager, atomic_write
from src.types import Tweet, AppState


class TestAtomicWrite:
    """Test atomic file writing."""

    def test_atomic_write_creates_file(self):
        """Test atomic_write creates file with correct content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "test.json"
            content = '{"test": "data"}'

            atomic_write(test_path, content)

            assert test_path.exists()
            assert test_path.read_text() == content

    def test_atomic_write_overwrites_existing(self):
        """Test atomic_write overwrites existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "test.json"

            # Write initial content
            atomic_write(test_path, '{"old": "data"}')
            assert test_path.read_text() == '{"old": "data"}'

            # Overwrite with new content
            atomic_write(test_path, '{"new": "data"}')
            assert test_path.read_text() == '{"new": "data"}'

    def test_atomic_write_creates_directory(self):
        """Test atomic_write creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "subdir" / "test.json"
            content = '{"test": "data"}'

            atomic_write(test_path, content)

            assert test_path.exists()
            assert test_path.read_text() == content


class TestStateManager:
    """Test StateManager state persistence."""

    def test_init_default_paths(self):
        """Test StateManager initialization with default paths."""
        manager = StateManager()
        assert manager.max_tweets == 1000
        assert manager.state_path is not None

    def test_save_and_load(self):
        """Test saving and loading state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create manager with custom paths
            state_path = Path(tmpdir) / "state.json"
            manager = StateManager(max_tweets=100)
            manager.state_path = state_path

            # Create state with tweets
            state = AppState()
            tweet = Tweet(
                id="123",
                author="user",
                author_name="USER",
                content="Test tweet",
                timestamp=datetime.now(timezone.utc),
                url="https://twitter.com/user/status/123",
                is_retweet=False,
                is_reply=False,
            )
            tweet.is_new = True
            state.tweets.append(tweet)
            state.known_ids.add("123")
            state.new_tweets_count = 1

            # Save
            manager.save(state)

            # Load
            loaded_state = manager.load()
            assert loaded_state is not None
            assert len(loaded_state.tweets) == 1
            assert loaded_state.tweets[0].id == "123"
            assert "123" in loaded_state.known_ids
            assert loaded_state.new_tweets_count == 1

    def test_save_truncates_tweets(self):
        """Test that save truncates tweets to max_tweets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            manager = StateManager(max_tweets=5)
            manager.state_path = state_path

            # Create state with 10 tweets
            state = AppState()
            for i in range(10):
                tweet = Tweet(
                    id=str(i),
                    author="user",
                    author_name="USER",
                    content=f"Tweet {i}",
                    timestamp=datetime.now(timezone.utc),
                    url=f"https://twitter.com/user/status/{i}",
                    is_retweet=False,
                    is_reply=False,
                )
                tweet.is_new = True
                state.tweets.append(tweet)
                state.known_ids.add(str(i))

            state.new_tweets_count = 10

            # Save
            manager.save(state)

            # Load and verify truncation
            loaded_state = manager.load()
            assert len(loaded_state.tweets) == 5
            # Counter should be recalculated
            assert loaded_state.new_tweets_count == 5

    def test_load_nonexistent_returns_none(self):
        """Test loading when no state file exists returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager()
            manager.state_path = Path(tmpdir) / "nonexistent.json"

            state = manager.load()
            assert state is None

    def test_load_clears_new_flag_for_expired_tweets(self):
        """Test tweets older than the expiry window are no longer marked new."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager()
            manager.state_path = Path(tmpdir) / "state.json"

            old_tweet = Tweet(
                id="old",
                author="user",
                author_name="USER",
                content="Old tweet",
                timestamp=datetime.now(timezone.utc) - timedelta(days=8),
                url="https://twitter.com/user/status/old",
                is_retweet=False,
                is_reply=False,
                is_new=True,
            )

            fresh_tweet = Tweet(
                id="fresh",
                author="user",
                author_name="USER",
                content="Fresh tweet",
                timestamp=datetime.now(timezone.utc),
                url="https://twitter.com/user/status/fresh",
                is_retweet=False,
                is_reply=False,
                is_new=True,
            )

            state = AppState(tweets=[old_tweet, fresh_tweet], known_ids={"old", "fresh"})
            state.new_tweets_count = 2
            manager.save(state)

            loaded_state = manager.load()
            assert loaded_state is not None
            assert loaded_state.tweets[0].is_new is False
            assert loaded_state.tweets[1].is_new is True
            assert loaded_state.new_tweets_count == 1
