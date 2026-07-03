from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.modules.notifications.schemas import (
    NotificationResponse,
    UnreadCountResponse,
)
from src.modules.notifications.service import (
    NotificationService,
    notification_service,
)
from src.modules.users.dependencies import require_permission
from src.modules.users.model import UserModel
from src.shared.pagination import PageParams
from src.shared.responses import (
    ERROR_RESPONSES,
    DataResponse,
    PaginatedResponse,
    ok,
    page,
)

# Every authenticated role reads/acks its OWN notifications: the guard authorizes
# and yields the current user, and the service scopes every query to
# ``current_user.id`` (the RESOURCE_ROLES matrix is role-level only).
router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    responses=ERROR_RESPONSES,
)


@router.get("/", response_model=PaginatedResponse[NotificationResponse])
def list_notifications(
    paging: PageParams = Depends(),
    unread: Optional[bool] = Query(
        None, description="If true, return only unread notifications"
    ),
    svc: NotificationService = Depends(notification_service),
    current_user: UserModel = Depends(require_permission("notifications:read")),
):
    """Lists the authenticated user's notifications (newest first)."""
    items, total = svc.list_for_user(
        current_user.id,
        unread_only=bool(unread),
        limit=paging.limit,
        offset=paging.offset,
    )
    return page(items, total, paging.limit, paging.offset)


@router.get("/unread-count", response_model=DataResponse[UnreadCountResponse])
def unread_count(
    svc: NotificationService = Depends(notification_service),
    current_user: UserModel = Depends(require_permission("notifications:read")),
):
    """Number of unread notifications (badge)."""
    return ok(UnreadCountResponse(count=svc.unread_count(current_user.id)))


@router.patch(
    "/{notification_id}/read", response_model=DataResponse[NotificationResponse]
)
def mark_notification_read(
    notification_id: int,
    svc: NotificationService = Depends(notification_service),
    current_user: UserModel = Depends(require_permission("notifications:read")),
):
    """Marks one notification as read (must belong to the user)."""
    return ok(svc.mark_read(notification_id, current_user.id))


@router.post("/read-all", response_model=DataResponse[UnreadCountResponse])
def mark_all_notifications_read(
    svc: NotificationService = Depends(notification_service),
    current_user: UserModel = Depends(require_permission("notifications:read")),
):
    """Marks all the user's notifications as read; returns how many were updated."""
    return ok(UnreadCountResponse(count=svc.mark_all_read(current_user.id)))
