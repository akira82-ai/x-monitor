"""Data structures for x-monitor."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class Tweet:
    """Represents a single tweet/post."""
    id: str
    author: str
    author_name: str
    content: str
    timestamp: datetime
    url: str
    likes: Optional[int] = None
    retweets: Optional[int] = None
    replies: Optional[int] = None
    media: List[str] = field(default_factory=list)
    is_retweet: bool = False
    is_reply: bool = False
    is_new: bool = True

    def format_timestamp(self) -> str:
        """Get a formatted timestamp string (date only)."""
        return self.timestamp.strftime("%m-%d")

    def preview(self, max_chars: int = 20) -> str:
        """Get a truncated version of the content."""
        from wcwidth import wcswidth

        # 设置合理的最小值（10 字符）
        if max_chars < 10:
            max_chars = 10

        # 计算实际显示宽度
        display_width = wcswidth(self.content) if wcswidth(self.content) > 0 else len(self.content)

        if display_width <= max_chars:
            return self.content

        # 需要截断：逐字符累加，直到达到 max_chars - 3（为 "..." 预留空间）
        target_width = max_chars - 3
        current_width = 0
        truncate_pos = 0

        for i, char in enumerate(self.content):
            char_width = wcswidth(char) if wcswidth(char) > 0 else 1
            if current_width + char_width > target_width:
                break
            current_width += char_width
            truncate_pos = i + 1

        return f"{self.content[:truncate_pos]}..."

    def to_dict(self) -> dict:
        """将 Tweet 转换为可序列化的字典."""
        return {
            "id": self.id,
            "author": self.author,
            "author_name": self.author_name,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "url": self.url,
            "likes": self.likes,
            "retweets": self.retweets,
            "replies": self.replies,
            "media": self.media,
            "is_retweet": self.is_retweet,
            "is_reply": self.is_reply,
            "is_new": self.is_new,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Tweet":
        """从字典创建 Tweet 对象."""
        from datetime import datetime, timezone
        return cls(
            id=data["id"],
            author=data["author"],
            author_name=data["author_name"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            url=data["url"],
            likes=data.get("likes"),
            retweets=data.get("retweets"),
            replies=data.get("replies"),
            media=data.get("media", []),
            is_retweet=data.get("is_retweet", False),
            is_reply=data.get("is_reply", False),
            is_new=data.get("is_new", False),
        )


@dataclass
class AppState:
    """Application state."""
    tweets: List[Tweet] = field(default_factory=list)
    known_ids: set = field(default_factory=set)
    selected_index: int = 0
    current_page: int = 0  # 当前页码（从 0 开始）
    page_size: int = 10  # 每页行数（会根据屏幕高度动态调整）
    paused: bool = False
    last_poll: Optional[datetime] = None
    status_message: str = "Initializing..."
    new_tweets_count: int = 0

    def add_tweet(self, tweet: Tweet) -> bool:
        """Add a tweet and return True if it's new."""
        if tweet.id in self.known_ids:
            return False

        self.known_ids.add(tweet.id)
        tweet.is_new = True  # 确保新推文标记为 True
        self.tweets.insert(0, tweet)
        self.new_tweets_count += 1
        return True

    def add_tweets(self, tweets: List[Tweet]) -> int:
        """Add multiple tweets and return count of new ones."""
        new_count = 0
        for tweet in tweets:
            if self.add_tweet(tweet):
                new_count += 1
        return new_count

    @property
    def selected_tweet(self) -> Optional[Tweet]:
        """Get the currently selected tweet."""
        if 0 <= self.selected_index < len(self.tweets):
            return self.tweets[self.selected_index]
        return None

    def select_next(self) -> None:
        """Select the next tweet."""
        if self.selected_index < len(self.tweets) - 1:
            self.selected_index += 1
            # 自动翻页
            if self.page_size > 0 and self.selected_index >= (self.current_page + 1) * self.page_size:
                max_page = max(0, (len(self.tweets) - 1) // self.page_size)
                self.current_page = min(self.current_page + 1, max_page)

    def select_previous(self) -> None:
        """Select the previous tweet."""
        if self.selected_index > 0:
            self.selected_index -= 1
            # 自动翻页
            if self.page_size > 0 and self.selected_index < self.current_page * self.page_size:
                self.current_page = max(self.current_page - 1, 0)

    def select_first(self) -> None:
        """Select the first tweet."""
        self.selected_index = 0
        self.current_page = 0

    def select_last(self) -> None:
        """Select the last tweet."""
        if self.tweets:
            self.selected_index = len(self.tweets) - 1
            # 确保页码不超过最大值
            max_page = max(0, (len(self.tweets) - 1) // self.page_size)
            self.current_page = min(self.selected_index // self.page_size, max_page)

    def next_page(self) -> None:
        """Go to next page."""
        if not self.tweets:
            return
        max_page = (len(self.tweets) - 1) // self.page_size
        if self.current_page < max_page:
            self.current_page += 1
            self.selected_index = min(self.current_page * self.page_size, len(self.tweets) - 1)

    def prev_page(self) -> None:
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.selected_index = max(0, min(self.current_page * self.page_size, len(self.tweets) - 1))

    def update_page_size(self, viewport_height: int) -> None:
        """Update page size based on viewport height."""
        if viewport_height > 0:
            self.page_size = viewport_height
            # 调整当前页码，确保选中项仍然可见
            if self.tweets:
                self.current_page = self.selected_index // self.page_size
                # 确保 current_page 不超过最大页码
                max_page = max(0, (len(self.tweets) - 1) // self.page_size)
                self.current_page = min(self.current_page, max_page)

    @property
    def total_pages(self) -> int:
        """Get total number of pages."""
        if not self.tweets:
            return 0
        return (len(self.tweets) - 1) // self.page_size + 1

    def ensure_visible(self, viewport_height: int) -> None:
        """Ensure selected item is visible in viewport."""
        # 更新页面大小
        self.update_page_size(viewport_height)
        # 确保选中项在当前页
        if self.tweets:
            max_page = max(0, (len(self.tweets) - 1) // self.page_size)
            self.current_page = min(self.selected_index // self.page_size, max_page)

    def reset_new_count(self) -> None:
        """Reset the new tweets counter."""
        self.new_tweets_count = 0

    def mark_selected_as_read(self) -> None:
        """将当前选中的推文标记为已读。"""
        if 0 <= self.selected_index < len(self.tweets):
            tweet = self.tweets[self.selected_index]
            if tweet.is_new:
                tweet.is_new = False
                self.new_tweets_count = max(0, self.new_tweets_count - 1)

    def mark_all_as_read(self) -> None:
        """将所有推文标记为已读。"""
        for tweet in self.tweets:
            tweet.is_new = False
        self.new_tweets_count = 0

    def clear(self) -> None:
        """Clear all tweets."""
        self.tweets.clear()
        self.known_ids.clear()
        self.selected_index = 0
        self.new_tweets_count = 0

    def to_dict(self) -> dict:
        """将 AppState 转换为可序列化的字典."""
        return {
            "tweets": [t.to_dict() for t in self.tweets],
            "known_ids": list(self.known_ids),
            "selected_index": self.selected_index,
            "current_page": self.current_page,
            "page_size": self.page_size,
            "paused": self.paused,
            "last_poll": self.last_poll.isoformat() if self.last_poll else None,
            "status_message": self.status_message,
            "new_tweets_count": self.new_tweets_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppState":
        """从字典创建 AppState 对象."""
        state = cls()
        state.tweets = [Tweet.from_dict(t) for t in data.get("tweets", [])]
        state.known_ids = set(data.get("known_ids", []))
        state.selected_index = data.get("selected_index", 0)
        state.current_page = data.get("current_page", 0)
        state.page_size = data.get("page_size", 10)
        state.paused = data.get("paused", False)
        state.status_message = data.get("status_message", "Initializing...")
        state.new_tweets_count = data.get("new_tweets_count", 0)

        if data.get("last_poll"):
            from datetime import datetime, timezone
            state.last_poll = datetime.fromisoformat(data["last_poll"])
        return state
