"""Rango de fechas y bucketing temporal.

``DateRange`` es una dependencia inyectable (como ``PageParams``) que parsea y valida
los query params ``from``/``to``. El bucketing se hace en Python (no en SQL) para
mantener la lógica en el dominio sin dependencias de funciones específicas del dialecto.

Todos los timestamps del dominio son naive UTC (``datetime.utcnow()``); aquí se tratan
como tales, sin conversión de zona.
"""

from datetime import date, datetime, time, timedelta

from fastapi import Query

from src.modules.analytics.constants import Granularity
from src.shared.exceptions import ValidationError

_DEFAULT_WINDOW_DAYS = 30


class DateRange:
    """Ventana ``[start, end)`` medio-abierta sobre ``created_at``.

    Defaults: últimos 30 días terminando hoy (UTC). El borde superior es exclusivo
    (``end = to + 1 día``) para evitar el bug del límite ``23:59:59``.
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
    """Fecha de inicio del bucket al que pertenece ``d``."""
    if granularity is Granularity.day:
        return d
    if granularity is Granularity.week:
        return d - timedelta(days=d.weekday())  # lunes ISO
    return d.replace(day=1)  # month


def _advance(d: date, granularity: Granularity) -> date:
    """Siguiente fecha de bucket."""
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
    """Eje denso de fechas de bucket que cubre ``[date_from, date_to]`` (sin huecos)."""
    keys: list[date] = []
    cur = bucket_key(date_from, granularity)
    last = bucket_key(date_to, granularity)
    while cur <= last:
        keys.append(cur)
        cur = _advance(cur, granularity)
    return keys
