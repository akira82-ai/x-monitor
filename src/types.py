"""Data structures for x-monitor."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

from .time_utils import format_local_month_day


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
        return format_local_month_day(self.timestamp)

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
class TimelineState:
    """Domain state for the monitored timeline."""

    tweets: List[Tweet] = field(default_factory=list)
    known_ids: set = field(default_factory=set)
    last_poll: Optional[datetime] = None
    new_tweets_count: int = 0
    current_instance: Optional[str] = None


@dataclass
class UiState:
    """Presentation state for the terminal UI."""

    page_size: int = 10
    paused: bool = False
    filter_keyword: Optional[str] = None
    filter_user: Optional[str] = None
    unfiltered_tweets: Optional[List[Tweet]] = None
    is_loading: bool = False
    search_visible: bool = False
    monitored_handles: List[str] = field(default_factory=list)
    selected_user_index: int = 0
    focus_column: str = "users"
    per_user_selected_post_index: dict = field(default_factory=dict)
    per_user_current_page: dict = field(default_factory=dict)
    per_user_details_scroll_offset: dict = field(default_factory=dict)

    @property
    def selected_index(self) -> int:
        """Backward-compatible alias for the old single-list selection index."""
        return self.selected_user_index

    @selected_index.setter
    def selected_index(self, value: int) -> None:
        self.selected_user_index = value

    @property
    def current_page(self) -> int:
        """Backward-compatible alias for the old single-list current page."""
        return self.selected_user_index

    @current_page.setter
    def current_page(self, value: int) -> None:
        self.selected_user_index = value

    @property
    def details_scroll_offset(self) -> int:
        """Backward-compatible alias for the old single-list detail offset."""
        return self.selected_user_index

    @details_scroll_offset.setter
    def details_scroll_offset(self, value: int) -> None:
        self.selected_user_index = value


@dataclass
class FeedbackState:
    """Transient user-facing messages and errors."""

    status_message: str = "Initializing..."
    status_message_timestamp: Optional[datetime] = None
    error_message: Optional[str] = None
    error_timestamp: Optional[datetime] = None


@dataclass(init=False)
class AppState:
    """Application state composed of domain, UI, and feedback concerns."""

    timeline: TimelineState = field(default_factory=TimelineState)
    ui: UiState = field(default_factory=UiState)
    feedback: FeedbackState = field(default_factory=FeedbackState)

    # Expiry time for new tweets (days)
    NEW_TWEET_EXPIRY_DAYS = 7

    def __init__(
        self,
        timeline: Optional[TimelineState] = None,
        ui: Optional[UiState] = None,
        feedback: Optional[FeedbackState] = None,
        **legacy_fields,
    ):
        """Initialize state while remaining compatible with legacy keyword construction."""
        self.timeline = timeline if timeline is not None else TimelineState()
        self.ui = ui if ui is not None else UiState()
        self.feedback = feedback if feedback is not None else FeedbackState()

        legacy_map = {
            "tweets": ("timeline", "tweets"),
            "known_ids": ("timeline", "known_ids"),
            "last_poll": ("timeline", "last_poll"),
            "new_tweets_count": ("timeline", "new_tweets_count"),
            "current_instance": ("timeline", "current_instance"),
            "page_size": ("ui", "page_size"),
            "paused": ("ui", "paused"),
            "filter_keyword": ("ui", "filter_keyword"),
            "filter_user": ("ui", "filter_user"),
            "unfiltered_tweets": ("ui", "unfiltered_tweets"),
            "is_loading": ("ui", "is_loading"),
            "search_visible": ("ui", "search_visible"),
            "selected_index": ("ui", "selected_user_index"),
            "current_page": ("ui", "selected_user_index"),
            "details_scroll_offset": ("ui", "selected_user_index"),
            "status_message": ("feedback", "status_message"),
            "status_message_timestamp": ("feedback", "status_message_timestamp"),
            "error_message": ("feedback", "error_message"),
            "error_timestamp": ("feedback", "error_timestamp"),
        }

        for field_name, value in legacy_fields.items():
            if field_name not in legacy_map:
                raise TypeError(f"__init__() got an unexpected keyword argument '{field_name}'")
            group_name, attr_name = legacy_map[field_name]
            getattr(self, group_name).__setattr__(attr_name, value)

    @property
    def tweets(self) -> List[Tweet]:
        return self.timeline.tweets

    @tweets.setter
    def tweets(self, value: List[Tweet]) -> None:
        self.timeline.tweets = value

    @property
    def known_ids(self) -> set:
        return self.timeline.known_ids

    @known_ids.setter
    def known_ids(self, value: set) -> None:
        self.timeline.known_ids = value

    @property
    def last_poll(self) -> Optional[datetime]:
        return self.timeline.last_poll

    @last_poll.setter
    def last_poll(self, value: Optional[datetime]) -> None:
        self.timeline.last_poll = value

    @property
    def new_tweets_count(self) -> int:
        return self.timeline.new_tweets_count

    @new_tweets_count.setter
    def new_tweets_count(self, value: int) -> None:
        self.timeline.new_tweets_count = value

    @property
    def current_instance(self) -> Optional[str]:
        return self.timeline.current_instance

    @current_instance.setter
    def current_instance(self, value: Optional[str]) -> None:
        self.timeline.current_instance = value

    @property
    def selected_index(self) -> int:
        if self.current_user is None:
            return self.ui.selected_user_index
        return self.current_post_index

    @selected_index.setter
    def selected_index(self, value: int) -> None:
        if self.current_user is None:
            self.ui.selected_user_index = value
        else:
            self.current_post_index = value

    @property
    def current_page(self) -> int:
        if self.current_user is None:
            return self.ui.selected_user_index
        return self.current_user_page

    @current_page.setter
    def current_page(self, value: int) -> None:
        if self.current_user is None:
            self.ui.selected_user_index = value
        else:
            self.current_user_page = value

    @property
    def page_size(self) -> int:
        return self.ui.page_size

    @page_size.setter
    def page_size(self, value: int) -> None:
        self.ui.page_size = value

    @property
    def paused(self) -> bool:
        return self.ui.paused

    @paused.setter
    def paused(self, value: bool) -> None:
        self.ui.paused = value

    @property
    def filter_keyword(self) -> Optional[str]:
        return self.ui.filter_keyword

    @filter_keyword.setter
    def filter_keyword(self, value: Optional[str]) -> None:
        self.ui.filter_keyword = value

    @property
    def filter_user(self) -> Optional[str]:
        return self.ui.filter_user

    @filter_user.setter
    def filter_user(self, value: Optional[str]) -> None:
        self.ui.filter_user = value

    @property
    def unfiltered_tweets(self) -> Optional[List[Tweet]]:
        return self.ui.unfiltered_tweets

    @unfiltered_tweets.setter
    def unfiltered_tweets(self, value: Optional[List[Tweet]]) -> None:
        self.ui.unfiltered_tweets = value

    @property
    def details_scroll_offset(self) -> int:
        if self.current_user is None:
            return self.ui.selected_user_index
        return self.current_user_details_scroll_offset

    @details_scroll_offset.setter
    def details_scroll_offset(self, value: int) -> None:
        if self.current_user is None:
            self.ui.selected_user_index = value
        else:
            self.current_user_details_scroll_offset = value

    @property
    def is_loading(self) -> bool:
        return self.ui.is_loading

    @is_loading.setter
    def is_loading(self, value: bool) -> None:
        self.ui.is_loading = value

    @property
    def search_visible(self) -> bool:
        return self.ui.search_visible

    @search_visible.setter
    def search_visible(self, value: bool) -> None:
        self.ui.search_visible = value

    @property
    def status_message(self) -> str:
        return self.feedback.status_message

    @status_message.setter
    def status_message(self, value: str) -> None:
        self.feedback.status_message = value

    @property
    def status_message_timestamp(self) -> Optional[datetime]:
        return self.feedback.status_message_timestamp

    @status_message_timestamp.setter
    def status_message_timestamp(self, value: Optional[datetime]) -> None:
        self.feedback.status_message_timestamp = value

    @property
    def error_message(self) -> Optional[str]:
        return self.feedback.error_message

    @error_message.setter
    def error_message(self, value: Optional[str]) -> None:
        self.feedback.error_message = value

    @property
    def error_timestamp(self) -> Optional[datetime]:
        return self.feedback.error_timestamp

    @error_timestamp.setter
    def error_timestamp(self, value: Optional[datetime]) -> None:
        self.feedback.error_timestamp = value

    def set_status(self, message: str, timestamp: Optional[datetime] = None) -> None:
        """Set a transient user-facing status message."""
        self.feedback.status_message = message
        self.feedback.status_message_timestamp = timestamp

    def clear_status(self) -> None:
        """Clear the current status message."""
        self.feedback.status_message = "Initializing..."
        self.feedback.status_message_timestamp = None

    def set_error(self, message: str, timestamp: Optional[datetime] = None) -> None:
        """Set a sticky error message."""
        self.feedback.error_message = message
        self.feedback.error_timestamp = timestamp

    def clear_error(self) -> None:
        """Clear the current error message."""
        self.feedback.error_message = None
        self.feedback.error_timestamp = None

    def _cleanup_old_new_tweets(self) -> None:
        """清理过期的未读标记（7天以上的推文不再标记为未读）."""
        from datetime import datetime, timezone, timedelta

        expiry_threshold = datetime.now(timezone.utc) - timedelta(days=self.NEW_TWEET_EXPIRY_DAYS)

        for tweet in self.tweets:
            if tweet.is_new and tweet.timestamp < expiry_threshold:
                tweet.is_new = False

    def add_tweet(self, tweet: Tweet) -> bool:
        """Add a tweet and return True if it's new."""
        if tweet.id in self.known_ids:
            return False

        self.known_ids.add(tweet.id)
        tweet.is_new = True  # Ensure new tweets are marked as True

        # If filtering is active, also add to unfiltered_tweets
        if self.unfiltered_tweets is not None:
            self.unfiltered_tweets.insert(0, tweet)

        self.tweets.insert(0, tweet)
        self.new_tweets_count += 1
        self.ensure_user_handles()
        return True

    def add_tweets(self, tweets: List[Tweet]) -> int:
        """Add multiple tweets and return count of new ones."""
        new_count = 0
        for tweet in tweets:
            if self.add_tweet(tweet):
                new_count += 1
        # Ensure page number is within valid range (since tweet count may have increased)
        self._clamp_current_user_page()
        self._clamp_selected_post_index()
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
        self.current_post_index = 0
        self.current_user_page = 0
        self.current_user_details_scroll_offset = 0

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
        self.current_post_index = 0
        self.current_user_page = 0
        self.current_user_details_scroll_offset = 0

    def clear_filters(self) -> None:
        """Clear all filters and restore the full tweet list."""
        if self.unfiltered_tweets is not None:
            self.tweets = self.unfiltered_tweets
            self.unfiltered_tweets = None

        self.filter_keyword = None
        self.filter_user = None
        self.current_post_index = 0
        self.current_user_page = 0
        self.current_user_details_scroll_offset = 0

    def set_monitored_handles(self, handles: List[str]) -> None:
        """Update the configured handles shown in the left navigation."""
        self.ui.monitored_handles = list(handles)
        self.ensure_user_handles()
        self._clamp_selected_user()

    @property
    def sorted_users(self) -> List[str]:
        """Get monitored users sorted alphabetically."""
        users = set(self.ui.monitored_handles)
        users.update(tweet.author for tweet in self.tweets)
        return sorted(users, key=str.lower)

    def ensure_user_handles(self) -> None:
        """Keep per-user UI state initialized for all visible users."""
        for handle in self.sorted_users:
            self.ui.per_user_selected_post_index.setdefault(handle, 0)
            self.ui.per_user_current_page.setdefault(handle, 0)
            self.ui.per_user_details_scroll_offset.setdefault(handle, 0)

    def _clamp_selected_user(self) -> None:
        """Ensure the selected user index remains in range."""
        users = self.sorted_users
        if not users:
            self.ui.selected_user_index = 0
            return
        self.ui.selected_user_index = max(0, min(self.ui.selected_user_index, len(users) - 1))

    @property
    def current_user(self) -> Optional[str]:
        """Get the currently selected user."""
        users = self.sorted_users
        if not users:
            return None
        self._clamp_selected_user()
        return users[self.ui.selected_user_index]

    @property
    def current_user_tweets(self) -> List[Tweet]:
        """Get tweets for the selected user in newest-first order."""
        handle = self.current_user
        if not handle:
            return []
        tweets = [tweet for tweet in self.tweets if tweet.author == handle]
        return sorted(tweets, key=lambda tweet: tweet.timestamp, reverse=True)

    def unread_count_for_user(self, handle: str) -> int:
        """Return the unread count for one user."""
        return sum(1 for tweet in self.tweets if tweet.author == handle and tweet.is_new)

    @property
    def current_post_index(self) -> int:
        """Get the selected post index for the current user."""
        handle = self.current_user
        if not handle:
            return 0
        self.ensure_user_handles()
        return self.ui.per_user_selected_post_index[handle]

    @current_post_index.setter
    def current_post_index(self, value: int) -> None:
        handle = self.current_user
        if not handle:
            return
        self.ensure_user_handles()
        self.ui.per_user_selected_post_index[handle] = value
        self._clamp_selected_post_index()

    @property
    def current_user_page(self) -> int:
        """Get the current page for the selected user's posts."""
        handle = self.current_user
        if not handle:
            return 0
        self.ensure_user_handles()
        return self.ui.per_user_current_page[handle]

    @current_user_page.setter
    def current_user_page(self, value: int) -> None:
        handle = self.current_user
        if not handle:
            return
        self.ensure_user_handles()
        self.ui.per_user_current_page[handle] = value
        self._clamp_current_user_page()

    @property
    def current_user_details_scroll_offset(self) -> int:
        """Get the details scroll offset for the current user."""
        handle = self.current_user
        if not handle:
            return 0
        self.ensure_user_handles()
        return self.ui.per_user_details_scroll_offset[handle]

    @current_user_details_scroll_offset.setter
    def current_user_details_scroll_offset(self, value: int) -> None:
        handle = self.current_user
        if not handle:
            return
        self.ensure_user_handles()
        self.ui.per_user_details_scroll_offset[handle] = max(0, value)

    @property
    def current_user_total_pages(self) -> int:
        """Get total pages for the selected user's posts."""
        tweets = self.current_user_tweets
        if not tweets or self.page_size <= 0:
            return 0
        return (len(tweets) - 1) // self.page_size + 1

    def _clamp_selected_post_index(self) -> None:
        """Keep the current user's selected post index in range."""
        tweets = self.current_user_tweets
        handle = self.current_user
        if handle is None or self.page_size <= 0 or not tweets:
            if handle is not None:
                self.ui.per_user_selected_post_index[handle] = 0
            return
        max_index = len(tweets) - 1
        self.ui.per_user_selected_post_index[handle] = max(
            0,
            min(self.ui.per_user_selected_post_index[handle], max_index),
        )
        self.ui.per_user_current_page[handle] = self.ui.per_user_selected_post_index[handle] // self.page_size

    def _clamp_current_user_page(self) -> None:
        """Keep the current user's page index in range without changing selection."""
        tweets = self.current_user_tweets
        handle = self.current_user
        if handle is None or self.page_size <= 0 or not tweets:
            if handle is not None:
                self.ui.per_user_current_page[handle] = 0
            return
        max_page = max(0, (len(tweets) - 1) // self.page_size)
        self.ui.per_user_current_page[handle] = max(
            0,
            min(self.ui.per_user_current_page[handle], max_page),
        )

    def select_next_user(self) -> None:
        """Select the next user in the left navigation."""
        users = self.sorted_users
        if not users:
            return
        if self.ui.selected_user_index < len(users) - 1:
            self.ui.selected_user_index += 1
        self._clamp_current_user_page()
        self._clamp_selected_post_index()

    def select_previous_user(self) -> None:
        """Select the previous user in the left navigation."""
        if self.ui.selected_user_index > 0:
            self.ui.selected_user_index -= 1
        self._clamp_current_user_page()
        self._clamp_selected_post_index()

    @property
    def selected_tweet(self) -> Optional[Tweet]:
        """Get the currently selected tweet."""
        tweets = self.current_user_tweets
        if 0 <= self.current_post_index < len(tweets):
            return tweets[self.current_post_index]
        return None

    def select_next(self) -> None:
        """Select the next tweet."""
        tweets = self.current_user_tweets
        if self.current_post_index < len(tweets) - 1:
            self.current_post_index += 1
            if self.page_size > 0 and self.current_post_index >= (self.current_user_page + 1) * self.page_size:
                max_page = max(0, (len(tweets) - 1) // self.page_size)
                self.current_user_page = min(self.current_user_page + 1, max_page)

    def select_previous(self) -> None:
        """Select the previous tweet."""
        if self.current_post_index > 0:
            self.current_post_index -= 1
            if self.page_size > 0 and self.current_post_index < self.current_user_page * self.page_size:
                self.current_user_page = max(self.current_user_page - 1, 0)

    def select_first(self) -> None:
        """Select the first tweet."""
        self.current_post_index = 0
        self.current_user_page = 0

    def select_last(self) -> None:
        """Select the last tweet."""
        tweets = self.current_user_tweets
        if tweets:
            self.current_post_index = len(tweets) - 1
            max_page = max(0, (len(tweets) - 1) // self.page_size)
            self.current_user_page = min(self.current_post_index // self.page_size, max_page)

    def next_page(self) -> None:
        """Go to next page."""
        tweets = self.current_user_tweets
        if not tweets:
            return
        max_page = (len(tweets) - 1) // self.page_size
        if self.current_user_page < max_page:
            self.current_user_page += 1
            self.current_post_index = min(self.current_user_page * self.page_size, len(tweets) - 1)

    def prev_page(self) -> None:
        """Go to previous page."""
        if self.current_user_page > 0:
            self.current_user_page -= 1
            tweets = self.current_user_tweets
            self.current_post_index = max(0, min(self.current_user_page * self.page_size, len(tweets) - 1))

    def update_page_size(self, viewport_height: int) -> None:
        """Update page size based on viewport height."""
        if viewport_height > 0:
            self.page_size = viewport_height
            self._clamp_current_user_page()
            self._clamp_selected_post_index()

    @property
    def total_pages(self) -> int:
        """Get total number of pages."""
        return self.current_user_total_pages

    def _clamp_current_page(self) -> None:
        """确保 current_page 在有效范围内."""
        self._clamp_current_user_page()
        self._clamp_selected_post_index()

    def ensure_visible(self, viewport_height: int) -> None:
        """Ensure selected item is visible in viewport."""
        self.update_page_size(viewport_height)
        tweets = self.current_user_tweets
        if tweets and self.page_size > 0:
            self.current_user_page = self.current_post_index // self.page_size
            self._clamp_current_user_page()
            self._clamp_selected_post_index()

    def reset_new_count(self) -> None:
        """Reset the new tweets counter."""
        self.new_tweets_count = 0

    def mark_selected_as_read(self) -> None:
        """将当前选中的推文标记为已读。"""
        tweet = self.selected_tweet
        if tweet and tweet.is_new:
            tweet.is_new = False
            self.recalculate_new_count()

    def mark_all_as_read(self) -> None:
        """将所有推文标记为已读。"""
        for tweet in self.tweets:
            tweet.is_new = False
        self.new_tweets_count = 0

    def clear(self) -> None:
        """Clear all tweets."""
        self.tweets.clear()
        self.known_ids.clear()
        self.ui.selected_user_index = 0
        self.ui.per_user_selected_post_index.clear()
        self.ui.per_user_current_page.clear()
        self.ui.per_user_details_scroll_offset.clear()
        self.new_tweets_count = 0
        self.filter_keyword = None
        self.filter_user = None
        self.unfiltered_tweets = None
        self.current_user_details_scroll_offset = 0

    def to_dict(self) -> dict:
        """将 AppState 转换为可序列化的字典."""
        return {
            "tweets": [t.to_dict() for t in self.tweets],
            "known_ids": list(self.known_ids),
            "page_size": self.page_size,
            "paused": self.paused,
            "last_poll": self.last_poll.isoformat() if self.last_poll else None,
            "status_message": self.status_message,
            "new_tweets_count": self.new_tweets_count,
            "selected_user_index": self.ui.selected_user_index,
            "focus_column": self.ui.focus_column,
            "per_user_selected_post_index": self.ui.per_user_selected_post_index,
            "per_user_current_page": self.ui.per_user_current_page,
            "per_user_details_scroll_offset": self.ui.per_user_details_scroll_offset,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppState":
        """从字典创建 AppState 对象."""
        state = cls()
        state.timeline = TimelineState(
            tweets=[Tweet.from_dict(t) for t in data.get("tweets", [])],
            known_ids=set(data.get("known_ids", [])),
            new_tweets_count=data.get("new_tweets_count", 0),
        )
        state.ui = UiState(
            page_size=data.get("page_size", 10),
            paused=data.get("paused", False),
            selected_user_index=data.get("selected_user_index", 0),
            focus_column=data.get("focus_column", "users"),
            per_user_selected_post_index=data.get("per_user_selected_post_index", {}),
            per_user_current_page=data.get("per_user_current_page", {}),
            per_user_details_scroll_offset=data.get("per_user_details_scroll_offset", {}),
        )
        state.feedback = FeedbackState(
            status_message=data.get("status_message", "Initializing..."),
        )

        if data.get("last_poll"):
            from datetime import datetime, timezone
            state.last_poll = datetime.fromisoformat(data["last_poll"])

        state.unfiltered_tweets = None
        state.ensure_user_handles()
        state._clamp_selected_user()
        state._clamp_current_user_page()
        state._clamp_selected_post_index()

        # 清理过期的未读标记
        state._cleanup_old_new_tweets()

        # 重新计算未读计数
        state.recalculate_new_count()

        return state
