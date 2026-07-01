from typing import Optional

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import Base
from src.shared.mixins import AuditMixin, TimestampMixin


class OptimizationDraftModel(TimestampMixin, AuditMixin, Base):
    """Optimizer draft: durable, mutable work in progress.

    Unlike the optimization (ephemeral, cache-only computation) and the order
    (frozen immutable output), a draft is the optimizer's **raw editable
    input** saved to resume later. ``payload`` is an opaque JSON bag holding
    the form state exactly as the frontend sends it (including half-filled
    rows): the backend persists it without validating its internal shape.

    It's workshop-wide (no per-user scoping); ``client_id`` is optional, just metadata.
    """

    __tablename__ = "optimization_drafts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    # Branch owning the draft: isolates work in progress between branches.
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), index=True)
    client_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("clients.id"), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON)

    branch: Mapped["BranchModel"] = relationship("BranchModel")  # noqa: F821
