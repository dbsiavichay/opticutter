from datetime import datetime
from typing import Iterable, List, Optional, Tuple

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.notifications.enums import NotificationType
from src.modules.notifications.model import NotificationModel
from src.modules.notifications.schemas import NotificationCreate, NotificationUpdate
from src.shared.crud import CRUDService
from src.shared.database import get_db
from src.shared.exceptions import EntityNotFoundError


class NotificationService(
    CRUDService[NotificationModel, NotificationCreate, NotificationUpdate]
):
    """Per-recipient notifications: listing, unread count, read marking, fan-out.

    Every read/write is scoped by ``user_id`` (the recipient) at the query level:
    the router passes ``current_user.id`` so a user only ever sees or mutates
    their own notifications.
    """

    model = NotificationModel

    def list_for_user(
        self,
        user_id: int,
        unread_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[NotificationModel], int]:
        """A page of the user's notifications (newest first); ``(items, total)``."""
        query = self.db.query(NotificationModel).filter(
            NotificationModel.user_id == user_id
        )
        if unread_only:
            query = query.filter(NotificationModel.read_at.is_(None))
        query = query.order_by(NotificationModel.id.desc())
        return self._paginate(query, limit, offset)

    def unread_count(self, user_id: int) -> int:
        """Number of unread notifications for the badge."""
        return (
            self.db.query(NotificationModel)
            .filter(
                NotificationModel.user_id == user_id,
                NotificationModel.read_at.is_(None),
            )
            .count()
        )

    def mark_read(self, notification_id: int, user_id: int) -> NotificationModel:
        """Marks one notification as read; 404 if it isn't the user's (idempotent)."""
        notification = self.get(notification_id)
        if notification is None or notification.user_id != user_id:
            raise EntityNotFoundError("Notification", notification_id)
        if notification.read_at is None:
            notification.read_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(notification)
        return notification

    def mark_all_read(self, user_id: int) -> int:
        """Marks all the user's unread notifications as read; returns how many."""
        updated = (
            self.db.query(NotificationModel)
            .filter(
                NotificationModel.user_id == user_id,
                NotificationModel.read_at.is_(None),
            )
            .update(
                {NotificationModel.read_at: datetime.utcnow()},
                synchronize_session=False,
            )
        )
        self.db.commit()
        return updated

    def create_bulk(
        self,
        user_ids: Iterable[int],
        notification_type: NotificationType,
        title: str,
        body: str,
        order_id: Optional[int] = None,
        data: Optional[dict] = None,
    ) -> List[NotificationModel]:
        """Fan-out: one notification row per recipient, in a single commit."""
        rows = [
            NotificationModel(
                user_id=user_id,
                type=notification_type.value,
                title=title,
                body=body,
                order_id=order_id,
                data=data,
            )
            for user_id in user_ids
        ]
        self.db.add_all(rows)
        self.db.commit()
        return rows


def notification_service(db: Session = Depends(get_db)) -> NotificationService:
    """``NotificationService`` provider for route injection."""
    return NotificationService(db)
