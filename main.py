"""Main entry point for x-monitor."""

import argparse
import asyncio
import atexit
from pathlib import Path

import httpx

from src.config import Config
from src.monitor import Monitor
from src.state_manager import StateManager
from src.types import AppState
from src.ui import run_ui
from src.startup_tracker import StartupTracker


async def main_async() -> None:
    """Main async entry point."""
    # 首先处理 --create-config，不使用追踪器
    parser = argparse.ArgumentParser(
        description="x-monitor - X (Twitter) User Monitoring Dashboard"
    )
    parser.add_argument(
        "config",
        nargs="?",
        help="Path to configuration file",
    )
    parser.add_argument(
        "--create-config",
        action="store_true",
        help="Create a sample config.toml and exit",
    )
    args = parser.parse_args()

    if args.create_config:
        Config().save("config.toml")
        print("Created config.toml")
        return

    # 开始启动追踪
    tracker = StartupTracker()

    # 步骤 1: 解析命令行参数
    parse_step = tracker.add_step("解析命令行参数")
    tracker.start(parse_step)
    tracker.complete(parse_step)

    # 步骤 2: 加载配置文件
    config_step = tracker.add_step("加载配置文件")
    tracker.start(config_step)
    config = Config.load(args.config)
    tracker.complete(config_step, f"已加载: {args.config or '默认配置'}")

    # 步骤 3: 初始化状态管理器
    sm_step = tracker.add_step("初始化状态管理器")
    tracker.start(sm_step)
    state_manager = StateManager(
        max_tweets=config.general.max_saved_tweets,
        merge_threshold=config.general.merge_threshold
    )
    tracker.complete(sm_step)

    # 步骤 4: 加载历史状态
    state_step = tracker.add_step("加载历史状态")
    tracker.start(state_step)
    if config.general.persist_state:
        saved_state = state_manager.load()
        if saved_state:
            state = saved_state
            # Reset page_size to allow UI to recalculate it based on actual window size
            # This prevents cursor_position from going negative due to page size mismatch
            state.page_size = 10
            state._clamp_current_page()
            tracker.complete(state_step, f"已恢复 {len(state.tweets)} 条推文")
        else:
            state = AppState()
            tracker.complete(state_step, "无历史数据")
    else:
        state = AppState()
        tracker.complete(state_step, "状态持久化已禁用")

    # 注册退出时保存状态
    if config.general.persist_state:
        def save_on_exit():
            if config.general.incremental_save:
                # 增量模式：退出时合并
                monitor.cleanup_and_save()
            else:
                # 全量模式
                state_manager.save(state)
        atexit.register(save_on_exit)

    # 步骤 5: 创建 Monitor
    monitor_step = tracker.add_step("创建 Monitor")
    tracker.start(monitor_step)
    monitor = Monitor(config, state, state_manager)
    monitor_msg = f"Nitter: {config.general.nitter_instance} | {len(config.users.handles)} 个账号 | 失败阈值: 3 次"
    tracker.complete(monitor_step, monitor_msg)

    # 步骤 6: 更新终端标题
    title_step = tracker.add_step("更新终端标题")
    tracker.start(title_step)
    monitor.instance_manager.update_terminal_title(config.general.nitter_instance)
    tracker.complete(title_step)

    # 创建刷新回调
    async def do_refresh() -> int:
        """Refresh tweets and return count of new tweets."""
        return await monitor.poll_once()

    # 步骤 7: 初始轮询
    poll_step = tracker.add_step("初始轮询")
    tracker.start(poll_step)

    total_new = 0
    for i, handle in enumerate(config.users.handles):
        # 为每个账号创建子步骤
        user_step = tracker.add_step(f"@{handle}", parent=poll_step)
        tracker.update(user_step, "获取中...")

        try:
            tweets = await monitor.fetcher.fetch_tweets(handle)

            await monitor.instance_manager.record_success()

            if config.general.filter_replies:
                tweets = [t for t in tweets if not t.is_reply]

            new_count = 0
            for tweet in tweets:
                if state.add_tweet(tweet):
                    total_new += 1

            if tweets:
                msg = f"{len(tweets)} 条推文"
                if new_count > 0:
                    msg += f", {new_count} 条新"
                tracker.complete(user_step, msg)
            else:
                tracker.complete(user_step, "无推文")

        except Exception as e:
            tracker.fail(user_step, str(e))
            # 尝试切换实例
            try:
                new_instance = await monitor.instance_manager.record_failure(e)
                if new_instance:
                    await monitor.fetcher.update_instance(new_instance)
                    state.current_instance = new_instance
                    monitor.instance_manager.update_terminal_title(new_instance)
            except Exception:
                pass

    # Trim to max tweets
    max_tweets = config.general.max_tweets
    if len(state.tweets) > max_tweets:
        selected_id = state.selected_tweet.id if state.selected_tweet else None
        state.tweets = state.tweets[:max_tweets]
        state.recalculate_new_count()
        if selected_id:
            for i, tweet in enumerate(state.tweets):
                if tweet.id == selected_id:
                    state.selected_index = i
                    break
            else:
                state.selected_index = 0

    # Sort tweets by timestamp (newest first)
    selected_id = state.selected_tweet.id if state.selected_tweet else None
    state.tweets.sort(key=lambda t: t.timestamp, reverse=True)
    if selected_id:
        for i, tweet in enumerate(state.tweets):
            if tweet.id == selected_id:
                state.selected_index = i
                break
        else:
            state.selected_index = 0

    # 更新状态
    from datetime import datetime, timezone
    state.last_poll = datetime.now(timezone.utc)
    state.status_message = (
        f"Last update: {state.last_poll.strftime('%H:%M:%S')} | "
        f"{len(state.tweets)} tweets"
    )

    # 轮询后自动保存
    if state_manager and config.general.persist_state:
        new_tweets_list = [t for t in state.tweets if t.is_new][:total_new]
        async with monitor._merge_lock:
            if config.general.incremental_save:
                state_manager.save_incremental(state, new_tweets_list)
            else:
                state_manager.save(state)

    if total_new > 0:
        poll_msg = f"共加载 {total_new} 条新推文"
    else:
        poll_msg = f"共加载 {len(state.tweets)} 条推文"
    tracker.complete(poll_step, poll_msg)

    # 步骤 8: 更新通知状态
    if state.new_tweets_count > 0:
        monitor.notifier.notify_batch(0, state.new_tweets_count)

    # 步骤 9: 启动 UI
    ui_step = tracker.add_step("启动界面")
    tracker.start(ui_step)
    tracker.complete(ui_step)

    # 清除启动信息，直接进入 UI
    tracker.clear()

    # Run the UI
    try:
        await run_ui(config, state, do_refresh, monitor)
    finally:
        await monitor.stop()


def main() -> None:
    """Main entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass  # Silent exit


if __name__ == "__main__":
    main()
