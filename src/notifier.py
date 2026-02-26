"""Notification system for x-monitor."""

import sys
from typing import Optional

from .config import Config
from .types import Tweet


class Notifier:
    """Handle notifications for new tweets."""

    def __init__(self, config: Config):
        """Initialize the notifier with configuration."""
        self.config = config

    def notify(self, tweet: Tweet) -> None:
        """Send a notification for a new tweet."""
        if not self.config.notification.enable:
            return

        # Terminal bell
        if self.config.notification.sound:
            self._bell()

        # Terminal flash
        if self.config.notification.flash:
            self._flash()

        # Desktop notification (if enabled and available)
        if self.config.notification.desktop:
            self._desktop_notify(tweet)

    def _bell(self) -> None:
        """Ring the terminal bell."""
        sys.stdout.write("\a")
        sys.stdout.flush()

    def _flash(self) -> None:
        """Flash the terminal (visual bell)."""
        # ANSI escape sequence for visual bell
        sys.stdout.write("\033[?5h")
        sys.stdout.flush()
        import time
        time.sleep(0.1)
        sys.stdout.write("\033[?5l")
        sys.stdout.flush()

    def _desktop_notify(self, tweet: Tweet) -> None:
        """Send a desktop notification (requires plyer)."""
        try:
            from plyer import notification
            notification.notify(
                title=f"New tweet from @{tweet.author}",
                message=tweet.preview(100),
                timeout=5,
            )
        except ImportError:
            # plyer not installed, skip desktop notifications
            pass
        except Exception:
            # Notification failed, ignore
            pass
