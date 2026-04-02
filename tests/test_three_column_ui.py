"""Tests for the three-column user-first TUI behavior."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from prompt_toolkit.keys import Keys

from src.config import Config
from src.types import AppState, Tweet
from src.ui_columns import COLUMN_SEPARATOR
from src.ui_controls import TweetDetailsControl, TweetTableControl, UserListControl
from src.ui_keybindings import create_key_bindings
from src.ui_layout import create_layout


def make_tweet(tweet_id: str, author: str, minutes_ago: int = 0, is_new: bool = True) -> Tweet:
    """Create a tweet for UI state tests."""
    tweet = Tweet(
        id=tweet_id,
        author=author,
        author_name=author.upper(),
        content=f"{author} post {tweet_id}",
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        url=f"https://x.com/{author}/status/{tweet_id}",
    )
    tweet.is_new = is_new
    return tweet


def invoke_binding(kb, key, event) -> None:
    """Invoke one binding handler by prompt-toolkit key enum."""
    binding = kb.get_bindings_for_keys((key,))[0]
    binding.handler(event)


def invoke_binding_sequence(kb, keys, event) -> None:
    """Invoke one binding handler by a prompt-toolkit key sequence."""
    binding = kb.get_bindings_for_keys(keys)[0]
    binding.handler(event)


def make_event():
    """Create a lightweight app event stub."""
    app = SimpleNamespace(invalidate=Mock(), exit=Mock())
    return SimpleNamespace(app=app)


def test_users_are_sorted_alphabetically_and_show_unread_counts():
    """Left navigation should show monitored users in stable alphabetical order."""
    state = AppState(tweets=[make_tweet("1", "sama", is_new=False), make_tweet("2", "dotey")])
    state.set_monitored_handles(["sama", "dotey", "openai"])
    control = UserListControl(state)

    content = control.create_content(width=20, height=5)
    rendered = ["".join(fragment[1] for fragment in content.get_line(i)) for i in range(3)]

    assert state.sorted_users == ["dotey", "openai", "sama"]
    assert rendered[0].startswith(" ")
    assert rendered[0].strip() == "@dotey(1)"
    assert rendered[1].startswith(" ")
    assert rendered[1].strip() == "@openai"
    assert rendered[2].startswith(" ")
    assert rendered[2].strip() == "@sama"


def test_each_user_keeps_independent_post_position_and_page():
    """Switching users should preserve each user's browsing context."""
    state = AppState(
        tweets=[
            make_tweet("1", "dotey", minutes_ago=1),
            make_tweet("2", "dotey", minutes_ago=2),
            make_tweet("3", "dotey", minutes_ago=3),
            make_tweet("4", "sama", minutes_ago=1),
            make_tweet("5", "sama", minutes_ago=2),
        ]
    )
    state.set_monitored_handles(["sama", "dotey"])
    state.page_size = 1

    assert state.current_user == "dotey"
    state.current_post_index = 2
    state.current_user_page = 2

    state.select_next_user()
    assert state.current_user == "sama"
    assert state.current_post_index == 0
    state.current_post_index = 1
    state.current_user_page = 1

    state.select_previous_user()
    assert state.current_user == "dotey"
    assert state.current_post_index == 2
    assert state.current_user_page == 2


def test_selecting_post_marks_it_read_and_reduces_unread_count():
    """Middle-column selection should immediately consume unread count."""
    state = AppState(
        tweets=[
            make_tweet("1", "dotey", minutes_ago=1, is_new=True),
            make_tweet("2", "dotey", minutes_ago=2, is_new=True),
        ]
    )
    state.set_monitored_handles(["dotey"])
    state.recalculate_new_count()
    state.ui.focus_column = "posts"

    kb = create_key_bindings(state=state, monitor=None, search_overlay=None, layout_factory=lambda *_: None)
    event = make_event()

    invoke_binding(kb, Keys.Down, event)

    assert state.current_post_index == 1
    assert state.selected_tweet.id == "2"
    assert state.unread_count_for_user("dotey") == 1


def test_tab_cycles_focus_between_users_and_posts_only():
    """Tab should only move between the left and middle columns."""
    state = AppState(
        tweets=[
            make_tweet("1", "dotey", minutes_ago=1),
            make_tweet("2", "dotey", minutes_ago=2),
            make_tweet("3", "dotey", minutes_ago=3),
        ]
    )
    state.set_monitored_handles(["dotey"])
    state.page_size = 1
    kb = create_key_bindings(state=state, monitor=None, search_overlay=None, layout_factory=lambda *_: None)
    event = make_event()

    invoke_binding(kb, Keys.ControlI, event)
    assert state.ui.focus_column == "posts"

    invoke_binding(kb, Keys.Right, event)
    assert state.current_user_page == 1

    invoke_binding(kb, Keys.ControlI, event)
    assert state.ui.focus_column == "users"

    invoke_binding(kb, Keys.Right, event)
    assert state.current_user_page == 1


def test_alt_arrow_scrolls_details_without_detail_focus():
    """Detail scrolling should remain available after removing right-column focus."""
    state = AppState(tweets=[make_tweet("1", "dotey", minutes_ago=1)])
    state.set_monitored_handles(["dotey"])
    state.ui.focus_column = "posts"
    kb = create_key_bindings(state=state, monitor=None, search_overlay=None, layout_factory=lambda *_: None)
    event = make_event()

    invoke_binding_sequence(kb, (Keys.Escape, Keys.Down), event)
    assert state.current_user_details_scroll_offset == 1

    invoke_binding_sequence(kb, (Keys.Escape, Keys.Up), event)
    assert state.current_user_details_scroll_offset == 0


def test_layout_footer_no_longer_mentions_search():
    """Three-column footer should expose the new navigation model without search hints."""
    state = AppState()
    config = Config()
    config.users.handles = ["dotey"]

    layout = create_layout(state, config)
    footer_window = layout.container.children[-1]
    footer_text = footer_window.content.text()

    assert "Tab左中切栏" in footer_text
    assert "/:搜索" not in footer_text


def test_layout_header_uses_explicit_column_separators():
    """The table header should visually separate the three columns."""
    state = AppState()
    config = Config()
    config.users.handles = ["dotey"]

    layout = create_layout(state, config)
    header_window = layout.container.children[1]
    header_text = header_window.content.text()

    assert header_text.count(COLUMN_SEPARATOR) == 2
    assert " Users (A-Z)" in header_text


def test_post_rows_keep_padding_and_right_aligned_date():
    """Post list rows should render with left padding and preserve the date column."""
    state = AppState(tweets=[make_tweet("1", "dotey", minutes_ago=1)])
    state.set_monitored_handles(["dotey"])
    control = TweetTableControl(state)

    content = control.create_content(width=30, height=3)
    rendered = "".join(fragment[1] for fragment in content.get_line(0))

    assert rendered.startswith(" ")
    assert "  " in rendered
    assert state.selected_tweet.format_timestamp() in rendered


def test_details_render_with_left_padding_for_readability():
    """Details should no longer start directly at the column edge."""
    state = AppState(tweets=[make_tweet("1", "dotey", minutes_ago=1)])
    state.set_monitored_handles(["dotey"])
    control = TweetDetailsControl(state)

    content = control.create_content(width=40, height=8)
    first_line = "".join(fragment[1] for fragment in content.get_line(0))
    time_line = "".join(fragment[1] for fragment in content.get_line(2))

    assert first_line.startswith(" @dotey")
    assert time_line.startswith(" 发布时间:")
