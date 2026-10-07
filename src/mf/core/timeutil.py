"""All times are timezone-aware UTC; serialized as ISO-8601 with a trailing 'Z'."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

UTC = timezone.utc


def parse(value: str | int | float | datetime | None) -> datetime | None:
    """Parse ISO strings (with 'Z' or offset), unix seconds, or datetimes into aware UTC."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=UTC)
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    if len(s) == 10:  # bare date
        s += "T00:00:00+00:00"
    dt = datetime.fromisoformat(s)
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def iso(dt: datetime) -> str:
    dt = parse(dt)
    assert dt is not None
    if dt.microsecond:
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def now() -> datetime:
    return datetime.now(UTC)


def to_unix(dt: datetime) -> int:
    return int(parse(dt).timestamp())


def floor_hour(dt: datetime) -> datetime:
    return parse(dt).replace(minute=0, second=0, microsecond=0)


def days(dt_a: datetime, dt_b: datetime) -> float:
    """(dt_a - dt_b) in fractional days."""
    return (parse(dt_a) - parse(dt_b)) / timedelta(days=1)


def month_key(dt: datetime) -> str:
    return parse(dt).strftime("%Y-%m")
