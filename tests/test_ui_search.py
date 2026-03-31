"""Unit tests for the search overlay state machine."""

from types import SimpleNamespace
from unittest.mock import Mock

from prompt_toolkit.keys import Keys

from src.config import Config
from src.types import AppState, Tweet
from src.ui_search import SearchOverlay


def make_tweet(tweet_id: str, content: str) -> Tweet:
    """Create a minimal tweet for search overlay tests."""
    from datetime import datetime, timezone

    return Tweet(
        id=tweet_id,
        author="tester",
        author_name="TESTER",
        content=content,
        timestamp=datetime.now(timezone.utc),
        url=f"https://x.com/tester/status/{tweet_id}",
    )


def invoke_binding(overlay: SearchOverlay, key: Keys, event) -> None:
    """Invoke a registered key binding by key enum."""
    binding = next(
        binding
        for binding in overlay._key_bindings.bindings
        if binding.keys and binding.keys[0] == key
    )
    binding.handler(event)


def make_event():
    """Create a lightweight prompt-toolkit event stub."""
    app = SimpleNamespace(layout=None, invalidate=Mock())
    return SimpleNamespace(app=app)


def test_search_overlay_filter_reflects_visibility():
    """The search mode filter should disable global shortcuts while visible."""
    overlay = SearchOverlay(layout_factory=Mock())
    state = AppState(search_visible=True)

    overlay.attach(state, Config())

    assert overlay.current_config is not None
    assert overlay.not_searching_filter() is False

    state.search_visible = False

    assert overlay.not_searching_filter() is True


def test_search_overlay_enter_applies_keyword_filter_and_rebuilds_layout():
    """Submitting a keyword should filter tweets, hide the overlay, and rebuild layout."""
    layout_factory = Mock(return_value="rebuilt-layout")
    overlay = SearchOverlay(layout_factory=layout_factory)
    state = AppState(tweets=[make_tweet("1", "hello world"), make_tweet("2", "bye now")], search_visible=True)
    config = Config()
    event = make_event()

    overlay.attach(state, config)
    overlay.buffer.text = "hello"

    invoke_binding(overlay, Keys.ControlM, event)

    assert state.search_visible is False
    assert state.filter_keyword == "hello"
    assert [tweet.id for tweet in state.tweets] == ["1"]
    assert state.status_message == "关键词: hello"
    assert event.app.layout == "rebuilt-layout"
    event.app.invalidate.assert_called_once()
    layout_factory.assert_called_once_with(state, config)


def test_search_overlay_enter_with_blank_text_clears_filters():
    """Submitting an empty search should clear existing filters."""
    layout_factory = Mock(return_value="rebuilt-layout")
    overlay = SearchOverlay(layout_factory=layout_factory)
    tweets = [make_tweet("1", "hello world"), make_tweet("2", "bye now")]
    state = AppState(tweets=tweets.copy(), search_visible=True)
    config = Config()
    event = make_event()

    state.apply_keyword_filter("hello")
    overlay.attach(state, config)
    overlay.buffer.text = "   "

    invoke_binding(overlay, Keys.ControlM, event)

    assert state.search_visible is False
    assert state.filter_keyword is None
    assert state.filter_user is None
    assert state.unfiltered_tweets is None
    assert [tweet.id for tweet in state.tweets] == ["1", "2"]
    assert state.status_message == "已清除过滤"
    assert event.app.layout == "rebuilt-layout"
    event.app.invalidate.assert_called_once()


def test_search_overlay_escape_clears_buffer_and_hides_overlay():
    """Escaping search mode should drop the draft query and hide the float."""
    layout_factory = Mock(return_value="rebuilt-layout")
    overlay = SearchOverlay(layout_factory=layout_factory)
    state = AppState(search_visible=True)
    config = Config()
    event = make_event()

    overlay.attach(state, config)
    overlay.buffer.text = "draft query"

    invoke_binding(overlay, Keys.Escape, event)

    assert state.search_visible is False
    assert overlay.buffer.text == ""
    assert event.app.layout == "rebuilt-layout"
    event.app.invalidate.assert_called_once()
