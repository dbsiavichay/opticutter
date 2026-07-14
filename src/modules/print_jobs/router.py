"""Print endpoints: user-triggered enqueue + the agent's long-poll contract.

Two audiences share the ``/print`` prefix:

- **Users** (JWT): ``POST /label`` (perm ``orders:cut``) and ``POST /consolidated``
  (perm ``orders:workshop``) enqueue a job; ``GET /jobs/{id}`` is optional UI
  feedback. They go through the uniform ``{data, meta}`` envelope.
- **The agent** (device token, ``get_current_agent``): ``GET /jobs/next`` long-poll,
  ``GET /jobs/{id}/payload`` raw bytes, ``POST /jobs/{id}/ack``. These are
  machine-to-machine and, like the PDF routes, are exempt from the JSON envelope —
  ``/jobs/next`` returns the snake_case job dict the agent expects.
- **Admin**: ``/agents`` CRUD to register a branch's agent and issue its token.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse

from src.modules.print_jobs import spool
from src.modules.print_jobs.dependencies import get_current_agent
from src.modules.print_jobs.model import PrintAgentModel
from src.modules.print_jobs.schemas import (
    JobAck,
    PrintAgentActiveUpdate,
    PrintAgentCreate,
    PrintAgentOut,
    PrintAgentToken,
    PrintConsolidatedRequest,
    PrintJobCreated,
    PrintJobOut,
    PrintLabelRequest,
)
from src.modules.print_jobs.service import PrintJobService, print_job_service
from src.modules.users.dependencies import get_branch_scope, require_permission
from src.modules.users.model import UserModel
from src.shared.responses import ERROR_RESPONSES, DataResponse, ok

router = APIRouter(prefix="/print", tags=["print"], responses=ERROR_RESPONSES)


def _agent_token(agent: PrintAgentModel, token: str) -> PrintAgentToken:
    """Serializes an agent plus its freshly issued raw token (returned once)."""
    return PrintAgentToken(
        id=agent.id,
        branch_id=agent.branch_id,
        name=agent.name,
        is_active=agent.is_active,
        last_seen_at=agent.last_seen_at,
        token=token,
    )


# --------------------------------------------------------------------------- #
# User side (JWT): enqueue after the existing cut/complete flows succeed.
# --------------------------------------------------------------------------- #
@router.post("/label", response_model=DataResponse[PrintJobCreated], status_code=202)
def enqueue_label(
    body: PrintLabelRequest,
    svc: PrintJobService = Depends(print_job_service),
    current_user: UserModel = Depends(require_permission("orders:cut")),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Queues a piece's label for the branch's thermal printer (perm ``orders:cut``)."""
    job = svc.enqueue_label(
        body.order_id,
        body.piece_id,
        created_by=current_user.id,
        branch_scope=branch_scope,
    )
    return ok(PrintJobCreated(job_id=job.id, status=job.status))


@router.post(
    "/consolidated", response_model=DataResponse[PrintJobCreated], status_code=202
)
def enqueue_consolidated(
    body: PrintConsolidatedRequest,
    svc: PrintJobService = Depends(print_job_service),
    current_user: UserModel = Depends(require_permission("orders:workshop")),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Queues the consolidated PDF packet for the branch's inkjet (perm ``orders:workshop``)."""
    job = svc.enqueue_consolidated(
        body.order_id, created_by=current_user.id, branch_scope=branch_scope
    )
    return ok(PrintJobCreated(job_id=job.id, status=job.status))


# --------------------------------------------------------------------------- #
# Agent side (device token). Declared before ``/jobs/{job_id}`` so the static
# ``/jobs/next`` route is matched first. Exempt from the JSON envelope.
# --------------------------------------------------------------------------- #
@router.get("/jobs/next")
def poll_next_job(
    svc: PrintJobService = Depends(print_job_service),
    agent: PrintAgentModel = Depends(get_current_agent),
):
    """Long-poll for the next job of the agent's branch (snake_case dict) or 204."""
    job = svc.claim_next(agent)
    if job is None:
        return Response(status_code=204)
    return {
        "id": job.id,
        "job_type": job.job_type,
        "payload_format": job.payload_format,
        "payload_url": f"/api/v1/print/jobs/{job.id}/payload",
    }


@router.get("/jobs/{job_id}/payload")
def download_payload(
    job_id: int,
    svc: PrintJobService = Depends(print_job_service),
    agent: PrintAgentModel = Depends(get_current_agent),
):
    """Streams the rendered payload's raw bytes (TSPL or PDF) for the agent."""
    job = svc.get_payload_for_agent(job_id, agent)
    return StreamingResponse(
        spool.open_stream(job.payload_path),
        media_type="application/octet-stream",
    )


@router.post("/jobs/{job_id}/ack")
def ack_job(
    job_id: int,
    body: JobAck,
    svc: PrintJobService = Depends(print_job_service),
    agent: PrintAgentModel = Depends(get_current_agent),
):
    """Agent reports a job's outcome (``done``/``error``); idempotent."""
    job = svc.ack(agent, job_id, body.status, body.error)
    return {"id": job.id, "status": job.status}


# --------------------------------------------------------------------------- #
# User status feedback (optional). Broad shop-floor read, scoped by branch.
# --------------------------------------------------------------------------- #
@router.get("/jobs/{job_id}", response_model=DataResponse[PrintJobOut])
def get_job(
    job_id: int,
    svc: PrintJobService = Depends(print_job_service),
    _user: UserModel = Depends(require_permission("orders:workshop")),
    branch_scope: Optional[int] = Depends(get_branch_scope),
):
    """Job status for UI feedback (imprimiendo… / impreso / error)."""
    return ok(svc.get_job_scoped(job_id, branch_scope))


# --------------------------------------------------------------------------- #
# Agent management (admin): register a branch's agent and issue/rotate its token.
# --------------------------------------------------------------------------- #
@router.post("/agents", response_model=DataResponse[PrintAgentToken], status_code=201)
def create_agent(
    body: PrintAgentCreate,
    svc: PrintJobService = Depends(print_job_service),
    current_user: UserModel = Depends(require_permission("print:agents")),
):
    """Registers a print agent and returns its token (shown only once)."""
    agent, token = svc.create_agent(
        body.branch_id, body.name, created_by=current_user.id
    )
    return ok(_agent_token(agent, token))


@router.get("/agents", response_model=DataResponse[List[PrintAgentOut]])
def list_agents(
    svc: PrintJobService = Depends(print_job_service),
    _user: UserModel = Depends(require_permission("print:agents")),
):
    """Lists registered agents (with last-seen presence); never returns tokens."""
    return ok(svc.list_agents())


@router.post(
    "/agents/{agent_id}/rotate-token",
    response_model=DataResponse[PrintAgentToken],
)
def rotate_agent_token(
    agent_id: int,
    svc: PrintJobService = Depends(print_job_service),
    current_user: UserModel = Depends(require_permission("print:agents")),
):
    """Issues a new token for an agent (revokes the previous one)."""
    agent, token = svc.rotate_token(agent_id, updated_by=current_user.id)
    return ok(_agent_token(agent, token))


@router.patch("/agents/{agent_id}", response_model=DataResponse[PrintAgentOut])
def set_agent_active(
    agent_id: int,
    body: PrintAgentActiveUpdate,
    svc: PrintJobService = Depends(print_job_service),
    current_user: UserModel = Depends(require_permission("print:agents")),
):
    """Activates or deactivates an agent (a deactivated token stops authenticating)."""
    return ok(
        svc.set_agent_active(agent_id, body.is_active, updated_by=current_user.id)
    )
