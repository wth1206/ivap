"""UTC time helpers.

The database stores UTC; API responses use ISO-8601 with a trailing ``Z``.
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_naive() -> datetime:
    """UTC without tzinfo, for MySQL DATETIME columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_iso(value: datetime) -> str:
    """Serialize a datetime as ``2026-11-06T11:20:00.123Z``."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
