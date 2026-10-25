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


def to_ist_date(val: Optional[Union[datetime, date]]) -> Optional[date]:
    """Converts a datetime or date object to an Asia/Kolkata date."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            # Assume UTC if naive, convert to IST
            val = val.replace(tzinfo=timezone.utc).astimezone(IST_TIMEZONE)
        else:
            val = val.astimezone(IST_TIMEZONE)
        return val.date()
    return val
