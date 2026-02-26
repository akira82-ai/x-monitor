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
    async def do_refresh() -> None:
        await monitor.poll_once()

    # Initial load with timeout
    print("Loading tweets... (this may take a moment)")
    try:
        await asyncio.wait_for(do_refresh(), timeout=10.0)
        print(f"Loaded {len(state.tweets)} tweets")
    except asyncio.TimeoutError:
        print("Initial load timed out, starting UI anyway...")
    except Exception as e:
        print(f"Error during initial load: {e}")
        print("Starting UI anyway...")

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
