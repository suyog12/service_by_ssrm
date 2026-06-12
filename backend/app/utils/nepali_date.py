import nepali_datetime
from datetime import date, datetime
from typing import Optional


def to_bs(ad_date) -> Optional[str]:
    """Convert an AD date/datetime to a BS date string (YYYY-MM-DD)."""
    if ad_date is None:
        return None
    if isinstance(ad_date, datetime):
        ad_date = ad_date.date()
    try:
        bs = nepali_datetime.date.from_datetime_date(ad_date)
        return bs.strftime("%Y-%m-%d")
    except Exception:
        return None


def to_ad(bs_date_str: str) -> Optional[date]:
    """Convert a BS date string (YYYY-MM-DD) to an AD date."""
    if not bs_date_str:
        return None
    try:
        parts = [int(p) for p in bs_date_str.split("-")]
        bs = nepali_datetime.date(parts[0], parts[1], parts[2])
        return bs.to_datetime_date()
    except Exception:
        return None


def add_bs_fields(d: dict, fields: list) -> dict:
    """
    For each field name in `fields` that exists in dict `d` and is not None,
    add a companion `<field>_bs` key with the BS date string.
    Mutates and returns `d`.
    """
    for f in fields:
        if f in d and d[f] is not None:
            d[f"{f}_bs"] = to_bs(d[f])
    return d