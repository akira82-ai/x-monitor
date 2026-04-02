"""Prompt-toolkit UI controls for the three-column TUI."""

from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout.controls import UIContent, UIControl
from prompt_toolkit.layout.screen import Point
from prompt_toolkit.utils import get_cwidth as _pt_cwidth

from .time_utils import format_local_datetime
from .types import AppState
from .ui_columns import COLUMN_PADDING, pad_column_text


def _w(text: str) -> int:
    """Display width matching prompt_toolkit's internal rendering."""
    return _pt_cwidth(text)


class UserListControl(UIControl):
    """Display monitored users and unread counts."""

    def __init__(self, state: AppState):
        self.state = state

    def create_content(self, width: int, height: int) -> UIContent:
        lines = []
        users = self.state.sorted_users

        add_style = "class:selected" if self.state.ui.add_user_selected and self.state.ui.focus_column == "users" else ""
        lines.append(FormattedText([(add_style, pad_column_text("+ Add user", width))]))

        for index, handle in enumerate(users[: max(0, height - 1)]):
            unread = self.state.unread_count_for_user(handle)
            label = f"@{handle}({unread})" if unread > 0 else f"@{handle}"
            is_selected = index == self.state.ui.selected_user_index
            style = "class:selected" if is_selected and self.state.ui.focus_column == "users" else ""
            lines.append(FormattedText([(style, pad_column_text(label, width))]))

        while len(lines) < height:
            lines.append(FormattedText([("", "")]))

        return UIContent(
            get_line=lambda i: lines[i] if 0 <= i < len(lines) else FormattedText([("", "")]),
            line_count=len(lines),
            cursor_position=Point(
                0,
                0
                if self.state.ui.add_user_selected or not users
                else min(self.state.ui.selected_user_index + 1, max(0, len(lines) - 1)),
            ),
        )

    def is_focusable(self) -> bool:
        return True


class TweetTableControl(UIControl):
    """Display posts for the currently selected user."""

    def __init__(self, state: AppState):
        self.state = state

    def create_content(self, width: int, height: int) -> UIContent:
        lines = []
        self.state.update_page_size(height)

        tweets = self.state.current_user_tweets
        date_width = 5
        fixed_width = date_width + 1 + (COLUMN_PADDING * 2)
        preview_width = max(width - fixed_width, 10)

        start_idx = self.state.current_user_page * self.state.page_size
        end_idx = min(start_idx + self.state.page_size, len(tweets))
        visible_tweets = tweets[start_idx:end_idx]

        for i, tweet in enumerate(visible_tweets):
            absolute_index = start_idx + i
            preview = tweet.preview(preview_width)
            preview_padding = max(0, preview_width - _w(preview))
            date_text = tweet.format_timestamp()
            row_text = (
                f"{' ' * COLUMN_PADDING}"
                f"{preview}{' ' * preview_padding} {date_text}"
                f"{' ' * COLUMN_PADDING}"
            )
            is_selected = absolute_index == self.state.current_post_index
            style = "class:selected" if is_selected and self.state.ui.focus_column == "posts" else ""
            lines.append(FormattedText([(style, row_text)]))

        if not visible_tweets:
            lines.append(FormattedText([("", pad_column_text("没有帖子", width))]))

        while len(lines) < height:
            lines.append(FormattedText([("", "")]))

        return UIContent(
            get_line=lambda i: lines[i] if 0 <= i < len(lines) else FormattedText([("", "")]),
            line_count=len(lines),
            cursor_position=Point(0, max(0, self.state.current_post_index - start_idx)),
        )

    def is_focusable(self) -> bool:
        return True


class TweetDetailsControl(UIControl):
    """Display the selected tweet details."""

    def __init__(self, state: AppState):
        self.state = state

    def create_content(self, width: int, height: int) -> UIContent:
        lines = []
        tweet = self.state.selected_tweet

        if not tweet:
            lines.append(FormattedText([("", pad_column_text("没有选中的推文", width))]))
        else:
            detail_width = max(10, width - (COLUMN_PADDING * 2))
            left_pad = " " * COLUMN_PADDING
            lines.append(FormattedText([("class:details.title", f"{left_pad}@{tweet.author}")]))
            lines.append(FormattedText([("", "")]))

            badges = []
            if tweet.is_retweet:
                badges.append("🔁 转推")
            if tweet.is_reply:
                badges.append("💬 回复")
            if badges:
                lines.append(FormattedText([("class:details.label", f"{left_pad}{' '.join(badges)}")]))
                lines.append(FormattedText([("", "")]))

            lines.append(
                FormattedText(
                    [
                        ("class:details.label", f"{left_pad}发布时间: "),
                        ("", format_local_datetime(tweet.timestamp)),
                    ]
                )
            )
            lines.append(
                FormattedText(
                    [
                        ("class:details.label", f"{left_pad}URL: "),
                        ("class:details.label", f"https://x.com/{tweet.author}/status/{tweet.id}"),
                    ]
                )
            )
            lines.append(FormattedText([("", "")]))
            lines.append(FormattedText([("class:details.label", f"{left_pad}---")]))
            lines.append(FormattedText([("", "")]))

            content_lines = []
            words = tweet.content.split()
            current_line = ""
            current_width = 0
            max_width = detail_width

            for word in words:
                word_width = _w(word)
                space_width = 1 if current_line else 0
                if current_width + space_width + word_width <= max_width:
                    current_line += (" " if current_line else "") + word
                    current_width += space_width + word_width
                else:
                    if current_line:
                        content_lines.append(current_line)
                    if word_width <= max_width:
                        current_line = word
                        current_width = word_width
                    else:
                        chunk_chars = []
                        chunk_width = 0
                        for ch in word:
                            char_width = _w(ch)
                            if chunk_width + char_width > max_width and chunk_chars:
                                content_lines.append("".join(chunk_chars))
                                chunk_chars = [ch]
                                chunk_width = char_width
                            else:
                                chunk_chars.append(ch)
                                chunk_width += char_width
                        if chunk_chars:
                            content_lines.append("".join(chunk_chars))
                        current_line = ""
                        current_width = 0
            if current_line:
                content_lines.append(current_line)

            for line in content_lines:
                lines.append(FormattedText([("", f"{left_pad}{line}")]))

        offset = self.state.current_user_details_scroll_offset
        if offset > 0:
            lines = lines[offset:]

        while len(lines) < height:
            lines.append(FormattedText([("", "")]))

        return UIContent(
            get_line=lambda i: lines[i] if 0 <= i < len(lines) else FormattedText([("", "")]),
            line_count=len(lines),
        )

    def is_focusable(self) -> bool:
        return False
