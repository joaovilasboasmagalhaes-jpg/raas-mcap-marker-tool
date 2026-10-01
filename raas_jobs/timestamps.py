"""Timestamp parsing and timezone conversion helpers."""

from datetime import datetime, timedelta, timezone
from typing import Optional, Union


UTC_PLUS_2 = timezone(timedelta(hours=2))


def convert_timestamp_to_utc(
    timestamp: Union[int, float, str, datetime],
    tz: Optional[timezone] = UTC_PLUS_2,
) -> datetime:
    """Convert a timestamp or datetime to a timezone-aware datetime."""
    target_tz = tz if tz is not None else timezone.utc

    if isinstance(timestamp, datetime):
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc).astimezone(target_tz)
        return timestamp.astimezone(target_tz)

    try:
        value = float(timestamp)
        if value > 1e17:
            value /= 1e9
        elif value > 1e14:
            value /= 1e6
        elif value > 1e11:
            value /= 1e3

        converted = datetime.fromtimestamp(value, tz=timezone.utc)
        return converted.astimezone(target_tz)
    except (ValueError, TypeError, OverflowError):
        pass

    if isinstance(timestamp, str):
        clean_string = timestamp.replace("Z", "+00:00")
        converted = datetime.fromisoformat(clean_string)
        if converted.tzinfo is None:
            converted = converted.replace(tzinfo=timezone.utc)
        return converted.astimezone(target_tz)

    raise ValueError(f"Unable to parse timestamp to datetime: {timestamp!r}")
