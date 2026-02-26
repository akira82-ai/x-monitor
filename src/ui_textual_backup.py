"""TUI interface for x-monitor using Textual."""

from datetime import datetime
from typing import AsyncIterator, Callable

from textual.app import App, ComposeResult
from textual.widgets import (
    Header,
    Footer,
    DataTable,
    Static,
    Button,
    Markdown,
)
from textual.containers import Horizontal, Vertical, Container
from textual.reactive import reactive
from textual import events
from textual.binding import Binding
from textual.timer import Timer

from .config import Config
from .types import AppState, Tweet


class TweetList(DataTable):
    """Widget displaying a list of tweets."""

    def __init__(self, state: AppState, **kwargs):
        super().__init__(**kwargs)
        self.state = state
        self.cursor_type = "row"
        self.zebra_stripes = True

    def on_mount(self) -> None:
        """Set up columns when widget is mounted."""
        self.add_column("User", width=15)
        self.add_column("Content", width=None)  # Auto width
        self.add_column("Time", width=8)
        self.show_cursor = True

    def update_tweets(self) -> None:
        """Update the displayed tweets."""
        self.clear()

        for tweet in self.state.tweets:
            # Add icon for retweets
            prefix = "🔁 " if tweet.is_retweet else ""
            # Adjust preview length based on terminal width
            self.add_row(
                f"@{tweet.author}",
                f"{prefix}{tweet.preview(100)}",
                tweet.format_timestamp(),
            )


class TweetDetails(Markdown):
    """Widget displaying details of selected tweet."""

    def __init__(self, state: AppState, **kwargs):
        super().__init__("", **kwargs)
        self.state = state

    def update_details(self) -> None:
        """Update the details panel."""
        tweet = self.state.selected_tweet
        if not tweet:
            self.update("*No tweet selected*")
            return

        # Format tweet details
        retweet_badge = "🔁 RETWEET" if tweet.is_retweet else ""
        reply_badge = "💬 REPLY" if tweet.is_reply else ""
        badges = " ".join(filter(None, [retweet_badge, reply_badge]))

        content = f"""# @{tweet.author}

{badges}

**Posted:** {tweet.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

---

{tweet.content}

---

**URL:** {tweet.url}
"""
        self.update(content)


class StatusPanel(Static):
    """Widget displaying status information."""

    def __init__(self, state: AppState, **kwargs):
        super().__init__("", **kwargs)
        self.state = state

    def update_status(self) -> None:
        """Update the status display."""
        # Status icon and text
        if self.state.paused:
            status = "⏸  PAUSED"
        else:
            status = "▶  RUNNING"

        # New tweets indicator
        new_count = ""
        if self.state.new_tweets_count > 0:
            new_count = f" • 🔔 {self.state.new_tweets_count} new"

        # Tweet count
        total = f" • 📊 {len(self.state.tweets)} tweets"

        # Last update time
        last_update = ""
        if self.state.last_poll:
            last_update = f" • 🕐 {self.state.last_poll.strftime('%H:%M:%S')}"

        self.update(f"{status}{new_count}{total}{last_update}")


class KeyBindingsBar(Static):
    """Widget displaying keyboard shortcuts at the bottom."""

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)

    def on_mount(self) -> None:
        """Set up the keybindings display."""
        bindings = [
            ("Q", "Quit"),
            ("R", "Refresh"),
            ("Space", "Pause"),
            ("D", "Details"),
            ("↑↓/JK", "Navigate"),
            ("g/G", "Top/Bottom"),
        ]

        binding_text = "  ".join([f"[{key}] {action}" for key, action in bindings])
        self.update(binding_text)


