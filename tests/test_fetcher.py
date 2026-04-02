"""Tests for TweetFetcher network recovery behavior."""

import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import Mock

import feedparser
import httpx
import pytest

from src.fetcher import RSSParseError, TweetFetcher
from src.types import Tweet
from src.ui_keybindings import format_tweet_as_markdown


def make_response(status_code: int = 200, text: str = "") -> httpx.Response:
    """Create an HTTPX response with an attached request."""
    request = httpx.Request("GET", "https://nitter.net/test/rss")
    return httpx.Response(status_code=status_code, text=text, request=request)


@pytest.mark.asyncio
async def test_fetch_tweets_propagates_request_error():
    """Network failures should be visible to the monitor layer."""
    fetcher = TweetFetcher("https://nitter.net")
    fetcher.client.get = AsyncMock(
        side_effect=httpx.RequestError("offline", request=httpx.Request("GET", "https://nitter.net/test/rss"))
    )

    with pytest.raises(httpx.RequestError):
        await fetcher.fetch_tweets("test")

    await fetcher.close()


@pytest.mark.asyncio
async def test_fetch_tweets_allows_empty_success_response():
    """A valid but empty feed should not be treated as an error."""
    fetcher = TweetFetcher("https://nitter.net")
    fetcher.client.get = AsyncMock(return_value=make_response(text="<?xml version='1.0'?><rss><channel></channel></rss>"))

    tweets = await fetcher.fetch_tweets("test")

    assert tweets == []
    await fetcher.close()


@pytest.mark.asyncio
async def test_fetch_tweets_raises_parse_error_for_broken_feed():
    """Broken RSS should surface as a parse error instead of silently returning empty."""
    fetcher = TweetFetcher("https://nitter.net")
    fetcher.client.get = AsyncMock(return_value=make_response(text="<rss"))

    with pytest.raises(RSSParseError, match="RSS parsing failed"):
        await fetcher.fetch_tweets("test")

    await fetcher.close()


@pytest.mark.asyncio
async def test_rebuild_client_replaces_old_client():
    """Rebuilding should swap out the HTTP client and close the old one."""
    fetcher = TweetFetcher("https://nitter.net")
    old_client = fetcher.client

    await fetcher.rebuild_client(reason="RequestError")

    assert fetcher.client is not old_client
    assert old_client.is_closed is True
    await fetcher.close()


def test_parse_entry_detects_reply_from_content_pattern():
    """Entries that start with multiple mentions should be recognized as replies."""
    fetcher = TweetFetcher("https://nitter.net")
    entry = feedparser.FeedParserDict(
        {
            "guid": "https://x.com/test/status/123",
            "link": "https://x.com/test/status/123",
            "description": "<p>@alice @bob hello there</p>",
            "published_parsed": time.gmtime(1700000000),
        }
    )

    tweet = fetcher._parse_entry(entry, "test")

    assert tweet.id == "123"
    assert tweet.is_reply is True
    assert tweet.is_retweet is False
    assert tweet.content == "@alice @bob hello there"


def test_parse_rss_skips_malformed_entries(monkeypatch):
    """Malformed entries should be skipped while valid ones are still returned."""
    fetcher = TweetFetcher("https://nitter.net")
    good_tweet = Tweet(
        id="1",
        author="test",
        author_name="TEST",
        content="hello",
        timestamp=datetime.now(timezone.utc),
        url="https://x.com/test/status/1",
    )
    monkeypatch.setattr(
        "src.fetcher.feedparser.parse",
        lambda _content: SimpleNamespace(bozo=False, bozo_exception=None, entries=["good", "bad"]),
    )
    fetcher._parse_entry = Mock(side_effect=[good_tweet, ValueError("broken entry")])

    tweets = fetcher._parse_rss("unused", "test")

    assert tweets == [good_tweet]


def test_format_tweet_as_markdown_uses_local_time():
    """Clipboard markdown should use the same local timestamp format as the details view."""
    tweet = Tweet(
        id="123",
        author="tester",
        author_name="TESTER",
        content="hello",
        timestamp=datetime(2026, 4, 2, 4, 39, 6, tzinfo=timezone.utc),
        url="https://x.com/tester/status/123",
    )

    markdown = format_tweet_as_markdown(tweet)
    local_time = tweet.timestamp.astimezone()
    expected_timestamp = (
        f"{local_time.year}-{local_time.month}-{local_time.day} "
        f"{local_time.hour:02d}:{local_time.minute:02d}:{local_time.second:02d}"
    )

    assert expected_timestamp in markdown
