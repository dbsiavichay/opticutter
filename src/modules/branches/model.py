from typing import Optional

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base
from src.shared.mixins import AuditMixin, TimestampMixin


class BranchModel(TimestampMixin, AuditMixin, Base):
    """Business branch (warehouse): root entity of the multi-branch isolation.

    Branches used to only exist as a letterhead JSON in ``settings``; now
    they're a real entity that orders, pre-orders, drafts and users point to
    (``branch_id``). Staff (seller/operator) is bound to a branch; the admin
    isn't (sees and operates all of them). Deactivation is logical
    (``is_active``) to avoid breaking historical FKs.
    """

    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    address: Mapped[Optional[str]] = mapped_column(String(256))
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
