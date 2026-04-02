"""TUI interface for x-monitor using prompt_toolkit."""

import asyncio
from typing import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.layout import Layout

from .config import Config
from .types import AppState
from .ui_keybindings import create_key_bindings
from .ui_layout import create_layout as _build_layout
from .ui_layout import create_style
from .ui_runtime import cancel_background_task, poll_tweets_background, update_ui_background
from .ui_status import get_status_text


def create_layout(state: AppState, config: Config) -> Layout:
    """Create the application layout."""
    return _build_layout(
        state=state,
        config=config,
    )


async def run_ui(config: Config, state: AppState, refresh_callback: Callable, monitor=None) -> None:
    """Run the TUI application."""
    def layout_factory(current_state: AppState, current_config: Config) -> Layout:
        return create_layout(current_state, current_config)

    # Create application
    app = Application(
        layout=layout_factory(state, config),
        key_bindings=create_key_bindings(
            state=state,
            monitor=monitor,
            search_overlay=None,
            layout_factory=layout_factory,
        ),
        style=create_style(),
        full_screen=True,
        mouse_support=False,  # Keyboard only
    )

    # Start background polling
    poll_task = asyncio.create_task(
        poll_tweets_background(state, config, app, refresh_callback)
    )

    # Start UI update task (for relative time)
    ui_update_task = asyncio.create_task(
        update_ui_background(app)
    )

    try:
        # Run application
        await app.run_async()
    finally:
        # Cleanup
        await cancel_background_task(poll_task)
        await cancel_background_task(ui_update_task)
