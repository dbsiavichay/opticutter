"""Dependencia reusable de paginación (``limit``/``offset``).

Alinea los listados con el contrato ``meta.pagination``. Reemplaza el par
``skip``/``limit`` previo (``skip`` -> ``offset``).
"""

from fastapi import Query


class PageParams:
    """Parámetros de paginación inyectables vía ``Depends()``."""

    def __init__(
        self,
        limit: int = Query(20, ge=1, le=100, description="Máximo de registros"),
        offset: int = Query(0, ge=0, description="Registros a omitir"),
    ):
        self.limit = limit
        self.offset = offset
