"""State persistence manager for x-monitor."""

import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

from .types import AppState, Tweet


def atomic_write(path: Path, content: str) -> None:
    """原子性写入文件.

    先写入临时文件，然后原子性重命名，确保写入过程不会损坏原文件。

    Args:
        path: 目标文件路径
        content: 要写入的内容
    """
    # 确保目录存在
    path.parent.mkdir(parents=True, exist_ok=True)

    # 创建临时文件
    fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        # 写入内容
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        # 原子性重命名（覆盖原文件）
        os.replace(temp_path, str(path))
    except Exception:
        # 失败时清理临时文件
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


class StateManager:
    """管理应用状态的持久化."""

    # 推文 ID 过期时间（天），超过此时间的推文 ID 会从 known_ids 中移除
    KNOWN_IDS_EXPIRY_DAYS = 7

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
        # 限制推文数量（只裁剪 tweets 列表，不影响 known_ids）
        if len(state.tweets) > self.max_tweets:
            removed_new_count = sum(1 for t in state.tweets[self.max_tweets:] if t.is_new)
            state.tweets = state.tweets[:self.max_tweets]
            # 不再重建 known_ids，保留已裁剪推文的 ID
            # 这样可以避免这些推文在后续轮询中被重复添加
            # 调整计数器，确保与实际 is_new 标志一致
            state.new_tweets_count = max(0, state.new_tweets_count - removed_new_count)

        # 清理过期的 known_ids：只保留当前 tweets 列表中的 ID
        # 这样被裁剪的推文可以重新出现，避免永久丢失
        self._cleanup_known_ids(state)

        try:
            # 序列化并保存（使用原子写入）
            data = state.to_dict()
            atomic_write(self.state_path, json.dumps(data, indent=2, ensure_ascii=False))
        except (OSError, IOError):
            # 静默处理保存失败
            pass

    def clear(self) -> None:
        """清除保存的状态."""
        if self.state_path.exists():
            self.state_path.unlink()

    def _get_expiry_threshold(self) -> datetime:
        """计算过期时间阈值.

        Returns:
            当前时间减去 KNOWN_IDS_EXPIRY 天后的时间戳
        """
        return datetime.now(timezone.utc) - timedelta(days=self.KNOWN_IDS_EXPIRY_DAYS)

    def _cleanup_known_ids(self, state: AppState) -> None:
        """清理过期的 known_ids.

        只保留当前 tweets 列表中的推文 ID。
        这样被裁剪的推文可以重新出现，避免永久丢失。

        Args:
            state: 当前的 AppState
        """
        if not state.tweets:
            # 如果没有推文，清空所有 known_ids
            state.known_ids.clear()
            return

        # 计算过期时间（7天前）
        expiry_threshold = self._get_expiry_threshold()

        # 获取当前推文列表中的所有 ID
        current_tweet_ids = {tweet.id for tweet in state.tweets}

        # 保留当前推文列表中的 ID
        # 这样被裁剪的推文可以重新出现，避免永久丢失
        state.known_ids = state.known_ids & current_tweet_ids

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

            # 写回增量文件（使用原子写入）
            data = {
                "tweets": all_tweets,
                "last_update": datetime.now(timezone.utc).isoformat()
            }
            atomic_write(
                self.incremental_path,
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

            # 用当前内存状态的 is_new 值覆盖，确保阅读状态正确持久化
            if state:
                for tweet in state.tweets:
                    if tweet.id in main_tweets:
                        main_tweets[tweet.id]["is_new"] = tweet.is_new

                # 清理过期的 known_ids（在合并前）
                self._cleanup_known_ids(state)

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

            # 更新主文件（使用原子写入）
            atomic_write(
                self.state_path,
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
                        # 直接添加，不使用 add_tweet（避免覆盖 is_new）
                        state.known_ids.add(tweet.id)
                        state.tweets.insert(0, tweet)
                        if tweet.is_new:
                            state.new_tweets_count += 1

                # 清空已应用的增量文件
                self.incremental_path.unlink()
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

        # 限制推文数量（只裁剪 tweets 列表，不影响 known_ids）
        if len(state.tweets) > self.max_tweets:
            removed_new_count = sum(1 for t in state.tweets[self.max_tweets:] if t.is_new)
            state.tweets = state.tweets[:self.max_tweets]
            # 不再重建 known_ids，保留已裁剪推文的 ID
            # 这样可以避免这些推文在后续轮询中被重复添加
            # 调整计数器，确保与实际 is_new 标志一致
            state.new_tweets_count = max(0, state.new_tweets_count - removed_new_count)

        # 清理老推文的未读标记（超过 7 天的推文不应该标记为未读）
        self._cleanup_old_new_tweets(state)

        # 重新计算以确保 new_tweets_count 与实际 is_new 标志一致
        state.new_tweets_count = sum(1 for t in state.tweets if t.is_new)

        return state

    def _cleanup_old_new_tweets(self, state: AppState) -> None:
        """清理老推文的未读标记.

        将超过 7 天的推文的 is_new 标记设置为 False。

        Args:
            state: 当前的 AppState
        """
        if not state.tweets:
            return

        # 计算过期时间（7天前）
        expiry_threshold = self._get_expiry_threshold()

        # 清理老推文的未读标记
        for tweet in state.tweets:
            if tweet.is_new and tweet.timestamp < expiry_threshold:
                tweet.is_new = False
