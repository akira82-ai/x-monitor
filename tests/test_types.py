"""Test Tweet and AppState serialization/deserialization."""

import pytest
from datetime import datetime, timezone

from src.types import AppState, FeedbackState, TimelineState, Tweet, UiState


NOW = datetime.now(timezone.utc)


class TestTweet:
    """Test Tweet serialization."""

    def test_to_dict(self):
        """Test Tweet serialization to dictionary."""
        tweet = Tweet(
            id="123456",
            author="testuser",
            author_name="TESTUSER",
            content="Test tweet content",
            timestamp=NOW,
            url="https://twitter.com/testuser/status/123456",
            is_retweet=False,
            is_reply=False,
        )
        tweet.is_new = True

        data = tweet.to_dict()
        assert data["id"] == "123456"
        assert data["author"] == "testuser"
        assert data["author_name"] == "TESTUSER"
        assert data["content"] == "Test tweet content"
        assert data["timestamp"] == NOW.isoformat()
        assert data["url"] == "https://twitter.com/testuser/status/123456"
        assert data["is_retweet"] is False
        assert data["is_reply"] is False
        assert data["is_new"] is True

    def test_from_dict(self):
        """Test Tweet deserialization from dictionary."""
        data = {
            "id": "123456",
            "author": "testuser",
            "author_name": "TESTUSER",
            "content": "Test tweet content",
            "timestamp": NOW.isoformat(),
            "url": "https://twitter.com/testuser/status/123456",
            "is_retweet": False,
            "is_reply": False,
            "is_new": True,
        }
        tweet = Tweet.from_dict(data)

        assert tweet.id == "123456"
        assert tweet.author == "testuser"
        assert tweet.author_name == "TESTUSER"
        assert tweet.content == "Test tweet content"
        assert tweet.timestamp == NOW
        assert tweet.url == "https://twitter.com/testuser/status/123456"
        assert tweet.is_retweet is False
        assert tweet.is_reply is False
        assert tweet.is_new is True

    def test_round_trip_serialization(self):
        """Test Tweet -> dict -> Tweet preserves all data."""
        original = Tweet(
            id="123456",
            author="testuser",
            author_name="TESTUSER",
            content="Test tweet content",
            timestamp=NOW,
            url="https://twitter.com/testuser/status/123456",
            is_retweet=False,
            is_reply=True,
        )
        original.is_new = True

        # Serialize and deserialize
        data = original.to_dict()
        restored = Tweet.from_dict(data)

        # Check all fields
        assert restored.id == original.id
        assert restored.author == original.author
        assert restored.author_name == original.author_name
        assert restored.content == original.content
        assert restored.timestamp == original.timestamp
        assert restored.url == original.url
        assert restored.is_retweet == original.is_retweet
        assert restored.is_reply == original.is_reply
        assert restored.is_new == original.is_new


