"""Main entry point for x-monitor."""

import argparse
import asyncio
from pathlib import Path

from src.config import Config
from src.monitor import Monitor
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

    # Create state and monitor (silently)
    state = AppState()
    monitor = Monitor(config, state)

    # Create refresh callback
    async def do_refresh() -> None:
        await monitor.poll_once()

    # Initial load
    await do_refresh()

    # Run the UI
    try:
        await run_ui(config, state, do_refresh)
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
