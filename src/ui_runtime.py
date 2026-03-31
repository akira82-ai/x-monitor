"""Background runtime tasks for the prompt-toolkit UI."""

import asyncio
import time
from datetime import datetime, timezone
from typing import Callable

from prompt_toolkit.application import Application

from .config import Config
from .types import AppState


async def poll_tweets_background(
    state: AppState,
    config: Config,
    app: Application,
    refresh_callback: Callable,
) -> None:
    """Poll tweets in the background on the configured interval."""
    last_poll_time = time.time()
    if state.last_poll is None:
        last_poll_time -= config.general.poll_interval_sec

    while True:
        try:
            current_time = time.time()
            time_since_last_poll = current_time - last_poll_time
            time_until_next_poll = config.general.poll_interval_sec - time_since_last_poll

            if time_until_next_poll > 0:
                await asyncio.sleep(time_until_next_poll)

            state.is_loading = True
            app.invalidate()

            try:
                await refresh_callback()
            except Exception as exc:
                state.error_message = str(exc)
                state.error_timestamp = datetime.now(timezone.utc)
            finally:
                state.is_loading = False

            app.invalidate()
            last_poll_time = time.time()

        except asyncio.CancelledError:
            break
        except Exception as exc:
            state.error_message = str(exc)
            state.error_timestamp = datetime.now(timezone.utc)
            state.is_loading = False
            await asyncio.sleep(5)
            last_poll_time = time.time() - config.general.poll_interval_sec


async def update_ui_background(app: Application) -> None:
    """Refresh the UI every second for relative-time rendering."""
    while True:
        try:
            await asyncio.sleep(1)
            app.invalidate()
        except asyncio.CancelledError:
            break


async def cancel_background_task(task: asyncio.Task) -> None:
    """Cancel a background task and swallow the expected cancellation."""
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
