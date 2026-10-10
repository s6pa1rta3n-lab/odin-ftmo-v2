"""FTMO day boundary: midnight Europe/Prague (CET/CEST, DST-aware)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

PRAGUE = ZoneInfo("Europe/Prague")


def tz(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def trading_day(now_utc: datetime, zone: ZoneInfo = PRAGUE) -> date:
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    return now_utc.astimezone(zone).date()


def day_start_utc(day: date, zone: ZoneInfo = PRAGUE) -> datetime:
    """UTC instant of local midnight on ``day``. Handles the DST shift (22:00Z vs 23:00Z)."""

    local_midnight = datetime(day.year, day.month, day.day, tzinfo=zone)
    return local_midnight.astimezone(timezone.utc)


def day_window_utc(now_utc: datetime, zone: ZoneInfo = PRAGUE) -> "tuple[datetime, datetime]":
    """[start, end) of the current FTMO day in UTC."""

    day = trading_day(now_utc, zone)
    start = day_start_utc(day, zone)
    end = day_start_utc(day + timedelta(days=1), zone)
    return start, end
