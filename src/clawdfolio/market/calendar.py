"""Trading calendar utilities."""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

# US market holidays (fixed dates - actual holidays may vary by year)
# This is a simplified version; for production, consider using a library
# like `exchange_calendars` or `pandas_market_calendars`
US_HOLIDAYS_2024 = {
    date(2024, 1, 1),   # New Year's Day
    date(2024, 1, 15),  # MLK Day
    date(2024, 2, 19),  # Presidents Day
    date(2024, 3, 29),  # Good Friday
    date(2024, 5, 27),  # Memorial Day
    date(2024, 6, 19),  # Juneteenth
    date(2024, 7, 4),   # Independence Day
    date(2024, 9, 2),   # Labor Day
    date(2024, 11, 28), # Thanksgiving
    date(2024, 12, 25), # Christmas
}

US_HOLIDAYS_2025 = {
    date(2025, 1, 1),   # New Year's Day
    date(2025, 1, 20),  # MLK Day
    date(2025, 2, 17),  # Presidents Day
    date(2025, 4, 18),  # Good Friday
    date(2025, 5, 26),  # Memorial Day
    date(2025, 6, 19),  # Juneteenth
    date(2025, 7, 4),   # Independence Day
    date(2025, 9, 1),   # Labor Day
    date(2025, 11, 27), # Thanksgiving
    date(2025, 12, 25), # Christmas
}

US_HOLIDAYS_2026 = {
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 19),  # MLK Day
    date(2026, 2, 16),  # Presidents Day
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 25),  # Memorial Day
    date(2026, 6, 19),  # Juneteenth
    date(2026, 7, 3),   # Independence Day (observed)
    date(2026, 9, 7),   # Labor Day
    date(2026, 11, 26), # Thanksgiving
    date(2026, 12, 25), # Christmas
}

US_HOLIDAYS_2027 = {
    date(2027, 1, 1),   # New Year's Day
    date(2027, 1, 18),  # MLK Day
    date(2027, 2, 15),  # Presidents Day
    date(2027, 3, 26),  # Good Friday
    date(2027, 5, 31),  # Memorial Day
    date(2027, 6, 18),  # Juneteenth (observed)
    date(2027, 7, 5),   # Independence Day (observed)
    date(2027, 9, 6),   # Labor Day
    date(2027, 11, 25), # Thanksgiving
    date(2027, 12, 24), # Christmas (observed)
}

US_HOLIDAYS = US_HOLIDAYS_2024 | US_HOLIDAYS_2025 | US_HOLIDAYS_2026 | US_HOLIDAYS_2027


def is_weekend(d: date) -> bool:
    """Check if date is a weekend."""
    return d.weekday() >= 5  # Saturday = 5, Sunday = 6


def is_us_holiday(d: date) -> bool:
    """Check if date is a US market holiday."""
    return d in US_HOLIDAYS


def is_trading_day(d: date | None = None, market: str = "US") -> bool:
    """Check if date is a trading day.

    Args:
        d: Date to check (defaults to today)
        market: Market code (currently only US supported)

    Returns:
        True if it's a trading day
    """
    if d is None:
        d = date.today()

    if is_weekend(d):
        return False

    if market.upper() == "US":
        return not is_us_holiday(d)

    # Default: assume weekdays are trading days
    return True


def next_trading_day(d: date | None = None, market: str = "US") -> date:
    """Get the next trading day after the given date.

    Args:
        d: Start date (defaults to today)
        market: Market code

    Returns:
        Next trading day
    """
    if d is None:
        d = date.today()

    d = d + timedelta(days=1)
    while not is_trading_day(d, market):
        d += timedelta(days=1)

    return d


def prev_trading_day(d: date | None = None, market: str = "US") -> date:
    """Get the previous trading day before the given date.

    Args:
        d: Start date (defaults to today)
        market: Market code

    Returns:
        Previous trading day
    """
    if d is None:
        d = date.today()

    d = d - timedelta(days=1)
    while not is_trading_day(d, market):
        d -= timedelta(days=1)

    return d


def trading_days_between(
    start: date, end: date, market: str = "US"
) -> list[date]:
    """Get all trading days between two dates (inclusive).

    Args:
        start: Start date
        end: End date
        market: Market code

    Returns:
        List of trading days
    """
    days = []
    current = start

    while current <= end:
        if is_trading_day(current, market):
            days.append(current)
        current += timedelta(days=1)

    return days


def trading_days_count(
    start: date, end: date, market: str = "US"
) -> int:
    """Count trading days between two dates.

    Args:
        start: Start date
        end: End date
        market: Market code

    Returns:
        Number of trading days
    """
    return len(trading_days_between(start, end, market))


@lru_cache(maxsize=1)
def get_current_year_holidays(market: str = "US") -> set[date]:
    """Get holidays for the current year (cached)."""
    current_year = date.today().year

    if market.upper() == "US":
        return {h for h in US_HOLIDAYS if h.year == current_year}

    return set()


def days_until_next_holiday(market: str = "US") -> int | None:
    """Get days until the next market holiday.

    Returns:
        Days until next holiday, or None if unknown
    """
    today = date.today()
    holidays = get_current_year_holidays(market)

    future_holidays = [h for h in holidays if h > today]
    if not future_holidays:
        return None

    next_holiday = min(future_holidays)
    return (next_holiday - today).days
