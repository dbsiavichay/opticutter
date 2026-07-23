from datetime import datetime
from typing import Optional

from src.shared.schemas import CamelModel

# Enqueue outcome when the order's branch has that print type disabled: no job row
# and no rendered payload. Deliberately NOT a ``PrintJobStatus`` value -- there is
# no row to carry it; it only ever travels in the 202 body.
PRINT_STATUS_SKIPPED = "skipped"


class PrintLabelRequest(CamelModel):
    """Enqueue a label for a cut piece. ``piece_id`` is the placed-piece id (the
    unit the operator marks cut), same identifier as ``mark_piece_cut``."""

    order_id: int
    piece_id: int


class PrintConsolidatedRequest(CamelModel):
    """Enqueue the consolidated print packet for a completed order."""

    order_id: int


class PrintJobCreated(CamelModel):
    """202 payload: the id the frontend can poll for status feedback.

    ``jobId`` is ``null`` with ``status = "skipped"`` when the branch has that
    print type disabled -- a benign no-op, not an error, because the triggers are
    automatic side-effects (one per cut piece) and a 4xx would toast on each one.
    """

    job_id: Optional[int] = None
    status: str


class PrintJobOut(CamelModel):
    """Job status for UI feedback (imprimiendo… / impreso / error)."""

    id: int
    job_type: str
    payload_format: str
    status: str
    attempts: int
    error_message: Optional[str] = None


class PrintJobListItem(CamelModel):
    """A print job for the shop-floor panel: its real status plus enough order
    context to render the row (``order_code``/``client_name``) and re-dispatch it
    (``order_id``, and ``placed_piece_id`` for labels)."""

    id: int
    order_id: int
    order_code: Optional[str] = None
    client_name: Optional[str] = None
    job_type: str
    placed_piece_id: Optional[int] = None
    status: str
    attempts: int
    error_message: Optional[str] = None
    created_at: datetime
    done_at: Optional[datetime] = None


class JobAck(CamelModel):
    """Agent's report of a job's outcome. ``status`` is ``done`` or ``error``."""

    status: str
    error: Optional[str] = None


# --- Agent management (admin) ------------------------------------------------
class PrintAgentCreate(CamelModel):
    branch_id: int
    name: str


class PrintAgentActiveUpdate(CamelModel):
    is_active: bool


class PrintAgentOut(CamelModel):
    id: int
    branch_id: int
    name: str
    is_active: bool
    last_seen_at: Optional[datetime] = None


class PrintAgentToken(PrintAgentOut):
    """Returned only once, at creation or rotation: the raw token to configure in
    the agent's ``config.ini``. It is never retrievable again (only its hash is
    stored)."""

    token: str