class XMonitorApp(App):
    """Main application class."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #header {
        height: 1;
        width: 100%;
        border-bottom: solid $accent;
        padding: 0 2;
        content-align: left middle;
        text-style: bold;
        background: $surface;
    }

    #status {
        height: 1;
        width: 100%;
        border-bottom: solid $primary-lighten-1;
        padding: 0 2;
        content-align: left middle;
        background: $surface;
    }

    #main {
        height: 1fr;
        width: 100%;
        border: none;
    }

    TweetList {
        height: 100%;
        width: 100%;
        border: none;
        padding: 0 1;
    }

    TweetDetails {
        height: 100%;
        width: 40%;
        border-left: solid $accent;
        padding: 1 2;
        overflow-y: auto;
    }

    #keybindings {
        height: 1;
        width: 100%;
        border-top: solid $accent;
        padding: 0 2;
        content-align: center middle;
        background: $surface;
    }

    .hidden {
        display: none;
    }

    /* DataTable styling */
    DataTable {
        height: 100%;
    }

    DataTable > .datatable--header {
        text-style: bold;
        background: transparent;
        border-bottom: solid $primary;
    }

    DataTable > .datatable--cursor {
        background: $primary 20%;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("space", "toggle_pause", "Pause/Resume", show=False),
        Binding("d", "toggle_details", "Toggle Details", show=False),
        Binding("down,j", "select_next", "Next", show=False),
        Binding("up,k", "select_previous", "Previous", show=False),
        Binding("g", "select_first", "First", show=False),
        Binding("G", "select_last", "Last", show=False),
    ]

    def __init__(self, config: Config, state: AppState, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.state = state
        self.show_details = False
        self.poll_timer: Timer | None = None
        self.refresh_callback: Callable[[], None] | None = None

    def compose(self) -> ComposeResult:
        """Compose the UI."""
        # Use Container to ensure proper layout
        yield Static("x-monitor - Twitter User Monitoring", id="header")
        yield StatusPanel(self.state, id="status")

        with Horizontal(id="main"):
            yield TweetList(self.state, id="tweets")

            with Vertical(id="details", classes="hidden"):
                yield TweetDetails(self.state, id="tweet_details")

        yield KeyBindingsBar(id="keybindings")

    def on_mount(self) -> None:
        """Set up the app after mounting."""
        self._update_details_visibility()
        self._update_ui()
        self._start_polling()

    def _update_details_visibility(self) -> None:
        """Update the visibility of the details panel."""
        try:
            details = self.query_one("#details", Vertical)
            if self.show_details:
                details.remove_class("hidden")
            else:
                details.add_class("hidden")
        except Exception as e:
            pass

    def _update_ui(self) -> None:
        """Update all UI elements."""
        try:
            self.query_one(TweetList).update_tweets()
            self.query_one(TweetDetails).update_details()
            self.query_one(StatusPanel).update_status()
        except Exception:
            pass

    def _start_polling(self) -> None:
        """Start the polling timer."""
        if self.poll_timer:
            self.poll_timer.stop()

        interval = self.config.general.poll_interval_sec

        async def poll() -> None:
            if self.refresh_callback:
                await self.refresh_callback()
            self._update_ui()

        self.set_interval(interval, poll)

    def set_refresh_callback(self, callback: Callable[[], None]) -> None:
        """Set the callback for refreshing data."""
        self.refresh_callback = callback

    def action_toggle_pause(self) -> None:
        """Toggle pause state."""
        self.state.paused = not self.state.paused
        self._update_ui()

    def action_toggle_details(self) -> None:
        """Toggle details panel visibility."""
        self.show_details = not self.show_details
        self._update_details_visibility()

    def action_select_next(self) -> None:
        """Select the next tweet."""
        self.state.select_next()
        self._update_ui()

    def action_select_previous(self) -> None:
        """Select the previous tweet."""
        self.state.select_previous()
        self._update_ui()

    def action_select_first(self) -> None:
        """Select the first tweet."""
        self.state.select_first()
        self._update_ui()

    def action_select_last(self) -> None:
        """Select the last tweet."""
        self.state.select_last()
        self._update_ui()

    async def action_refresh(self) -> None:
        """Trigger a manual refresh."""
        if self.refresh_callback:
            await self.refresh_callback()
        self._update_ui()


async def run_ui(config: Config, state: AppState, refresh_callback: Callable[[], None]) -> None:
    """Run the TUI application."""
    app = XMonitorApp(config, state)
    app.set_refresh_callback(refresh_callback)
    await app.run_async()
