"""Notification system for x-monitor."""

import platform
import subprocess
import sys
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from .config import Config
from .types import Tweet


class BurstDetector:
    """检测爆发模式：在指定时间窗口内收到超过阈值的推文数量。"""

    def __init__(self, threshold: int = 5, window_sec: int = 60):
        self.threshold = threshold
        self.window_sec = window_sec
        self._timestamps: deque = deque()

    def record(self, count: int) -> bool:
        """记录 count 条新推文，返回是否进入爆发模式。"""
        now = datetime.now(timezone.utc)
        for _ in range(count):
            self._timestamps.append(now)

        # 清除窗口外的旧时间戳
        cutoff = now.timestamp() - self.window_sec
        while self._timestamps and self._timestamps[0].timestamp() < cutoff:
            self._timestamps.popleft()

        return len(self._timestamps) > self.threshold

    @property
    def recent_count(self) -> int:
        """当前时间窗口内的推文数量。"""
        return len(self._timestamps)

    def is_bursting(self) -> bool:
        """检查当前是否处于爆发状态。"""
        return len(self._timestamps) > self.threshold


class TitleBadgeManager:
    """管理终端窗口标题和 Dock 徽章（macOS）。"""

    BASE_TITLE = "x-monitor"
    _is_macos = platform.system() == "Darwin"

    def update(self, count: int, is_burst: bool = False) -> None:
        """根据未读数量和爆发状态更新标题和徽章。"""
        if count <= 0:
            self._set_title(self.BASE_TITLE)
            self._clear_badge()
            return

        count_str = str(count)
        if is_burst:
            title = f"[\u26a0\ufe0f{count}] {self.BASE_TITLE}"
        else:
            title = f"[\U0001f514{count}] {self.BASE_TITLE}"

        self._set_title(title)
        self._set_badge(count_str)

    def clear(self) -> None:
        """清除所有通知状态（用户已读时调用）。"""
        self._set_title(self.BASE_TITLE)
        self._clear_badge()

    def _set_title(self, title: str) -> None:
        """使用 ANSI 转义序列设置终端标题。"""
        sys.stdout.write(f"\033]0;{title}\007")
        sys.stdout.flush()

    def _set_badge(self, text: str) -> None:
        """设置 Dock 徽章（仅 macOS）。"""
        if not self._is_macos:
            return
        try:
            script = f'tell application "Terminal" to set badge label of front window to "{text}"'
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=1.0,
            )
        except Exception:
            pass

    def _clear_badge(self) -> None:
        """清除 Dock 徽章。"""
        if not self._is_macos:
            return
        try:
            script = 'tell application "Terminal" to set badge label of front window to ""'
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=1.0,
            )
        except Exception:
            pass


class Notifier:
    """Handle notifications for new tweets."""

    def __init__(self, config: Config):
        """Initialize the notifier with configuration."""
        self.config = config
        self._burst_detector = BurstDetector(
            threshold=config.notification.burst_threshold,
            window_sec=config.notification.burst_window_sec,
        )
        self._title_badge = TitleBadgeManager()

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

    def notify_batch(self, new_count: int, total_unread: int) -> None:
        """批量通知接口：处理标题、徽章和爆发检测。

        Args:
            new_count: 本轮轮询到的新推文数
            total_unread: 内存中所有未读推文数
        """
        if not self.config.notification.enable:
            return

        # 爆发检测和声音/视觉通知（仅在真正有新消息时）
        if new_count > 0:
            is_burst = self._burst_detector.record(new_count)

            # 爆发模式：多次响铃
            if self.config.notification.sound:
                if is_burst and self.config.notification.burst_sound:
                    self._bell_burst()
                else:
                    self._bell()

            # 视觉闪烁
            if self.config.notification.flash:
                self._flash()

        # 更新标题和徽章（无论是否有新消息，都要反映当前未读状态）
        if self.config.notification.title_badge:
            is_burst = self._burst_detector.is_bursting() if new_count > 0 else False
            self._title_badge.update(total_unread, is_burst)

    def clear_badge(self) -> None:
        """用户已读时清除徽章（由 UI 层调用）。"""
        self._title_badge.clear()

    def _bell(self) -> None:
        """Ring the terminal bell."""
        sys.stdout.write("\a")
        sys.stdout.flush()

    def _bell_burst(self) -> None:
        """连续三声响铃（爆发模式）。"""
        sys.stdout.write("\a\a\a")
        sys.stdout.flush()

    def _flash(self) -> None:
        """Flash the terminal (visual bell)."""
        # 非阻塞版本：连续发送转义序列
        sys.stdout.write("\033[?5h\033[?5l")
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
