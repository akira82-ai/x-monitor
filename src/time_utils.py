"""Local time formatting helpers for user-visible timestamps."""

from datetime import datetime


def to_local_time(timestamp: datetime) -> datetime:
    """Convert an aware timestamp to the machine's local timezone."""
    return timestamp.astimezone()


def format_local_datetime(timestamp: datetime) -> str:
    """Format a timestamp using local time for detailed display."""
    local_time = to_local_time(timestamp)
    return (
        f"{local_time.year}-{local_time.month}-{local_time.day} "
        f"{local_time.hour:02d}:{local_time.minute:02d}:{local_time.second:02d}"
    )


def format_local_month_day(timestamp: datetime) -> str:
    """Format a timestamp using local time for compact list display."""
    local_time = to_local_time(timestamp)
    return f"{local_time.month:02d}-{local_time.day:02d}"
