"""Tests for shared local time formatting helpers."""

from datetime import datetime, timedelta, timezone

from src.time_utils import format_local_datetime


def test_format_local_datetime_uses_local_timezone_offset():
    """Detailed tweet timestamps should render in the local timezone."""
    utc_time = datetime(2026, 4, 2, 4, 39, 6, tzinfo=timezone.utc)
    local_time = utc_time.astimezone()
    formatted = format_local_datetime(utc_time)

    expected = (
        f"{local_time.year}-{local_time.month}-{local_time.day} "
        f"{local_time.hour:02d}:{local_time.minute:02d}:{local_time.second:02d}"
    )

    assert formatted == expected
    assert formatted != utc_time.strftime("%Y-%m-%d %H:%M:%S") or local_time.utcoffset() == timedelta(0)
