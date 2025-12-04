from typing import Optional

from pydantic import BaseModel, Field


class ClientBase(BaseModel):
    phone: str = Field(
        ..., min_length=1, max_length=32, description="Client phone number"
    )
    first_name: Optional[str] = Field(
        None, max_length=64, description="Client first name"
    )
    last_name: Optional[str] = Field(
        None, max_length=64, description="Client last name"
    )


class ClientCreate(ClientBase):
    """Schema for creating a new client"""


class ClientUpdate(BaseModel):
    """Schema for updating an existing client"""

    phone: Optional[str] = Field(
        None, min_length=1, max_length=32, description="Client phone number"
    )
    first_name: Optional[str] = Field(
        None, max_length=64, description="Client first name"
    )
    last_name: Optional[str] = Field(
        None, max_length=64, description="Client last name"
    )


class ClientResponse(ClientBase):
    """Schema for client responses"""

    id: int = Field(..., description="Client ID")

    class Config:
        from_attributes = True
