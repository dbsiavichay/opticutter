from datetime import datetime
from typing import Optional

from pydantic import Field

from src.shared.schemas import CamelModel


class NotificationResponse(CamelModel):
    """A notification as returned by the API (camelCase)."""

    id: int
    type: str
    title: str
    body: str
    order_id: Optional[int] = Field(None, description="Linked order id, if any")
    data: Optional[dict] = Field(None, description="Extra machine-readable payload")
    read_at: Optional[datetime] = Field(
        None, description="Read timestamp; null means unread"
    )
    created_at: datetime


class UnreadCountResponse(CamelModel):
    """Unread notifications count for the badge."""

    count: int = Field(..., ge=0)


class NotificationCreate(CamelModel):
    """Internal create schema (not exposed): one recipient's notification."""

    user_id: int
    type: str
    title: str
    body: str
    order_id: Optional[int] = None
    data: Optional[dict] = None


class NotificationUpdate(CamelModel):
    """Internal update schema (not exposed)."""

    read_at: Optional[datetime] = None
