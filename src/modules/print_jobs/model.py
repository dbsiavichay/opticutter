from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import Base
from src.shared.mixins import AuditMixin, TimestampMixin


class PrintJobType(str, Enum):
    """What the job prints, which drives the agent's printer/renderer choice.

    ``label`` → TSPL on the thermal printer (per cut piece); ``sheet`` → PDF on
    the inkjet (consolidated packet when an order is completed).
    """

    label = "label"
    sheet = "sheet"


class PrintPayloadFormat(str, Enum):
    """Wire format of the rendered payload the agent downloads and prints raw."""

    tspl = "tspl"
    pdf = "pdf"


class PrintJobStatus(str, Enum):
    """Lifecycle of a print job (at-least-once delivery).

    ``pending`` → queued, waiting for an agent. ``sent`` → claimed by an agent
    (re-queued to ``pending`` if it doesn't ack within the visibility timeout).
    ``done`` / ``error`` → the agent reported the result. ``expired`` → the TTL
    lapsed with no agent (the shop PC was off); it won't print stale.
    """

    pending = "pending"
    sent = "sent"
    done = "done"
    error = "error"
    expired = "expired"


# Non-terminal statuses: the ones an agent can still claim and the sweeps act on.
PRINT_JOB_OPEN_STATUSES = (PrintJobStatus.pending.value, PrintJobStatus.sent.value)


class PrintAgentModel(TimestampMixin, AuditMixin, Base):
    """A print agent: one per branch shop PC, authenticating the long-poll endpoints.

    Only the sha256 ``token_hash`` is stored (never the raw token), same as the
    refresh tokens / pre-order review links: a random 256-bit token is its own
    salt, and the hash is what the ``Authorization: Bearer`` lookup matches (an
    indexed equality lookup bcrypt couldn't serve). ``created_by`` (AuditMixin) is
    the admin who registered it.
    """

    __tablename__ = "print_agents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Branch whose jobs this agent claims. CASCADE: removing a branch removes its
    # agents (their jobs cascade from the branch too).
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Refreshed on every poll (presence indicator for the admin agent list).
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class PrintJobModel(TimestampMixin, AuditMixin, Base):
    """A single print job: a payload rendered server-side, spooled to disk and
    delivered to the branch's agent via long-poll (at-least-once).

    The bytes live under ``config.PRINT_SPOOL_DIR`` at ``payload_path``; only this
    metadata + status lives in Postgres. ``created_by`` (AuditMixin) is the staff
    user who requested the print.
    """

    __tablename__ = "print_jobs"
    __table_args__ = (
        # The agent's claim filters ``branch_id = ? AND status = 'pending'`` (and
        # the sweeps filter by status); the composite serves both, and branch-only
        # lookups via its leftmost column.
        Index("ix_print_jobs_branch_status", "branch_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE")
    )
    # The agent that claimed the job (NULL while pending). SET NULL so removing an
    # agent doesn't delete its job history.
    agent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("print_agents.id", ondelete="SET NULL"), nullable=True
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    # Label jobs only: the placed piece the label describes. SET NULL — the payload
    # is already rendered, so the job survives the piece being removed.
    placed_piece_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("order_placed_pieces.id", ondelete="SET NULL"), nullable=True
    )
    job_type: Mapped[str] = mapped_column(String(16))
    payload_format: Mapped[str] = mapped_column(String(8))
    payload_path: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(16), default=PrintJobStatus.pending.value
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    done_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # TTL: an unclaimed job past this instant expires (won't print stale).
    expires_at: Mapped[datetime] = mapped_column(DateTime)

    agent: Mapped[Optional["PrintAgentModel"]] = relationship("PrintAgentModel")
