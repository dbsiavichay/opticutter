from typing import Optional

from pydantic import Field

from src.shared.schemas import CamelModel


class ClientBase(CamelModel):
    identifier: str = Field(
        ..., min_length=1, max_length=32, description="Client external identifier"
    )
    first_name: Optional[str] = Field(
        None, max_length=64, description="Client first name"
    )
    last_name: Optional[str] = Field(
        None, max_length=64, description="Client last name"
    )
    source: Optional[str] = Field(
        None, max_length=64, description="Client source (e.g. instagram, referral)"
    )
    phone: Optional[str] = Field(
        None, max_length=32, description="Client mobile phone (celular)"
    )
    email: Optional[str] = Field(
        None, max_length=128, description="Client email (optional)"
    )


class ClientCreate(ClientBase):
    """Schema for creating a new client."""


class ClientUpdate(CamelModel):
    """Schema for updating an existing client."""

    identifier: Optional[str] = Field(
        None, min_length=1, max_length=32, description="Client external identifier"
    )
    first_name: Optional[str] = Field(
        None, max_length=64, description="Client first name"
    )
    last_name: Optional[str] = Field(
        None, max_length=64, description="Client last name"
    )
    source: Optional[str] = Field(
        None, max_length=64, description="Client source (e.g. instagram, referral)"
    )
    phone: Optional[str] = Field(
        None, max_length=32, description="Client mobile phone (celular)"
    )
    email: Optional[str] = Field(
        None, max_length=128, description="Client email (optional)"
    )


class ClientResponse(ClientBase):
    """Schema for client responses."""

    id: int = Field(..., description="Client ID")
