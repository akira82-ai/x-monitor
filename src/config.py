"""Configuration management for x-monitor."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
from urllib.parse import urlparse
import toml


@dataclass
class GeneralConfig:
    """General configuration settings."""
    poll_interval_sec: int = 300
    nitter_instance: str = "https://nitter.net"
    max_tweets: int = 50
    filter_replies: bool = True  # Filter out reply tweets
    persist_state: bool = True   # 是否持久化状态
    max_saved_tweets: int = 1000  # 最大保存推文数
    incremental_save: bool = True  # 是否使用增量保存
    merge_threshold: int = 50  # 合并增量文件的阈值
    auto_merge_interval_sec: int = 60  # 自动合并增量文件的间隔（秒），0 表示禁用

    def validate(self) -> None:
        """Validate general configuration."""
        if self.poll_interval_sec < 10:
            raise ValueError("poll_interval_sec must be at least 10 seconds")
        if self.auto_merge_interval_sec < 0:
            raise ValueError("auto_merge_interval_sec must be non-negative")

        # Validate nitter_instance URL
        try:
            parsed = urlparse(self.nitter_instance)
            if parsed.scheme not in ('http', 'https'):
                raise ValueError("nitter_instance must use http or https protocol")
            if not parsed.netloc:
                raise ValueError("nitter_instance must be a valid URL")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Invalid nitter_instance URL: {e}")


@dataclass
class UsersConfig:
    """User configuration settings."""
    handles: List[str] = field(default_factory=list)

    def validate(self) -> None:
        """Validate user configuration."""
        if not self.handles:
            raise ValueError("No users specified in configuration")
        for handle in self.handles:
            if handle.startswith("@"):
                raise ValueError(f"User handle '{handle}' should not include @ symbol")


@dataclass
class NotificationConfig:
    """Notification configuration settings."""
    enable: bool = True
    sound: bool = True
    flash: bool = True
    desktop: bool = False
    title_badge: bool = True      # 窗口标题未读数和 Dock 徽章
    burst_threshold: int = 5      # 爆发检测阈值（推文/分钟）
    burst_window_sec: int = 60    # 爆发检测时间窗口（秒）
    burst_sound: bool = True      # 爆发时连续响铃


@dataclass
class UiConfig:
    """UI configuration settings."""
    theme: str = "dark"
    show_timestamps: bool = True
    auto_scroll: bool = True


@dataclass
class Config:
    """Main configuration structure."""
    general: GeneralConfig = field(default_factory=GeneralConfig)
    users: UsersConfig = field(default_factory=UsersConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    ui: UiConfig = field(default_factory=UiConfig)

    @staticmethod
    def get_config_paths() -> List[Path]:
        """Get default configuration file paths."""
        paths = [
            Path("config.toml"),
            Path.home() / ".config" / "x-monitor" / "config.toml",
            Path(".x-monitor.toml"),
        ]
        return paths

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        """Load configuration from a file path."""
        if path:
            config_path = Path(path)
        else:
            for config_path in cls.get_config_paths():
                if config_path.exists():
                    break
            else:
                print("Warning: No configuration file found. Using defaults.")
                print(f"Create a config file at one of these locations:")
                for p in cls.get_config_paths():
                    print(f"  - {p}")
                return cls()

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        data = toml.loads(config_path.read_text())

        config = cls(
            general=GeneralConfig(**data.get("general", {})),
            users=UsersConfig(**data.get("users", {"handles": []})),
            notification=NotificationConfig(**data.get("notification", {})),
            ui=UiConfig(**data.get("ui", {})),
        )

        config.validate()
        return config

    def validate(self) -> None:
        """Validate all configuration sections."""
        self.general.validate()
        self.users.validate()

    def save(self, path: str) -> None:
        """Save configuration to a file."""
        Path(path).write_text(toml.dumps({
            "general": {
                "poll_interval_sec": self.general.poll_interval_sec,
                "nitter_instance": self.general.nitter_instance,
                "max_tweets": self.general.max_tweets,
                "filter_replies": self.general.filter_replies,
                "persist_state": self.general.persist_state,
                "max_saved_tweets": self.general.max_saved_tweets,
                "incremental_save": self.general.incremental_save,
                "merge_threshold": self.general.merge_threshold,
                "auto_merge_interval_sec": self.general.auto_merge_interval_sec,
            },
            "users": {
                "handles": self.users.handles,
            },
            "notification": {
                "enable": self.notification.enable,
                "sound": self.notification.sound,
                "flash": self.notification.flash,
                "desktop": self.notification.desktop,
                "title_badge": self.notification.title_badge,
                "burst_threshold": self.notification.burst_threshold,
                "burst_window_sec": self.notification.burst_window_sec,
                "burst_sound": self.notification.burst_sound,
            },
            "ui": {
                "theme": self.ui.theme,
                "show_timestamps": self.ui.show_timestamps,
                "auto_scroll": self.ui.auto_scroll,
            },
        }))
