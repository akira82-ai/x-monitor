"""State persistence manager for x-monitor."""

import json
from pathlib import Path
from typing import Optional

from .types import AppState, Tweet


class StateManager:
    """管理应用状态的持久化."""

    def __init__(self, max_tweets: int = 1000):
        """初始化 StateManager.

        Args:
            max_tweets: 最大保存推文数量，默认 1000
        """
        self.max_tweets = max_tweets
        self.state_path = self._get_state_path()

    @staticmethod
    def _get_state_path() -> Path:
        """获取状态文件路径."""
        # 优先使用 XDG 配置目录
        config_dir = Path.home() / ".config" / "x-monitor"
        if config_dir.exists():
            return config_dir / "state.json"

        # 回退到当前目录
        return Path("state.json")

    def load(self) -> Optional[AppState]:
        """从文件加载状态.

        Returns:
            加载的 AppState，如果文件不存在或加载失败则返回 None
        """
        if not self.state_path.exists():
            return None

        try:
            data = json.loads(self.state_path.read_text())
            state = AppState.from_dict(data)

            # 限制推文数量
            if len(state.tweets) > self.max_tweets:
                state.tweets = state.tweets[:self.max_tweets]
                # 重建 known_ids
                state.known_ids = {t.id for t in state.tweets}

            return state
        except (json.JSONDecodeError, KeyError, ValueError):
            # 损坏的状态文件，返回 None
            return None

    def save(self, state: AppState) -> None:
        """保存状态到文件.

        Args:
            state: 要保存的 AppState
        """
        # 限制推文数量
        if len(state.tweets) > self.max_tweets:
            state.tweets = state.tweets[:self.max_tweets]
            # 重建 known_ids
            state.known_ids = {t.id for t in state.tweets}

        try:
            # 确保目录存在
            self.state_path.parent.mkdir(parents=True, exist_ok=True)

            # 序列化并保存
            data = state.to_dict()
            self.state_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except (OSError, IOError):
            # 静默处理保存失败
            pass

    def clear(self) -> None:
        """清除保存的状态."""
        if self.state_path.exists():
            self.state_path.unlink()
