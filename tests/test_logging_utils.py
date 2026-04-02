"""Tests for logging configuration behavior."""

import logging

from src import logging_utils


def test_configure_logging_writes_to_file_only_by_default(monkeypatch, tmp_path):
    """Periodic application logs should avoid stderr unless explicitly requested."""
    log_path = tmp_path / "x-monitor.log"

    monkeypatch.delenv("X_MONITOR_LOG_STDERR", raising=False)
    monkeypatch.setenv("X_MONITOR_LOG_LEVEL", "INFO")
    monkeypatch.setattr(logging_utils, "get_log_file_path", lambda: log_path)

    logging_utils.configure_logging()

    root_logger = logging.getLogger()
    assert any(isinstance(handler, logging.FileHandler) for handler in root_logger.handlers)
    assert not any(isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler) for handler in root_logger.handlers)

    logging.getLogger("x-monitor.test").info("hello logger")

    for handler in root_logger.handlers:
        handler.flush()

    assert "hello logger" in log_path.read_text(encoding="utf-8")
