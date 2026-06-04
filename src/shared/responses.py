"""Contratos de respuesta del API: envoltura uniforme de éxito y error.

Toda respuesta JSON comparte ``meta`` (requestId + timestamp). El éxito viaja en
``data`` (recurso o lista paginada) y el error en ``errors`` (lista, preparada
para múltiples errores de validación). Los helpers ``ok``/``page`` reducen el
endpoint a una sola línea; ``meta`` se autocompleta por ``default_factory``.

Exentos de la envoltura (por diseño): el transporte de archivos PDF
(``StreamingResponse``/base64) y los endpoints de diagnóstico (``system``).
"""

from datetime import datetime, timezone
from typing import Any, Generic, List, Optional, Sequence, TypeVar

from pydantic import Field

from src.shared.context import get_request_id
from src.shared.schemas import CamelModel

T = TypeVar("T")


class Meta(CamelModel):
    """Metadatos comunes a toda respuesta (observabilidad/trazabilidad)."""

    request_id: str = Field(default_factory=get_request_id)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Pagination(CamelModel):
    total: int
    limit: int
    offset: int


class PaginatedMeta(Meta):
    pagination: Pagination


class DataResponse(CamelModel, Generic[T]):
    """Recurso único o estructura compuesta envuelta en ``data``."""

    data: T
    meta: Meta = Field(default_factory=Meta)


class PaginatedResponse(CamelModel, Generic[T]):
    """Listado con conteo total en ``meta.pagination``."""

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
    """Envuelve un recurso. FastAPI lo valida contra ``DataResponse[T]``."""
    return {"data": data}


def page(items: Sequence, total: int, limit: int, offset: int) -> dict:
    """Envuelve un listado paginado. Se valida contra ``PaginatedResponse[T]``."""
    return {
        "data": items,
        "meta": {"pagination": {"total": total, "limit": limit, "offset": offset}},
    }


# Documentación OpenAPI: un único grupo de errores aplicado a nivel router
# (``APIRouter(responses=ERROR_RESPONSES)``). La forma de éxito ya la documenta
# el ``response_model`` genérico de cada ruta.
ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Solicitud inválida"},
    404: {"model": ErrorResponse, "description": "Recurso no encontrado"},
    409: {"model": ErrorResponse, "description": "Conflicto de estado"},
    422: {"model": ErrorResponse, "description": "Error de validación"},
    500: {"model": ErrorResponse, "description": "Error interno"},
}
