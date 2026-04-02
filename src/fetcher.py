"""RSS feed fetcher for x-monitor."""

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import List

import feedparser
import httpx

from .types import Tweet


logger = logging.getLogger(__name__)


class RSSParseError(ValueError):
    """Raised when an RSS response cannot be parsed into entries."""


class TweetFetcher:
    """Fetch tweets from Nitter RSS feeds."""

    # RSS response size limit (10MB)
    MAX_RSS_SIZE = 10 * 1024 * 1024

    def __init__(self, nitter_instance: str, timeout: float = 10.0):
        """Initialize the fetcher with a Nitter instance URL."""
        self.nitter_instance = nitter_instance.rstrip("/")
        self.timeout = timeout
        self.proxy = os.environ.get("https_proxy") or os.environ.get("http_proxy")
        self.client = self._create_client()

    def _create_client(self) -> httpx.AsyncClient:
        """Create a fresh HTTP client instance."""
        # trust_env=False prevents httpx from reading environment variables.
        return httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            follow_redirects=True,
            proxy=self.proxy,
            trust_env=False,
        )

    async def rebuild_client(self, reason: str = "") -> None:
        """Recreate the HTTP client to drop stale connections after failures."""
        old_client = self.client
        self.client = self._create_client()

        log_suffix = f" ({reason})" if reason else ""
        logger.info("Rebuilding HTTP client%s for %s", log_suffix, self.nitter_instance)

        await old_client.aclose()

    async def fetch_tweets(self, handle: str) -> List[Tweet]:
        """Fetch tweets for a specific user via RSS."""
        rss_url = self._build_rss_url(handle)
        response = await self.client.get(rss_url)
        response.raise_for_status()

        if not self._is_response_size_allowed(handle, response.content):
            return []

        return self._parse_rss(response.text, handle)

    def _build_rss_url(self, handle: str) -> str:
        """Build the RSS URL for a monitored handle."""
        return f"{self.nitter_instance}/{handle}/rss"

    def _is_response_size_allowed(self, handle: str, content: bytes) -> bool:
        """Check the RSS payload size and log when it exceeds the safety cap."""
        content_size = len(content)
        if content_size <= self.MAX_RSS_SIZE:
            return True

        logger.warning(
            "RSS feed too large for %s: %s bytes (max: %s bytes)",
            handle,
            content_size,
            self.MAX_RSS_SIZE,
        )
        return False

    def _parse_rss(self, content: str, handle: str) -> List[Tweet]:
        """Parse RSS feed content into tweets."""
        feed = feedparser.parse(content)

        if feed.bozo and feed.bozo_exception and not feed.entries:
            raise RSSParseError(f"RSS parsing failed for {handle}: {feed.bozo_exception}")

        tweets = []
        for entry in feed.entries:
            try:
                tweets.append(self._parse_entry(entry, handle))
            except Exception as e:
                logger.warning("Skipping malformed RSS entry for %s: %s", handle, e)
                continue

        return tweets

    def _parse_entry(self, entry, handle: str) -> Tweet:
        """Convert one RSS entry into a Tweet domain object."""
        content = self._extract_content(entry)

        return Tweet(
            id=self._extract_tweet_id(entry),
            author=handle,
            author_name=handle.upper(),
            content=content.strip(),
            timestamp=self._extract_timestamp(entry),
            url=self._extract_url(entry, handle),
            is_retweet=self._is_retweet_content(content),
            is_reply=self._is_reply(entry),
        )

    def _extract_tweet_id(self, entry) -> str:
        """Extract or synthesize a stable tweet identifier from an RSS entry."""
        tweet_id = entry.get("guid", entry.get("link", ""))
        if "/" in tweet_id:
            tweet_id = tweet_id.split("/")[-1]
        if not tweet_id or tweet_id.startswith("http"):
            tweet_id = hashlib.md5(entry.get("link", "").encode()).hexdigest()
        return tweet_id

    def _extract_timestamp(self, entry) -> datetime:
        """Extract the entry timestamp, falling back to 'now' when absent."""
        if "published" in entry and entry.published_parsed:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if "updated" in entry and entry.updated_parsed:
            return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        return datetime.now(timezone.utc)

    def _extract_url(self, entry, handle: str) -> str:
        """Extract the canonical tweet URL from an entry."""
        tweet_id = self._extract_tweet_id(entry)
        return entry.get("link", f"https://twitter.com/{handle}/status/{tweet_id}")

    def _extract_content(self, entry) -> str:
        """Extract plain text content from an RSS entry."""
        return self._strip_html(entry.get("description", ""))

    @staticmethod
    def _is_retweet_content(content: str) -> bool:
        """Check whether plain text entry content represents a retweet."""
        return "RT @" in content or content.startswith("RT @")

    @staticmethod
    def _strip_html(html: str) -> str:
        """Simple HTML tag stripper."""
        result = []
        in_tag = False
        for ch in html:
            if ch == "<":
                in_tag = True
            elif ch == ">":
                in_tag = False
            elif not in_tag:
                result.append(ch)
        return " ".join("".join(result).split())

    def _is_reply(self, entry) -> bool:
        """Check if RSS entry is a reply tweet."""
        # Method 1: Check in-reply-to field (most reliable)
        if entry.get('in-reply-to'):
            return True

        # Method 2: Check tags/categories
        tags = entry.get('tags', [])
        if tags:
            for tag in tags:
                if isinstance(tag, dict) and 'term' in tag:
                    if 'reply' in tag['term'].lower():
                        return True

        # Method 3: Content pattern detection (auxiliary, avoid false positives)
        content = entry.get('description', '')
        stripped = self._strip_html(content)

        # After excluding retweets, check if starts with @
        if not (stripped.startswith('RT @') or 'RT @' in stripped):
            # If starts with @ and has multiple @mentions, likely a reply
            if stripped.startswith('@'):
                mention_count = stripped.count('@')
                if mention_count >= 2:
                    return True

        return False

    async def set_instance(self, new_instance: str, rebuild_client: bool = False) -> None:
        """Update the active Nitter instance, optionally rebuilding the client."""
        old_instance = self.nitter_instance
        self.nitter_instance = new_instance.rstrip("/")
        logger.info("Fetcher instance updated: %s -> %s", old_instance, self.nitter_instance)
        if rebuild_client:
            await self.rebuild_client(reason="instance switch")

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
