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
        from wcwidth import wcwidth as _wcwidth

        def _cw(s: str) -> int:
            return sum(max(0, _wcwidth(c)) for c in s)

        if max_chars < 10:
            max_chars = 10

        if _cw(self.content) <= max_chars:
            return self.content

        target_width = max_chars - 3
        current_width = 0
        result = []

        for char in self.content:
            cw = max(0, _wcwidth(char))
            if current_width + cw > target_width:
                break
            result.append(char)
            current_width += cw

        return ''.join(result) + '...'

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
    status_message_timestamp: Optional[datetime] = None  # When the status message was set
    new_tweets_count: int = 0

    # Filter states
    filter_keyword: Optional[str] = None  # Keyword filter for tweets
    filter_user: Optional[str] = None  # User filter (author)
    unfiltered_tweets: Optional[List[Tweet]] = None  # Backup of full list before filtering

    # Details panel scroll
    details_scroll_offset: int = 0  # Scroll offset for details panel

    # Loading and error states
    is_loading: bool = False  # Loading indicator
    error_message: Optional[str] = None  # Error message to display
    error_timestamp: Optional[datetime] = None  # When the error occurred

    # Search overlay state
    search_visible: bool = False  # 搜索浮层是否可见

    def add_tweet(self, tweet: Tweet) -> bool:
        """Add a tweet and return True if it's new."""
        if tweet.id in self.known_ids:
            return False

        self.known_ids.add(tweet.id)
        tweet.is_new = True  # 确保新推文标记为 True

        # If filtering is active, also add to unfiltered_tweets
        if self.unfiltered_tweets is not None:
            self.unfiltered_tweets.insert(0, tweet)

        self.tweets.insert(0, tweet)
        self.new_tweets_count += 1
        return True

    def add_tweets(self, tweets: List[Tweet]) -> int:
        """Add multiple tweets and return count of new ones."""
        new_count = 0
        for tweet in tweets:
            if self.add_tweet(tweet):
                new_count += 1
        # 确保页码在有效范围内（因为推文数量可能增加了）
        self._clamp_current_page()
        return new_count

    def recalculate_new_count(self) -> None:
        """重新计算未读推文数量，确保与实际 is_new 状态一致."""
        self.new_tweets_count = sum(1 for t in self.tweets if t.is_new)

    def apply_keyword_filter(self, keyword: str) -> None:
        """Apply keyword filter - overrides any existing filter."""
        # Save full list if not already saved
        if self.unfiltered_tweets is None:
            self.unfiltered_tweets = self.tweets.copy()

        # Clear existing user filter and apply keyword filter from full list
        self.filter_user = None
        self.filter_keyword = keyword
        keyword_lower = keyword.lower()
        self.tweets = [t for t in self.unfiltered_tweets if keyword_lower in t.content.lower()]

        # Reset selection state
        self.selected_index = 0
        self.current_page = 0
        self.details_scroll_offset = 0

    def apply_user_filter(self, user: str) -> None:
        """Apply user filter - overrides any existing filter."""
        # Save full list if not already saved
        if self.unfiltered_tweets is None:
            self.unfiltered_tweets = self.tweets.copy()

        # Clear existing keyword filter and apply user filter from full list
        self.filter_keyword = None
        self.filter_user = user
        self.tweets = [t for t in self.unfiltered_tweets if t.author == user]

        # Reset selection state
        self.selected_index = 0
        self.current_page = 0
        self.details_scroll_offset = 0

    def clear_filters(self) -> None:
        """Clear all filters and restore the full tweet list."""
        if self.unfiltered_tweets is not None:
            self.tweets = self.unfiltered_tweets
            self.unfiltered_tweets = None

        self.filter_keyword = None
        self.filter_user = None
        self.selected_index = 0
        self.current_page = 0
        self.details_scroll_offset = 0

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
            # 确保页码和选中项在有效范围内
            self._clamp_current_page()

    @property
    def total_pages(self) -> int:
        """Get total number of pages."""
        if not self.tweets or self.page_size <= 0:
            return 0
        return (len(self.tweets) - 1) // self.page_size + 1

    def _clamp_current_page(self) -> None:
        """确保 current_page 在有效范围内."""
        if not self.tweets or self.page_size <= 0:
            self.current_page = 0
            return

        max_page = max(0, (len(self.tweets) - 1) // self.page_size)
        self.current_page = max(0, min(self.current_page, max_page))

        # 同时确保 selected_index 在有效范围内
        if self.tweets:
            self.selected_index = max(0, min(self.selected_index, len(self.tweets) - 1))
        else:
            self.selected_index = 0

    def ensure_visible(self, viewport_height: int) -> None:
        """Ensure selected item is visible in viewport."""
        # 更新页面大小
        self.update_page_size(viewport_height)
        # 确保选中项在当前页
        if self.tweets and self.page_size > 0:
            target_page = self.selected_index // self.page_size
            # 将当前页设置为选中项所在的页
            self.current_page = target_page
            # 再次验证以确保在有效范围内
            self._clamp_current_page()

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
        self.current_page = 0
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
            "filter_keyword": self.filter_keyword,
            "filter_user": self.filter_user,
            "details_scroll_offset": self.details_scroll_offset,
            # Note: unfiltered_tweets is not persisted (it's only used temporarily during filtering)
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
        state.filter_keyword = data.get("filter_keyword")
        state.filter_user = data.get("filter_user")
        state.details_scroll_offset = data.get("details_scroll_offset", 0)

        if data.get("last_poll"):
            from datetime import datetime, timezone
            state.last_poll = datetime.fromisoformat(data["last_poll"])

        # Reset unfiltered_tweets (filters are not restored from saved state)
        state.unfiltered_tweets = None

        # 确保 current_page 和 selected_index 在有效范围内
        state._clamp_current_page()
        return state
