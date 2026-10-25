from datetime import datetime, date
from typing import Optional, Union
from zoneinfo import ZoneInfo

IST_TIMEZONE = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    """Returns the current timezone-aware datetime in Asia/Kolkata (IST)."""
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
            val = val.replace(tzinfo=ZoneInfo("UTC")).astimezone(IST_TIMEZONE)
        else:
            val = val.astimezone(IST_TIMEZONE)
        return val.date()
    return val
