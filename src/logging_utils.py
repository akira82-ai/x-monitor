"""Logging helpers for x-monitor."""

import logging
import os


def configure_logging() -> None:
    """Configure application logging from environment variables."""
    level_name = os.environ.get("X_MONITOR_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
