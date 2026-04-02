"""Main entry point for x-monitor."""

import argparse
import asyncio
from typing import Callable

from .config import Config
from .logging_utils import configure_logging
from .monitor import HandlePollResult, Monitor
from .state_manager import StateManager
from .types import AppState
from .ui import run_ui
from .startup_tracker import StartupTracker


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
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
    return parser


def _load_initial_state(config: Config, tracker: StartupTracker) -> tuple[AppState, StateManager]:
    """Load persisted state and return both state and state manager."""
    sm_step = tracker.add_step("初始化状态管理器")
    tracker.start(sm_step)
    state_manager = StateManager(max_tweets=config.general.max_saved_tweets)
    tracker.complete(sm_step)

    state_step = tracker.add_step("加载历史状态")
    tracker.start(state_step)

    if not config.general.persist_state:
        state = AppState()
        tracker.complete(state_step, "状态持久化已禁用")
        return state, state_manager

    saved_state = state_manager.load()
    if saved_state:
        state = saved_state
        state.page_size = 10
        state._clamp_current_page()
        tracker.complete(state_step, f"已恢复 {len(state.tweets)} 条推文")
        return state, state_manager

    state = AppState()
    tracker.complete(state_step, "无历史数据")
    return state, state_manager


def _create_monitor(
    config: Config,
    state: AppState,
    state_manager: StateManager,
    tracker: StartupTracker,
) -> Monitor:
    """Create the monitor and update startup tracking."""
    monitor_step = tracker.add_step("创建 Monitor")
    tracker.start(monitor_step)
    monitor = Monitor(config, state, state_manager)
    monitor_msg = (
        f"Nitter: {config.general.nitter_instance} | "
        f"{len(config.users.handles)} 个账号 | 失败阈值: 3 次"
    )
    tracker.complete(monitor_step, monitor_msg)
    return monitor


def _update_terminal_title(monitor: Monitor, tracker: StartupTracker) -> None:
    """Update the terminal title to reflect the current instance."""
    title_step = tracker.add_step("更新终端标题")
    tracker.start(title_step)
    monitor.instance_manager.update_terminal_title(monitor.config.general.nitter_instance)
    tracker.complete(title_step)


async def _run_startup_poll(
    config: Config,
    monitor: Monitor,
    state: AppState,
    tracker: StartupTracker,
) -> None:
    """Run the first poll using the shared monitor flow."""
    poll_step = tracker.add_step("初始轮询")
    tracker.start(poll_step)
    user_steps = {
        handle: tracker.add_step(f"@{handle}", parent=poll_step)
        for handle in config.users.handles
    }

    def startup_progress(result: HandlePollResult) -> None:
        step_id = user_steps[result.handle]
        if result.outcome == "start":
            tracker.update(step_id, result.message)
        elif result.outcome == "success":
            message = result.message
            if result.new_count > 0:
                message = f"{message}, {result.new_count} 条新"
            tracker.complete(step_id, message)
        else:
            tracker.fail(step_id, result.message)

    poll_result = await monitor.poll_once(progress_callback=startup_progress)

    if poll_result.total_new > 0:
        poll_msg = f"共加载 {poll_result.total_new} 条新推文"
    else:
        poll_msg = f"共加载 {len(state.tweets)} 条推文"
    tracker.complete(poll_step, poll_msg)

    if state.new_tweets_count > 0:
        monitor.notifier.notify_batch(0, state.new_tweets_count)


def _create_refresh_callback(monitor: Monitor) -> Callable[[], object]:
    """Create the UI refresh callback backed by the monitor."""

    async def do_refresh():
        return await monitor.refresh()

    return do_refresh


def _save_state_on_exit(config: Config, state_manager: StateManager, monitor: Monitor) -> None:
    """Persist state during shutdown when configured."""
    if not config.general.persist_state or not state_manager:
        return
    print("正在保存状态...", end="", flush=True)
    monitor.save_state()
    print(" 完成")


async def main_async() -> None:
    """Main async entry point."""
    configure_logging()

    parser = build_parser()
    args = parser.parse_args()

    if args.create_config:
        Config().save("config.toml")
        print("Created config.toml")
        return

    tracker = StartupTracker()

    parse_step = tracker.add_step("解析命令行参数")
    tracker.start(parse_step)
    tracker.complete(parse_step)

    config_step = tracker.add_step("加载配置文件")
    tracker.start(config_step)
    config = Config.load(args.config)
    tracker.complete(config_step, f"已加载: {args.config or '默认配置'}")

    state, state_manager = _load_initial_state(config, tracker)
    monitor = _create_monitor(config, state, state_manager, tracker)
    _update_terminal_title(monitor, tracker)
    await _run_startup_poll(config, monitor, state, tracker)

    ui_step = tracker.add_step("启动界面")
    tracker.start(ui_step)
    tracker.complete(ui_step)
    tracker.clear()

    try:
        await run_ui(config, state, _create_refresh_callback(monitor), monitor)
    finally:
        await monitor.stop()
        _save_state_on_exit(config, state_manager, monitor)


def main() -> None:
    """Main entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
