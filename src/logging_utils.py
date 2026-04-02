"""Logging helpers for x-monitor."""

import logging
import os
from pathlib import Path
import sys


def get_log_file_path() -> Path:
    """Return the default application log file path."""
    cache_dir = Path.home() / ".cache" / "x-monitor"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / "x-monitor.log"
    except OSError:
        return Path.cwd() / "x-monitor.log"


def _create_file_handler() -> logging.Handler:
    """Create a file handler, falling back to the current directory if needed."""
    primary_path = get_log_file_path()
    try:
        return logging.FileHandler(primary_path, encoding="utf-8")
    except OSError:
        fallback_path = Path.cwd() / "x-monitor.log"
        return logging.FileHandler(fallback_path, encoding="utf-8")


def configure_logging() -> None:
    """Configure application logging from environment variables."""
    level_name = os.environ.get("X_MONITOR_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)
    log_to_stderr = os.environ.get("X_MONITOR_LOG_STDERR", "").lower() in {"1", "true", "yes", "on"}

    handlers = [_create_file_handler()]
    if log_to_stderr:
        handlers.append(logging.StreamHandler(sys.stderr))

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=handlers,
        force=True,
    )