class TestAppState:
    """Test AppState serialization and state management."""

    def test_default_values(self):
        """Test default AppState values."""
        state = AppState()
        assert isinstance(state.timeline, TimelineState)
        assert isinstance(state.ui, UiState)
        assert isinstance(state.feedback, FeedbackState)
        assert state.tweets == []
        assert state.known_ids == set()
        assert state.selected_index == 0
        assert state.current_page == 0
        assert state.new_tweets_count == 0
        assert state.paused is False
        assert state.filter_keyword is None
        assert state.filter_user is None

    def test_compat_properties_map_to_nested_state(self):
        """Legacy AppState properties should still map onto the split state objects."""
        state = AppState()

        state.current_instance = "https://nitter.net"
        state.status_message = "ok"
        state.error_message = "err"
        state.selected_index = 3

        assert state.timeline.current_instance == "https://nitter.net"
        assert state.feedback.status_message == "ok"
        assert state.feedback.error_message == "err"
        assert state.ui.selected_index == 3

    def test_to_dict(self):
        """Test AppState serialization to dictionary."""
        state = AppState()
        tweet = Tweet(
            id="123",
            author="user",
            author_name="USER",
            content="Test",
            timestamp=datetime.now(timezone.utc),
            url="https://twitter.com/user/status/123",
            is_retweet=False,
            is_reply=False,
        )
        tweet.is_new = True
        state.tweets.append(tweet)
        state.known_ids.add("123")
        state.new_tweets_count = 1

        data = state.to_dict()
        assert "tweets" in data
        assert "known_ids" in data
        assert data["new_tweets_count"] == 1
        assert len(data["tweets"]) == 1
        assert data["tweets"][0]["id"] == "123"

    def test_from_dict(self):
        """Test AppState deserialization from dictionary."""
        data = {
            "tweets": [
                {
                    "id": "123",
                    "author": "user",
                    "author_name": "USER",
                    "content": "Test",
                    "timestamp": NOW.isoformat(),
                    "url": "https://twitter.com/user/status/123",
                    "is_retweet": False,
                    "is_reply": False,
                    "is_new": True,
                }
            ],
            "known_ids": ["123"],
            "selected_index": 0,
            "current_page": 0,
            "new_tweets_count": 1,
        }
        state = AppState.from_dict(data)

        assert len(state.tweets) == 1
        assert state.tweets[0].id == "123"
        assert "123" in state.known_ids
        assert state.new_tweets_count == 1

    def test_add_tweet_new(self):
        """Test adding a new tweet."""
        state = AppState()
        tweet = Tweet(
            id="123",
            author="user",
            author_name="USER",
            content="Test",
            timestamp=datetime.now(timezone.utc),
            url="https://twitter.com/user/status/123",
            is_retweet=False,
            is_reply=False,
        )

        result = state.add_tweet(tweet)
        assert result is True
        assert len(state.tweets) == 1
        assert state.tweets[0].id == "123"
        assert "123" in state.known_ids
        assert state.new_tweets_count == 1

    def test_add_tweet_duplicate(self):
        """Test adding a duplicate tweet returns False."""
        state = AppState()
        tweet = Tweet(
            id="123",
            author="user",
            author_name="USER",
            content="Test",
            timestamp=datetime.now(timezone.utc),
            url="https://twitter.com/user/status/123",
            is_retweet=False,
            is_reply=False,
        )

        # Add first time
        result1 = state.add_tweet(tweet)
        assert result1 is True

        # Add second time (duplicate)
        result2 = state.add_tweet(tweet)
        assert result2 is False
        assert len(state.tweets) == 1  # Still only one tweet
        assert state.new_tweets_count == 1  # Counter unchanged

    def test_recalculate_new_count(self):
        """Test recalculation of new tweets count."""
        state = AppState()

        # Add 3 new tweets
        for i in range(3):
            tweet = Tweet(
                id=str(i),
                author="user",
                author_name="USER",
                content=f"Test {i}",
                timestamp=datetime.now(timezone.utc),
                url=f"https://twitter.com/user/status/{i}",
                is_retweet=False,
                is_reply=False,
            )
            tweet.is_new = True
            state.tweets.append(tweet)
            state.known_ids.add(str(i))

        # Manually set wrong count
        state.new_tweets_count = 10

        # Recalculate
        state.recalculate_new_count()
        assert state.new_tweets_count == 3

        # Mark one as read
        state.tweets[0].is_new = False
        state.recalculate_new_count()
        assert state.new_tweets_count == 2

    def test_mark_selected_as_read(self):
        """Test marking selected tweet as read."""
        state = AppState()
        tweet = Tweet(
            id="123",
            author="user",
            author_name="USER",
            content="Test",
            timestamp=datetime.now(timezone.utc),
            url="https://twitter.com/user/status/123",
            is_retweet=False,
            is_reply=False,
        )
        tweet.is_new = True
        state.tweets.append(tweet)
        state.known_ids.add("123")
        state.new_tweets_count = 1
        state.selected_index = 0

        # Mark as read
        state.mark_selected_as_read()
        assert tweet.is_new is False
        assert state.new_tweets_count == 0

    def test_mark_all_as_read(self):
        """Test marking all tweets as read."""
        state = AppState()

        # Add 3 new tweets
        for i in range(3):
            tweet = Tweet(
                id=str(i),
                author="user",
                author_name="USER",
                content=f"Test {i}",
                timestamp=datetime.now(timezone.utc),
                url=f"https://twitter.com/user/status/{i}",
                is_retweet=False,
                is_reply=False,
            )
            tweet.is_new = True
            state.tweets.append(tweet)
            state.known_ids.add(str(i))

        state.new_tweets_count = 3

        # Mark all as read
        state.mark_all_as_read()
        assert all(not t.is_new for t in state.tweets)
        assert state.new_tweets_count == 0

    def test_clear(self):
        """Test clearing all state."""
        state = AppState()
        tweet = Tweet(
            id="123",
            author="user",
            author_name="USER",
            content="Test",
            timestamp=datetime.now(timezone.utc),
            url="https://twitter.com/user/status/123",
            is_retweet=False,
            is_reply=False,
        )
        state.tweets.append(tweet)
        state.known_ids.add("123")
        state.selected_index = 5

        state.clear()
        assert state.tweets == []
        assert state.known_ids == set()
        assert state.selected_index == 0
        assert state.current_page == 0
        assert state.new_tweets_count == 0
