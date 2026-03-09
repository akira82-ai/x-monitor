"""RSS feed fetcher for x-monitor."""

import hashlib
import feedparser
import httpx
from datetime import datetime, timezone
from typing import Optional, List

from .types import Tweet


class TweetFetcher:
    """Fetch tweets from Nitter RSS feeds."""

    # 需要清除的 SOCKS 代理环境变量名
    _SOCKS_PROXY_ENV_VARS = ('all_proxy', 'ALL_PROXY')

    def __init__(self, nitter_instance: str, timeout: float = 10.0):
        """Initialize the fetcher with a Nitter instance URL."""
        self.nitter_instance = nitter_instance.rstrip("/")
        self.timeout = timeout

        # Use HTTP/HTTPS proxy from environment, but not SOCKS
        # This avoids the socksio dependency issue
        import os
        # 清除 all_proxy 环境变量，避免 httpx 尝试使用 SOCKS 代理
        for env_var in self._SOCKS_PROXY_ENV_VARS:
            os.environ.pop(env_var, None)

        proxy = os.environ.get('https_proxy') or os.environ.get('http_proxy')

        # Create client with HTTP proxy support only
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            follow_redirects=True,
            proxy=proxy,  # Use HTTP/HTTPS proxy explicitly
        )

    async def fetch_tweets(self, handle: str) -> List[Tweet]:
        """Fetch tweets for a specific user via RSS."""
        rss_url = f"{self.nitter_instance}/{handle}/rss"

        try:
            response = await self.client.get(rss_url)
            response.raise_for_status()

            return self._parse_rss(response.text, handle)

        except httpx.HTTPStatusError as e:
            # Silent error handling
            return []
        except httpx.RequestError as e:
            # Silent error handling
            return []
        except Exception as e:
            # Silent error handling
            return []

    def _parse_rss(self, content: str, handle: str) -> List[Tweet]:
        """Parse RSS feed content into tweets."""
        feed = feedparser.parse(content)

        if feed.bozo and feed.bozo_exception:
            # Feed had parsing errors, but might still have entries
            pass

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
                if "published" in entry:
                    timestamp = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif "updated" in entry:
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
                # Silent error handling
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
        """检测 RSS entry 是否为回复推文."""
        # 方法1：检查 in-reply-to 字段（最可靠）
        if entry.get('in-reply-to'):
            return True

        # 方法2：检查标签/分类
        tags = entry.get('tags', [])
        if tags:
            for tag in tags:
                if isinstance(tag, dict) and 'term' in tag:
                    if 'reply' in tag['term'].lower():
                        return True

        # 方法3：内容模式检测（辅助，避免误判）
        content = entry.get('description', '')
        stripped = self._strip_html(content)

        # 排除转推后，检查是否以 @ 开头
        if not (stripped.startswith('RT @') or 'RT @' in stripped):
            # 如果以 @ 开头且有多个 @mentions，很可能是回复
            if stripped.startswith('@'):
                mention_count = stripped.count('@')
                if mention_count >= 2:
                    return True

        return False

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
