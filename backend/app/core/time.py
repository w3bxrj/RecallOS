from datetime import datetime, date, timezone, timedelta
from typing import Optional, Union

try:
    from zoneinfo import ZoneInfo
    IST_TIMEZONE = ZoneInfo("Asia/Kolkata")
except Exception:
    # India Standard Time (IST) is strictly UTC+05:30 year-round with no DST
    IST_TIMEZONE = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")


def now_ist() -> datetime:
    """Returns current timezone-aware datetime in Asia/Kolkata (IST)."""
    return datetime.now(IST_TIMEZONE)


def today_ist() -> date:
    """Returns current date in Asia/Kolkata (IST)."""
    return now_ist().date()


def ist_midnight(d: date) -> datetime:
    """Returns midnight (00:00:00) of a given date in Asia/Kolkata timezone."""
    return datetime.combine(d, datetime.min.time(), tzinfo=IST_TIMEZONE)


def to_ist_date(val: Optional[Union[datetime, date]]) -> Optional[date]:
    """Converts a datetime or date object to an Asia/Kolkata date.

    Handles:
    - None -> None
    - date -> date
    - tz-aware datetime -> converts to Asia/Kolkata timezone and returns its date
    - naive datetime (from SQLite where now_ist was stored as IST wall-time) -> returns its date directly
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is not None:
            return val.astimezone(IST_TIMEZONE).date()
        # In SQLite, now_ist() is stored as naive IST wall clock time; its date is already IST
        return val.date()
    return val

