"""Date range and time bucketing.

``DateRange`` is an injectable dependency (like ``PageParams``) that parses and
validates the ``from``/``to`` query params. Bucketing is done in Python (not SQL)
to keep the logic in the domain, free of dialect-specific function dependencies.

All domain timestamps are naive UTC (``datetime.utcnow()``); they're treated as
such here, with no timezone conversion.
"""

from datetime import date, datetime, time, timedelta

from fastapi import Query

from src.modules.analytics.constants import Granularity
from src.shared.exceptions import ValidationError

_DEFAULT_WINDOW_DAYS = 30


class DateRange:
    """Half-open ``[start, end)`` window over ``created_at``.

    Defaults: last 30 days ending today (UTC). The upper bound is exclusive
    (``end = to + 1 day``) to avoid the ``23:59:59`` boundary bug.
    """

    def __init__(
        self,
        date_from: date | None = Query(
            None, alias="from", description="Inicio del rango (YYYY-MM-DD, inclusivo)"
        ),
        date_to: date | None = Query(
            None, alias="to", description="Fin del rango (YYYY-MM-DD, inclusivo)"
        ),
    ):
        today = datetime.utcnow().date()
        self.date_to = date_to or today
        self.date_from = date_from or (
            self.date_to - timedelta(days=_DEFAULT_WINDOW_DAYS)
        )
        if self.date_from > self.date_to:
            raise ValidationError(
                "'from' debe ser menor o igual que 'to'", field="from"
            )
        self.start = datetime.combine(self.date_from, time.min)
        self.end = datetime.combine(self.date_to, time.min) + timedelta(days=1)


def bucket_key(d: date, granularity: Granularity) -> date:
    """Start date of the bucket ``d`` belongs to."""
    if granularity is Granularity.day:
        return d
    if granularity is Granularity.week:
        return d - timedelta(days=d.weekday())  # ISO Monday
    return d.replace(day=1)  # month


def _advance(d: date, granularity: Granularity) -> date:
    """Next bucket date."""
    if granularity is Granularity.day:
        return d + timedelta(days=1)
    if granularity is Granularity.week:
        return d + timedelta(days=7)
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1)
    return d.replace(month=d.month + 1)


def iter_buckets(
    date_from: date, date_to: date, granularity: Granularity
) -> list[date]:
    """Dense axis of bucket dates covering ``[date_from, date_to]`` (no gaps)."""
    keys: list[date] = []
    cur = bucket_key(date_from, granularity)
    last = bucket_key(date_to, granularity)
    while cur <= last:
        keys.append(cur)
        cur = _advance(cur, granularity)
    return keys
