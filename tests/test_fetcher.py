"""Tests for TweetFetcher network recovery behavior."""

from unittest.mock import AsyncMock

import httpx
import pytest

from src.fetcher import RSSParseError, TweetFetcher


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
