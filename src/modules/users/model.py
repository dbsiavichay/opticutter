from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.modules.users.enums import UserRole
from src.shared.database import Base
from src.shared.mixins import AuditMixin, TimestampMixin


class UserModel(TimestampMixin, AuditMixin, Base):
    """Internal system user (staff): credentials + role.

    Login is by ``email`` (unique). The password is never stored in plain text:
    only its bcrypt hash in ``hashed_password``. Deactivation is logical
    (``is_active``) to avoid breaking references or losing traceability.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(128))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default=UserRole.OPERATOR.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Branch assigned to staff (seller/operator). NULL = global administrator,
    # who sees and operates all branches. Editable by the admin (moves the branch);
    # the change takes effect instantly (the branch doesn't travel in the JWT).
    branch_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("branches.id"), index=True, nullable=True
    )
