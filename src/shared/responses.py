"""API response contracts: uniform success and error envelope.

Every JSON response shares ``meta`` (requestId + timestamp). Success travels in
``data`` (single resource or paginated list) and errors in ``errors`` (a list,
ready for multiple validation errors). The ``ok``/``page`` helpers reduce the
endpoint to a single line; ``meta`` is auto-filled via ``default_factory``.

Exempt from the envelope (by design): PDF file transport
(``StreamingResponse``/base64) and the diagnostic endpoints (``system``).
"""

from datetime import datetime, timezone
from typing import Any, Generic, List, Optional, Sequence, TypeVar

from pydantic import Field

from src.shared.context import get_request_id
from src.shared.schemas import CamelModel

T = TypeVar("T")


class Meta(CamelModel):
    """Metadata common to every response (observability/traceability)."""

    request_id: str = Field(default_factory=get_request_id)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Pagination(CamelModel):
    total: int
    limit: int
    offset: int


class PaginatedMeta(Meta):
    pagination: Pagination


class DataResponse(CamelModel, Generic[T]):
    """Single resource or composite structure wrapped in ``data``."""

    data: T
    meta: Meta = Field(default_factory=Meta)


class PaginatedResponse(CamelModel, Generic[T]):
    """Listing with total count in ``meta.pagination``."""

    data: List[T]
    meta: PaginatedMeta


class ErrorDetail(CamelModel):
    code: str
    message: str
    field: Optional[str] = None


class ErrorResponse(CamelModel):
    errors: List[ErrorDetail]
    meta: Meta = Field(default_factory=Meta)


def ok(data: Any) -> dict:
    """Wraps a resource. FastAPI validates it against ``DataResponse[T]``."""
    return {"data": data}


def page(items: Sequence, total: int, limit: int, offset: int) -> dict:
    """Wraps a paginated listing. Validated against ``PaginatedResponse[T]``."""
    return {
        "data": items,
        "meta": {"pagination": {"total": total, "limit": limit, "offset": offset}},
    }


# OpenAPI documentation: a single error group applied at router level
# (``APIRouter(responses=ERROR_RESPONSES)``). The success shape is already
# documented by each route's generic ``response_model``.
ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Invalid request"},
    401: {"model": ErrorResponse, "description": "Not authenticated"},
    403: {"model": ErrorResponse, "description": "Forbidden"},
    404: {"model": ErrorResponse, "description": "Resource not found"},
    409: {"model": ErrorResponse, "description": "State conflict"},
    422: {"model": ErrorResponse, "description": "Validation error"},
    500: {"model": ErrorResponse, "description": "Internal error"},
}
