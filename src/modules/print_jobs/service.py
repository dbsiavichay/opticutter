"""Print-job lifecycle: enqueue (user), claim via long-poll (agent), ack.

The queue lives entirely in Postgres (``PrintJobModel``), so it needs no
WebSocket, Redis pub/sub or Celery and works across uvicorn workers unchanged.
Delivery is *at least once*: a claimed job that isn't acked within the visibility
timeout is re-queued, and the TTL expires jobs no agent ever claimed.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from fastapi import Depends
from sqlalchemy.orm import Session

from src.modules.branches.model import BranchModel
from src.modules.branches.service import branch_letterhead
from src.modules.optimizations.carrier import ProformaCarrier
from src.modules.optimizations.proforma import (
    ProformaService,
    attachment_to_pdf_part,
    merge_pdfs,
)
from src.modules.orders import attachment_storage
from src.modules.orders.attachment_service import AttachmentService
from src.modules.orders.model import OrderModel, OrderPlacedPieceModel
from src.modules.print_jobs import label as label_renderer
from src.modules.print_jobs import spool
from src.modules.print_jobs.model import (
    PrintAgentModel,
    PrintJobModel,
    PrintJobStatus,
    PrintJobType,
    PrintPayloadFormat,
)
from src.modules.settings.service import SettingsService
from src.shared.config import config
from src.shared.database import get_db
from src.shared.exceptions import EntityNotFoundError, ValidationError
from src.shared.security import generate_refresh_token, hash_token

log = logging.getLogger(__name__)

# Monotonic timestamp of the last on-disk spool backstop, throttling the directory
# walk that runs on every long-poll (see ``_sweep_spool_disk``). Process-local: with
# N uvicorn workers the backstop runs up to N times per interval, which is harmless
# because ``spool.sweep_stale`` is idempotent.
_last_disk_sweep = 0.0


class PrintJobService:
    """Renders payloads, spools them to disk and manages the delivery queue."""

    def __init__(self, db: Session):
        self.db = db

    # --- scoping -----------------------------------------------------------
    def _order_scoped(self, order_id: int, branch_scope: Optional[int]) -> OrderModel:
        """Order by id, verifying branch ownership. Cross-branch → uniform 404."""
        order = self.db.get(OrderModel, order_id)
        if order is None or (
            branch_scope is not None and order.branch_id != branch_scope
        ):
            raise EntityNotFoundError("Order", order_id)
        return order

    # --- enqueue (user side) -----------------------------------------------
    def enqueue_label(
        self,
        order_id: int,
        piece_id: int,
        created_by: Optional[int],
        branch_scope: Optional[int],
    ) -> PrintJobModel:
        """Renders a piece's label to TSPL and queues it for the branch's agent."""
        order = self._order_scoped(order_id, branch_scope)
        piece = self.db.get(OrderPlacedPieceModel, piece_id)
        if piece is None or piece.order_id != order.id:
            raise EntityNotFoundError("OrderPlacedPiece", piece_id)
        payload = label_renderer.render_label(
            label_renderer.build_label_data(order, piece)
        )
        return self._spool_and_create(
            order=order,
            job_type=PrintJobType.label,
            payload_format=PrintPayloadFormat.tspl,
            payload=payload,
            created_by=created_by,
            placed_piece_id=piece.id,
        )

    def enqueue_consolidated(
        self, order_id: int, created_by: Optional[int], branch_scope: Optional[int]
    ) -> PrintJobModel:
        """Renders the consolidated PDF packet and queues it for the branch's agent."""
        order = self._order_scoped(order_id, branch_scope)
        payload = self._render_consolidated(order, branch_scope)
        return self._spool_and_create(
            order=order,
            job_type=PrintJobType.sheet,
            payload_format=PrintPayloadFormat.pdf,
            payload=payload,
            created_by=created_by,
        )

    def _render_consolidated(
        self, order: OrderModel, branch_scope: Optional[int]
    ) -> bytes:
        """Same packet as ``GET /orders/{id}/consolidated``, as raw PDF bytes.

        Order document (no diagram) + cut diagram + dispatch sheet + attachments,
        merged into one PDF.
        """
        carrier = ProformaCarrier.from_order(
            order,
            company=SettingsService(self.db).get_company(),
            branch=branch_letterhead(self.db, order.branch_id),
        )
        parts = [
            ProformaService.generate_proforma_pdf(
                carrier, title="ORDEN DE PEDIDO", include_diagram=False
            ),
            ProformaService.generate_diagram_pdf(carrier),
            ProformaService.generate_dispatch_sheet_pdf(carrier),
        ]
        for att in AttachmentService(self.db).list_attachments(
            order.id, branch_scope=branch_scope
        ):
            try:
                data = attachment_storage.read(att.stored_key)
            except OSError:
                continue  # file missing on disk: skip, still print the rest
            part = attachment_to_pdf_part(data, att.content_type)
            if part is not None:
                parts.append(part)
        return merge_pdfs(parts).getvalue()

    def _spool_and_create(
        self,
        *,
        order: OrderModel,
        job_type: PrintJobType,
        payload_format: PrintPayloadFormat,
        payload: bytes,
        created_by: Optional[int],
        placed_piece_id: Optional[int] = None,
    ) -> PrintJobModel:
        key = spool.build_key(order.branch_id, payload_format.value)
        spool.save(key, payload)
        job = PrintJobModel(
            branch_id=order.branch_id,
            order_id=order.id,
            placed_piece_id=placed_piece_id,
            job_type=job_type.value,
            payload_format=payload_format.value,
            payload_path=key,
            status=PrintJobStatus.pending.value,
            attempts=0,
            created_by=created_by,
            expires_at=datetime.utcnow()
            + timedelta(minutes=config.PRINT_JOB_TTL_MINUTES),
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    # --- claim (agent side) ------------------------------------------------
    def claim_next(self, agent: PrintAgentModel) -> Optional[PrintJobModel]:
        """Long-poll for the branch's oldest pending job, or ``None`` on timeout.

        Runs the sweeps once (expire TTL-lapsed jobs, re-queue timed-out ones),
        stamps the agent's presence, then polls for a claimable job for up to
        ``PRINT_POLL_WAIT_SECONDS``. Each attempt is a short transaction, so the
        DB connection is released back to the pool between polls.
        """
        self._sweep()
        agent.last_seen_at = datetime.utcnow()
        self.db.commit()
        deadline = time.monotonic() + config.PRINT_POLL_WAIT_SECONDS
        while True:
            job = self._claim_one(agent)
            if job is not None:
                return job
            if time.monotonic() >= deadline:
                return None
            time.sleep(1.0)

    def _sweep(self) -> None:
        """Expire TTL-lapsed jobs and re-queue claimed jobs past the visibility
        timeout, reclaiming the spooled files of the jobs that expire (and, on a
        throttled schedule, any stale files the row-driven path missed)."""
        now = datetime.utcnow()
        # TTL first: a job both expired and stale-sent is expired (won't reprint).
        # Grab the paths before the bulk UPDATE, then unlink after the rows commit
        # (commit-then-delete, like orders.attachment_service.delete_attachment).
        expiring_ttl = self.db.query(PrintJobModel.payload_path).filter(
            PrintJobModel.status.in_(
                [PrintJobStatus.pending.value, PrintJobStatus.sent.value]
            ),
            PrintJobModel.expires_at < now,
        )
        expired_paths = [path for (path,) in expiring_ttl]
        self.db.query(PrintJobModel).filter(
            PrintJobModel.status.in_(
                [PrintJobStatus.pending.value, PrintJobStatus.sent.value]
            ),
            PrintJobModel.expires_at < now,
        ).update(
            {PrintJobModel.status: PrintJobStatus.expired.value},
            synchronize_session=False,
        )
        stale_before = now - timedelta(
            seconds=config.PRINT_JOB_VISIBILITY_TIMEOUT_SECONDS
        )
        self.db.query(PrintJobModel).filter(
            PrintJobModel.status == PrintJobStatus.sent.value,
            PrintJobModel.sent_at < stale_before,
        ).update(
            {
                PrintJobModel.status: PrintJobStatus.pending.value,
                PrintJobModel.agent_id: None,
            },
            synchronize_session=False,
        )
        self.db.commit()
        for path in expired_paths:
            try:
                spool.remove(path)
            except OSError:
                log.warning("No se pudo borrar el spool del job expirado (%s)", path)
        self._sweep_spool_disk()

    def _sweep_spool_disk(self) -> None:
        """Backstop: reclaim spool files with no live job, at most once per
        ``PRINT_SPOOL_SWEEP_INTERVAL_MINUTES``.

        Runs from the agent long-poll (~every 25s per branch), so a process-local
        timestamp throttles the directory walk. Anything older than the TTL (plus a
        margin) can't belong to a deliverable job, so it's safe to delete; this
        catches CASCADE-orphaned files and any backlog the row-driven path misses.
        """
        global _last_disk_sweep
        interval = config.PRINT_SPOOL_SWEEP_INTERVAL_MINUTES * 60
        now_monotonic = time.monotonic()
        if now_monotonic - _last_disk_sweep < interval:
            return
        _last_disk_sweep = now_monotonic
        removed = spool.sweep_stale(config.PRINT_SPOOL_RETENTION_MINUTES * 60)
        if removed:
            log.info("Backstop del spool eliminó %d archivo(s) obsoleto(s)", removed)

    def _claim_one(self, agent: PrintAgentModel) -> Optional[PrintJobModel]:
        """Atomically claim the oldest pending job for the agent's branch.

        ``FOR UPDATE SKIP LOCKED`` lets concurrent agents/workers each grab a
        different job without blocking. Returns the claimed job (now ``sent``) or
        ``None``, ending the transaction either way so the connection is freed.
        """
        job = (
            self.db.query(PrintJobModel)
            .filter(
                PrintJobModel.branch_id == agent.branch_id,
                PrintJobModel.status == PrintJobStatus.pending.value,
            )
            .order_by(PrintJobModel.id.asc())
            .with_for_update(skip_locked=True)
            .first()
        )
        if job is None:
            self.db.rollback()  # release the (empty) FOR UPDATE transaction
            return None
        job.status = PrintJobStatus.sent.value
        job.sent_at = datetime.utcnow()
        job.agent_id = agent.id
        job.attempts += 1
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_payload_for_agent(
        self, job_id: int, agent: PrintAgentModel
    ) -> PrintJobModel:
        """The job whose payload the agent may download (its own branch), or 404."""
        job = self.db.get(PrintJobModel, job_id)
        if job is None or job.branch_id != agent.branch_id:
            raise EntityNotFoundError("PrintJob", job_id)
        return job

    def ack(
        self,
        agent: PrintAgentModel,
        job_id: int,
        status: str,
        error: Optional[str] = None,
    ) -> PrintJobModel:
        """Records the agent's outcome for a claimed job (idempotent).

        Only a ``sent`` job transitions to ``done``/``error``; a repeated or late
        ack (job already terminal or re-queued) is a no-op. The spooled payload is
        reclaimed on a terminal result.
        """
        if status not in (PrintJobStatus.done.value, PrintJobStatus.error.value):
            raise ValidationError("status debe ser 'done' o 'error'")
        job = self.db.get(PrintJobModel, job_id)
        if job is None or job.branch_id != agent.branch_id:
            raise EntityNotFoundError("PrintJob", job_id)
        if job.status == PrintJobStatus.sent.value:
            job.status = status
            job.done_at = datetime.utcnow()
            job.error_message = (
                error[:512]
                if (status == PrintJobStatus.error.value and error)
                else None
            )
            self.db.commit()
            try:
                spool.remove(job.payload_path)
            except OSError:
                log.warning("No se pudo borrar el spool del job %s", job.id)
            self.db.refresh(job)
        return job

    # --- status (user feedback) --------------------------------------------
    def get_job_scoped(self, job_id: int, branch_scope: Optional[int]) -> PrintJobModel:
        job = self.db.get(PrintJobModel, job_id)
        if job is None or (branch_scope is not None and job.branch_id != branch_scope):
            raise EntityNotFoundError("PrintJob", job_id)
        return job

    # --- agent management (admin) ------------------------------------------
    def create_agent(
        self, branch_id: int, name: str, created_by: Optional[int]
    ) -> Tuple[PrintAgentModel, str]:
        """Registers an agent and returns it plus its raw token (shown only once)."""
        if self.db.get(BranchModel, branch_id) is None:
            raise EntityNotFoundError("Branch", branch_id)
        raw = generate_refresh_token()
        agent = PrintAgentModel(
            branch_id=branch_id,
            name=name,
            token_hash=hash_token(raw),
            is_active=True,
            created_by=created_by,
        )
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent, raw

    def list_agents(self) -> List[PrintAgentModel]:
        return self.db.query(PrintAgentModel).order_by(PrintAgentModel.id.asc()).all()

    def rotate_token(
        self, agent_id: int, updated_by: Optional[int]
    ) -> Tuple[PrintAgentModel, str]:
        """Issues a new token (revokes the old one), returned once."""
        agent = self.db.get(PrintAgentModel, agent_id)
        if agent is None:
            raise EntityNotFoundError("PrintAgent", agent_id)
        raw = generate_refresh_token()
        agent.token_hash = hash_token(raw)
        agent.updated_by = updated_by
        self.db.commit()
        self.db.refresh(agent)
        return agent, raw

    def set_agent_active(
        self, agent_id: int, is_active: bool, updated_by: Optional[int]
    ) -> PrintAgentModel:
        agent = self.db.get(PrintAgentModel, agent_id)
        if agent is None:
            raise EntityNotFoundError("PrintAgent", agent_id)
        agent.is_active = is_active
        agent.updated_by = updated_by
        self.db.commit()
        self.db.refresh(agent)
        return agent


def print_job_service(db: Session = Depends(get_db)) -> PrintJobService:
    """``PrintJobService`` provider for route injection."""
    return PrintJobService(db)
