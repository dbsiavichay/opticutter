from typing import Optional

from pydantic import Field

from src.shared.schemas import CamelModel


class BranchBase(CamelModel):
    code: str = Field(
        ..., min_length=1, max_length=32, description="Código único de la sucursal"
    )
    name: str = Field(
        ..., min_length=1, max_length=128, description="Nombre de la sucursal"
    )
    address: Optional[str] = Field(
        None, max_length=256, description="Dirección (membrete de la proforma)"
    )
    phone: Optional[str] = Field(
        None, max_length=32, description="Teléfono de contacto"
    )


class BranchCreate(BranchBase):
    """Alta de una sucursal."""


class BranchUpdate(CamelModel):
    """Actualización parcial de una sucursal."""

    code: Optional[str] = Field(None, min_length=1, max_length=32)
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    address: Optional[str] = Field(None, max_length=256)
    phone: Optional[str] = Field(None, max_length=32)
    is_active: Optional[bool] = Field(None, description="Activa/inactiva (baja lógica)")


class BranchResponse(BranchBase):
    """Representación pública de una sucursal."""

    id: int = Field(..., description="ID de la sucursal")
    is_active: bool = Field(..., description="Activa/inactiva")
