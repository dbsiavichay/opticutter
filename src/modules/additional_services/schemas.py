from typing import Optional

from pydantic import Field

from src.shared.schemas import CamelModel


class AdditionalServiceBase(CamelModel):
    name: str = Field(
        ..., min_length=1, max_length=128, description="Additional service name"
    )
    price: float = Field(
        ..., ge=0, description="Default unit price (editable per line on the quote)"
    )
    is_active: bool = Field(
        default=True, description="Whether it appears in the quote's service picker"
    )


class AdditionalServiceCreate(AdditionalServiceBase):
    """Schema for creating an additional service."""


class AdditionalServiceUpdate(CamelModel):
    """Schema for updating an additional service (all fields optional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=128)
    price: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None


class AdditionalServiceResponse(AdditionalServiceBase):
    """Schema for additional service responses."""

    id: int = Field(..., description="Additional service ID")
