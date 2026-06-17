from datetime import datetime
from typing import Optional

from pydantic import Field

from src.modules.branches.schemas import BranchRefResponse
from src.shared.schemas import CamelModel


class DraftCreate(CamelModel):
    """Crear un borrador del optimizador.

    Los campos mapean 1:1 a columnas para que ``CRUDService.create`` funcione con
    ``self.model(**data.model_dump())``. ``payload`` es un objeto JSON opaco: el
    backend no valida su forma interna (la define el frontend).
    """

    name: str = Field(..., min_length=1, max_length=128, description="Draft name")
    client_id: Optional[int] = Field(
        default=None, description="Optional client this draft is associated with"
    )
    branch_id: Optional[int] = Field(
        default=None,
        description=(
            "Target branch. Ignored for branch staff (forced to their own branch); "
            "required for a global admin."
        ),
    )
    payload: dict = Field(
        ..., description="Opaque optimizer form state (materials + pieces, as-is)"
    )


class DraftUpdate(CamelModel):
    """Actualizar (sobrescribir) un borrador. Todos los campos son opcionales."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    client_id: Optional[int] = None
    payload: Optional[dict] = None


class DraftResponse(CamelModel):
    """Detalle de un borrador, incluido el ``payload`` completo."""

    id: int
    name: str
    client_id: Optional[int] = None
    branch: BranchRefResponse = Field(..., description="Owning branch")
    payload: dict
    created_at: datetime
    updated_at: datetime


class DraftSummaryResponse(CamelModel):
    """Resumen liviano para el listado: el ``payload`` se omite a propósito."""

    id: int
    name: str
    client_id: Optional[int] = None
    branch: BranchRefResponse = Field(..., description="Owning branch")
    created_at: datetime
    updated_at: datetime
