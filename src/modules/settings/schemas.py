from typing import List, Optional

from pydantic import Field

from src.shared.schemas import CamelModel


# --- Parámetros de corte ------------------------------------------------------
class CuttingSettingsResponse(CamelModel):
    """Parámetros de corte vigentes (mm) que alimentan al optimizador."""

    kerf: float = Field(..., ge=0, description="Ancho de sierra (kerf) en mm")
    top_trim: float = Field(..., ge=0, description="Recorte superior en mm")
    bottom_trim: float = Field(..., ge=0, description="Recorte inferior en mm")
    left_trim: float = Field(..., ge=0, description="Recorte izquierdo en mm")
    right_trim: float = Field(..., ge=0, description="Recorte derecho en mm")
    edge_banding_waste_factor: float = Field(
        ..., ge=0, description="Merma de tapacanto sobre el metraje neto (0.10 = +10%)"
    )


class CuttingSettingsUpdate(CamelModel):
    """Actualización parcial de los parámetros de corte."""

    kerf: Optional[float] = Field(None, ge=0)
    top_trim: Optional[float] = Field(None, ge=0)
    bottom_trim: Optional[float] = Field(None, ge=0)
    left_trim: Optional[float] = Field(None, ge=0)
    right_trim: Optional[float] = Field(None, ge=0)
    edge_banding_waste_factor: Optional[float] = Field(None, ge=0)


# --- Pre-órdenes (cotización mutable) -----------------------------------------
class PreOrderSettingsResponse(CamelModel):
    """Config de pre-órdenes vigente: vigencia y tope de abiertas por cliente."""

    preorder_validity_days: int = Field(
        ..., ge=1, description="Días de vigencia de una pre-orden (cotización)"
    )
    max_open_preorders_per_client: int = Field(
        ..., ge=1, description="Tope de pre-órdenes abiertas por cliente (antiabuso)"
    )


class PreOrderSettingsUpdate(CamelModel):
    """Actualización parcial de la config de pre-órdenes."""

    preorder_validity_days: Optional[int] = Field(None, ge=1)
    max_open_preorders_per_client: Optional[int] = Field(None, ge=1)


# --- Datos de la empresa ------------------------------------------------------
class Branch(CamelModel):
    """Sucursal mostrada en el membrete de la proforma."""

    name: str = Field(..., min_length=1, max_length=128)
    address: str = Field(..., min_length=1, max_length=256)


class CompanySettingsResponse(CamelModel):
    """Datos de la empresa vigentes (membrete de la proforma)."""

    name: str = Field(..., max_length=128)
    tagline: str = Field(..., max_length=256)
    email: str = Field(..., max_length=128)
    phone: str = Field(..., max_length=128)
    branches: List[Branch] = Field(default_factory=list)


class CompanySettingsUpdate(CamelModel):
    """Actualización parcial de los datos de la empresa."""

    name: Optional[str] = Field(None, max_length=128)
    tagline: Optional[str] = Field(None, max_length=256)
    email: Optional[str] = Field(None, max_length=128)
    phone: Optional[str] = Field(None, max_length=128)
    branches: Optional[List[Branch]] = None
