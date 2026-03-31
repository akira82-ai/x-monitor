"""Prompt-toolkit UI controls for the tweet list and details pane."""

from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout.controls import UIContent, UIControl
from prompt_toolkit.layout.screen import Point
from prompt_toolkit.utils import get_cwidth as _pt_cwidth

from .types import AppState


def _w(text: str) -> int:
    """Display width matching prompt_toolkit's internal rendering."""
    return _pt_cwidth(text)


class TweetTableControl(UIControl):
    """Custom control for displaying tweet table."""

    def __init__(self, state: AppState):
        self.state = state

    def create_content(self, width: int, height: int) -> UIContent:
        """Generate table content for display."""
        lines = []

        self.state.update_page_size(height)
        visible_tweets_all = self.state.tweets

        user_width = 16
        date_width = 9
        separator_width = 3
        fixed_width = user_width + date_width + separator_width + 2
        content_width = max(width - fixed_width, 20)

        total_filtered = len(visible_tweets_all)
        start_idx = self.state.current_page * self.state.page_size
        end_idx = min(start_idx + self.state.page_size, total_filtered)
        visible_tweets = visible_tweets_all[start_idx:end_idx]

        for i, tweet in enumerate(visible_tweets):
            absolute_index = start_idx + i

            prefix = ""
            if tweet.is_new:
                prefix = "🔔 "
            elif tweet.is_retweet:
                prefix = "🔁 "
            prefix_display_width = _w(prefix) if prefix else 0
            available_content_width = content_width - prefix_display_width

            tweet_preview = tweet.preview(available_content_width)
            preview_display_width = _w(tweet_preview)

            content_padding = content_width - prefix_display_width - preview_display_width
            if content_padding < 0:
                content_padding = 0

            user_col = f"@{tweet.author}"
            user_col_width = _w(user_col)
            user_padding = user_width - user_col_width
            if user_padding < 0:
                user_padding = 0

            content_col = f"{prefix}{tweet_preview}{' ' * content_padding}"

            date_col = tweet.format_timestamp()
            date_col_width = _w(date_col)
            date_padding = date_width - date_col_width
            if date_padding < 0:
                date_padding = 0

            separator_col = " │"
            is_selected = absolute_index == self.state.selected_index
            if is_selected:
                row_text = (
                    f"{user_col}{' ' * user_padding} {content_col} "
                    f"{date_col}{' ' * date_padding}{separator_col}"
                )
                lines.append(FormattedText([("class:selected", row_text)]))
            else:
                lines.append(
                    FormattedText(
                        [
                            ("class:author", f"{user_col}{' ' * user_padding}"),
                            ("", f" {content_col} "),
                            ("class:date", f"{date_col}{' ' * date_padding}"),
                            ("class:vseparator", separator_col),
                        ]
                    )
                )

        while len(lines) < height:
            lines.append(FormattedText([("", "")]))

        return UIContent(
            get_line=lambda i: lines[i] if 0 <= i < len(lines) else FormattedText([("", "")]),
            line_count=len(lines),
            cursor_position=Point(0, max(0, self.state.selected_index - start_idx)),
        )

    def is_focusable(self) -> bool:
        """This control can receive focus."""
        return True

    def get_key_bindings(self):
        """No specific key bindings for this control."""
        return None


class TweetDetailsControl(UIControl):
    """Display the selected tweet details."""

    def __init__(self, state: AppState):
        self.state = state

    def create_content(self, width: int, height: int) -> UIContent:
        """Generate details content."""
        lines = []

        tweet = self.state.selected_tweet
        if not tweet:
            lines.append(FormattedText([("", "没有选中的推文")]))
        else:
            lines.append(FormattedText([("class:details.title", f"@{tweet.author}")]))
            lines.append(FormattedText([("", "")]))

            badges = []
            if tweet.is_retweet:
                badges.append("🔁 转推")
            if tweet.is_reply:
                badges.append("💬 回复")
            if badges:
                lines.append(FormattedText([("class:details.label", " ".join(badges))]))
                lines.append(FormattedText([("", "")]))

            local_time = tweet.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(
                FormattedText(
                    [
                        ("class:details.label", "发布时间: "),
                        ("", local_time),
                    ]
                )
            )

            x_url = f"https://x.com/{tweet.author}/status/{tweet.id}"
            lines.append(
                FormattedText(
                    [
                        ("class:details.label", "URL: "),
                        ("class:details.label", x_url),
                    ]
                )
            )
            lines.append(FormattedText([("", "")]))
            lines.append(FormattedText([("class:details.label", "---")]))
            lines.append(FormattedText([("", "")]))

            content_lines = []
            words = tweet.content.split()
            current_line = ""
            current_width = 0
            max_width = width - 2

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
                        chunk_w = 0
                        for ch in word:
                            cw = _w(ch)
                            if chunk_w + cw > max_width and chunk_chars:
                                content_lines.append("".join(chunk_chars))
                                chunk_chars = [ch]
                                chunk_w = cw
                            else:
                                chunk_chars.append(ch)
                                chunk_w += cw
                        if chunk_chars:
                            content_lines.append("".join(chunk_chars))
                        current_line = ""
                        current_width = 0

            if current_line:
                content_lines.append(current_line)

            for line in content_lines:
                lines.append(FormattedText([("", " " + line)]))

        offset = self.state.details_scroll_offset
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
