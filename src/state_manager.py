"""State persistence manager for x-monitor."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .types import AppState, Tweet


class StateManager:
    """管理应用状态的持久化."""

    def __init__(self, max_tweets: int = 1000, merge_threshold: int = 50):
        """初始化 StateManager.

        Args:
            max_tweets: 最大保存推文数量，默认 1000
            merge_threshold: 增量文件达到此数量时合并，默认 50
        """
        self.max_tweets = max_tweets
        self.merge_threshold = merge_threshold
        self.state_path = self._get_state_path()
        self.incremental_path = self._get_incremental_path()

    @staticmethod
    def _get_state_path() -> Path:
        """获取状态文件路径."""
        # 优先使用 XDG 配置目录
        config_dir = Path.home() / ".config" / "x-monitor"
        if config_dir.exists():
            return config_dir / "state.json"

        # 回退到当前目录
        return Path("state.json")

    @staticmethod
    def _get_incremental_path() -> Path:
        """获取增量文件路径."""
        config_dir = Path.home() / ".config" / "x-monitor"
        if config_dir.exists():
            return config_dir / "state.incremental.json"
        return Path("state.incremental.json")

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

    def save_incremental(self, state: AppState, new_tweets: List[Tweet]) -> None:
        """增量保存：只保存新增的推文.

        Args:
            state: 当前的 AppState
            new_tweets: 新增的推文列表
        """
        if not new_tweets:
            return

        try:
            # 读取现有增量文件
            existing = []
            if self.incremental_path.exists():
                existing = json.loads(self.incremental_path.read_text()).get("tweets", [])

            # 追加新推文
            all_tweets = existing + [t.to_dict() for t in new_tweets]

            # 写回增量文件
            self.incremental_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "tweets": all_tweets,
                "last_update": datetime.now(timezone.utc).isoformat()
            }
            self.incremental_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False)
            )

            # 检查是否需要合并
            if len(all_tweets) >= self.merge_threshold:
                self._merge_incremental(state)

        except (OSError, IOError):
            pass

    def _merge_incremental(self, state: AppState) -> None:
        """合并增量文件到主文件.

        Args:
            state: 当前的 AppState
        """
        try:
            # 加载主文件
            main_data = {}
            if self.state_path.exists():
                main_data = json.loads(self.state_path.read_text())

            # 加载增量文件
            incremental_data = {}
            if self.incremental_path.exists():
                incremental_data = json.loads(self.incremental_path.read_text())

            # 合并推文（去重）
            main_tweets = {t["id"]: t for t in main_data.get("tweets", [])}
            for t in incremental_data.get("tweets", []):
                main_tweets[t["id"]] = t

            # 排序并限制数量
            tweets_list = sorted(
                main_tweets.values(),
                key=lambda x: x["timestamp"],
                reverse=True
            )[:self.max_tweets]

            # 更新主文件
            main_data["tweets"] = tweets_list
            # 保存其他状态字段
            if state:
                main_data["selected_index"] = state.selected_index
                main_data["current_page"] = state.current_page
                main_data["page_size"] = state.page_size
                main_data["paused"] = state.paused
                main_data["last_poll"] = state.last_poll.isoformat() if state.last_poll else None
                main_data["status_message"] = state.status_message
                main_data["new_tweets_count"] = state.new_tweets_count
                main_data["filter_keyword"] = state.filter_keyword
                main_data["filter_user"] = state.filter_user
                main_data["details_scroll_offset"] = state.details_scroll_offset
                main_data["known_ids"] = list(state.known_ids)

            self.state_path.write_text(
                json.dumps(main_data, indent=2, ensure_ascii=False)
            )

            # 清空增量文件
            if self.incremental_path.exists():
                self.incremental_path.unlink()

        except (OSError, IOError, json.JSONDecodeError):
            pass

    def load(self) -> Optional[AppState]:
        """加载状态（主文件 + 增量文件）.

        Returns:
            加载的 AppState，如果文件不存在或加载失败则返回 None
        """
        if not self.state_path.exists() and not self.incremental_path.exists():
            return None

        state = AppState()

        # 加载主文件
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text())
                state = AppState.from_dict(data)
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

        # 应用增量文件
        if self.incremental_path.exists():
            try:
                data = json.loads(self.incremental_path.read_text())
                for t_dict in data.get("tweets", []):
                    tweet = Tweet.from_dict(t_dict)
                    if tweet.id not in state.known_ids:
                        state.add_tweet(tweet)

                # 清空已应用的增量文件
                self.incremental_path.unlink()
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

        # 限制推文数量
        if len(state.tweets) > self.max_tweets:
            state.tweets = state.tweets[:self.max_tweets]
            state.known_ids = {t.id for t in state.tweets}

        return state
