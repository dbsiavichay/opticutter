"""Reusable pagination dependency (``limit``/``offset``).

Aligns listings with the ``meta.pagination`` contract. Replaces the previous
``skip``/``limit`` pair (``skip`` -> ``offset``).
"""

from fastapi import Query


class PageParams:
    """Pagination parameters injectable via ``Depends()``."""

    def __init__(
        self,
        limit: int = Query(20, ge=1, le=100, description="Maximum number of records"),
        offset: int = Query(0, ge=0, description="Number of records to skip"),
    ):
        self.limit = limit
        self.offset = offset
