"""Test StateManager functionality."""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timezone

from state_manager import StateManager, atomic_write
from types import Tweet, AppState


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
        assert manager.merge_threshold == 50
        assert manager.state_path is not None
        assert manager.incremental_path is not None

    def test_save_and_load(self):
        """Test saving and loading state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create manager with custom paths
            state_path = Path(tmpdir) / "state.json"
            manager = StateManager(max_tweets=100)
            manager.state_path = state_path
            manager.incremental_path = Path(tmpdir) / "incremental.json"

            # Create state with tweets
            state = AppState()
            tweet = Tweet(
                id="123",
                author="user",
                author_name="USER",
                content="Test tweet",
                timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
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
            manager.incremental_path = Path(tmpdir) / "incremental.json"

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

    def test_save_incremental(self):
        """Test incremental save functionality."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(max_tweets=100)
            manager.state_path = Path(tmpdir) / "state.json"
            manager.incremental_path = Path(tmpdir) / "incremental.json"

            # Initial state
            state = AppState()
            tweet1 = Tweet(
                id="1",
                author="user",
                author_name="USER",
                content="First tweet",
                timestamp=datetime.now(timezone.utc),
                url="https://twitter.com/user/status/1",
                is_retweet=False,
                is_reply=False,
            )
            state.add_tweet(tweet1)

            # Save main state
            manager.save(state)

            # Add new tweets incrementally
            new_tweets = []
            for i in range(3):
                tweet = Tweet(
                    id=f"new_{i}",
                    author="user",
                    author_name="USER",
                    content=f"New tweet {i}",
                    timestamp=datetime.now(timezone.utc),
                    url=f"https://twitter.com/user/status/new_{i}",
                    is_retweet=False,
                    is_reply=False,
                )
                tweet.is_new = True
                new_tweets.append(tweet)

            # Incremental save
            manager.save_incremental(state, new_tweets)

            # Verify incremental file exists
            assert manager.incremental_path.exists()

            # Load and verify tweets are merged
            loaded_state = manager.load()
            # Should have original tweet + new tweets
            assert len(loaded_state.tweets) == 4
            assert loaded_state.tweets[0].id in ["new_0", "new_1", "new_2"]  # New tweets at front

    def test_merge_incremental(self):
        """Test merging incremental file into main file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(max_tweets=100)
            manager.state_path = Path(tmpdir) / "state.json"
            manager.incremental_path = Path(tmpdir) / "incremental.json"

            # Create main state file
            main_state = AppState()
            for i in range(3):
                tweet = Tweet(
                    id=f"main_{i}",
                    author="user",
                    author_name="USER",
                    content=f"Main tweet {i}",
                    timestamp=datetime.now(timezone.utc),
                    url=f"https://twitter.com/user/status/main_{i}",
                    is_retweet=False,
                    is_reply=False,
                )
                tweet.is_new = False
                main_state.tweets.append(tweet)
                main_state.known_ids.add(f"main_{i}")

            manager.save(main_state)

            # Create incremental file
            incremental_tweets = []
            for i in range(2):
                tweet = Tweet(
                    id=f"inc_{i}",
                    author="user",
                    author_name="USER",
                    content=f"Incremental tweet {i}",
                    timestamp=datetime.now(timezone.utc),
                    url=f"https://twitter.com/user/status/inc_{i}",
                    is_retweet=False,
                    is_reply=False,
                )
                incremental_tweets.append(tweet)

            manager.save_incremental(AppState(), incremental_tweets)

            # Merge
            current_state = AppState()
            current_state.tweets = main_state.tweets.copy()
            current_state.known_ids = main_state.known_ids.copy()
            manager.merge_incremental(current_state)

            # Verify incremental file was deleted
            assert not manager.incremental_path.exists()

            # Verify main file contains all tweets
            loaded_state = manager.load()
            assert len(loaded_state.tweets) == 5  # 3 main + 2 incremental

    def test_load_nonexistent_returns_none(self):
        """Test loading when no state files exist returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager()
            manager.state_path = Path(tmpdir) / "nonexistent.json"
            manager.incremental_path = Path(tmpdir) / "nonexistent_inc.json"

            state = manager.load()
            assert state is None

    def test_cleanup_known_ids(self):
        """Test that _cleanup_known_ids removes IDs not in current tweets."""
        manager = StateManager()

        state = AppState()
        # Add tweets
        for i in range(3):
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
            state.tweets.append(tweet)

        # Add extra IDs not in tweets
        state.known_ids = {"0", "1", "2", "999", "888"}

        # Clean up
        manager._cleanup_known_ids(state)

        # Should only have IDs from current tweets
        assert state.known_ids == {"0", "1", "2"}
