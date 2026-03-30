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
        rss_url = f"{self.nitter_instance}/{handle}/rss"
        response = await self.client.get(rss_url)
        response.raise_for_status()

        content_size = len(response.content)
        if content_size > self.MAX_RSS_SIZE:
            logger.warning(
                "RSS feed too large for %s: %s bytes (max: %s bytes)",
                handle,
                content_size,
                self.MAX_RSS_SIZE,
            )
            return []

        return self._parse_rss(response.text, handle)

    def _parse_rss(self, content: str, handle: str) -> List[Tweet]:
        """Parse RSS feed content into tweets."""
        feed = feedparser.parse(content)

        if feed.bozo and feed.bozo_exception and not feed.entries:
            raise ValueError(f"RSS parsing failed for {handle}: {feed.bozo_exception}")

        tweets = []
        for entry in feed.entries:
            try:
                # Extract tweet ID from GUID or link
                tweet_id = entry.get("guid", entry.get("link", ""))
                if "/" in tweet_id:
                    tweet_id = tweet_id.split("/")[-1]
                if not tweet_id or tweet_id.startswith("http"):
                    # Generate hash ID if no proper ID found
                    tweet_id = hashlib.md5(
                        entry.get("link", "").encode()
                    ).hexdigest()

                # Parse timestamp
                timestamp = datetime.now(timezone.utc)
                if "published" in entry and entry.published_parsed:
                    timestamp = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif "updated" in entry and entry.updated_parsed:
                    timestamp = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

                # Get URL
                url = entry.get("link", f"https://twitter.com/{handle}/status/{tweet_id}")

                # Extract content from description
                content = entry.get("description", "")
                # Strip HTML tags
                content = self._strip_html(content)

                # Check if retweet
                is_retweet = "RT @" in content or content.startswith("RT @")
                # Check if reply
                is_reply = self._is_reply(entry)

                tweet = Tweet(
                    id=tweet_id,
                    author=handle,
                    author_name=handle.upper(),
                    content=content.strip(),
                    timestamp=timestamp,
                    url=url,
                    is_retweet=is_retweet,
                    is_reply=is_reply,
                )
                tweets.append(tweet)

            except Exception as e:
                logger.warning("Skipping malformed RSS entry for %s: %s", handle, e)
                continue

        return tweets

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

    async def update_instance(self, new_instance: str) -> None:
        """更新 Nitter 实例 URL（运行时切换）."""
        old_instance = self.nitter_instance
        self.nitter_instance = new_instance.rstrip("/")
        logger.info("Fetcher instance updated: %s -> %s", old_instance, self.nitter_instance)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
