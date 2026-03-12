"""Main entry point for x-monitor."""

import argparse
import asyncio
import atexit
from pathlib import Path

from src.config import Config
from src.monitor import Monitor
from src.state_manager import StateManager
from src.types import AppState
from src.ui import run_ui


async def refresh_monitor(monitor: Monitor) -> int:
    """Callback for UI refresh."""
    return await monitor.refresh()


async def main_async() -> None:
    """Main async entry point."""
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

    # Load configuration
    config = Config.load(args.config)

    # 初始化状态管理器
    state_manager = StateManager(
        max_tweets=config.general.max_saved_tweets,
        merge_threshold=config.general.merge_threshold
    )

    # 尝试加载保存的状态
    if config.general.persist_state:
        saved_state = state_manager.load()
        if saved_state:
            state = saved_state
            print(f"Restored {len(state.tweets)} tweets from previous session")
            # Reset page_size to allow UI to recalculate it based on actual window size
            # This prevents cursor_position from going negative due to page size mismatch
            state.page_size = 10
            state._clamp_current_page()
        else:
            state = AppState()
    else:
        state = AppState()

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

    # Create monitor
    monitor = Monitor(config, state, state_manager)

    # Create refresh callback
    async def do_refresh() -> int:
        """Refresh tweets and return count of new tweets."""
        return await monitor.poll_once()

    # Initial load with progress
    total = len(config.users.handles)

    def on_progress(done, total):
        print(f"\rLoading tweets... {done}/{total}", end="", flush=True)

    print(f"Loading tweets... 0/{total}", end="", flush=True)
    try:
        await asyncio.wait_for(monitor.poll_once(progress_callback=on_progress), timeout=10.0)
        print(f"\nLoaded {len(state.tweets)} tweets")
    except asyncio.TimeoutError:
        print("\nInitial load timed out, starting UI anyway...")
    except Exception as e:
        print(f"\nError during initial load: {e}")
        print("Starting UI anyway...")

    # 初始加载后，如果有未读推文，更新通知状态
    if state.new_tweets_count > 0:
        monitor.notifier.notify_batch(0, state.new_tweets_count)

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
