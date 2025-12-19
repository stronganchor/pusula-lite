from __future__ import annotations

from datetime import date, datetime

# Consistent Turkish date display: Gün-Ay-Yıl (GG-AA-YYYY)
DATE_DISPLAY_FORMAT = "%d-%m-%Y"


def format_date_tr(value: date | datetime | None) -> str:
    """Return a day-month-year string (GG-AA-YYYY) or empty when value is falsy."""
    if not value:
        return ""
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime(DATE_DISPLAY_FORMAT)


def parse_date_tr(text: str) -> date:
    """Parse a GG-AA-YYYY string into a date."""
    return datetime.strptime(text.strip(), DATE_DISPLAY_FORMAT).date()


def today_str_tr() -> str:
    """Today formatted as GG-AA-YYYY."""
    return format_date_tr(date.today())
