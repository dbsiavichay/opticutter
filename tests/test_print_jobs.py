"""Integration: the print-jobs queue and its delivery state machine.

Covers the service state machine (enqueue → claim marks ``sent`` → ack ``done``;
visibility-timeout re-queue; TTL expiry; branch isolation) against real
PostgreSQL, plus the full HTTP contract the agent consumes (register agent →
enqueue → long-poll → download payload → ack) and its auth.
"""

from datetime import datetime, timedelta

import pytest

from src.modules.branches.model import BranchModel
from src.modules.orders.model import OrderPlacedPieceModel
from src.modules.orders.schemas import OrderCreate
from src.modules.orders.service import OrderService
from src.modules.print_jobs import spool
from src.modules.print_jobs.model import (
    PrintAgentModel,
    PrintJobModel,
    PrintJobStatus,
)
from src.modules.print_jobs.service import PrintJobService
from src.shared.config import config
from src.shared.exceptions import ValidationError
from src.shared.security import hash_token


@pytest.fixture(autouse=True)
def _print_env(tmp_path, monkeypatch):
    """Isolate the spool on disk and don't hold the long-poll open during tests."""
    monkeypatch.setattr(config, "PRINT_SPOOL_DIR", str(tmp_path / "spool"))
    monkeypatch.setattr(config, "PRINT_POLL_WAIT_SECONDS", 0)


# --- seeding (same pattern as test_order_cutting_plan) ----------------------
def _create_client(client, identifier="0991112233"):
    return client.post(
        "/api/v1/clients/",
        json={
            "identifier": identifier,
            "firstName": "Ada",
            "lastName": "Lovelace",
            "phone": "0991112233",
        },
    ).json()["data"]


def _create_board(client, code="MEL18"):
    return client.post(
        "/api/v1/products/",
        json={
            "type": "board",
            "code": code,
            "name": f"Melamina {code}",
            "price": 45.5,
            "attributes": {"height": 2440, "width": 1220, "thickness": 18},
        },
    ).json()["data"]


def _create_order(client, db_session, branch_id=1):
    c = _create_client(client)
    b = _create_board(client)
    payload = {
        "clientId": c["id"],
        "branchId": branch_id,
        "materials": [{"key": "b1", "source": "catalog", "productId": b["id"]}],
        "requirements": [
            {
                "priority": 0,
                "height": 800,
                "width": 700,
                "quantity": 2,
                "materialKey": "b1",
                "label": "Puerta",
                "canRotate": True,
            }
        ],
    }
    return OrderService(db_session).create(OrderCreate.model_validate(payload))


def _a_piece(db_session, order_id) -> OrderPlacedPieceModel:
    return (
        db_session.query(OrderPlacedPieceModel)
        .filter(OrderPlacedPieceModel.order_id == order_id)
        .first()
    )


def _make_agent(db_session, branch_id=1, token="agent-tok", is_active=True):
    agent = PrintAgentModel(
        branch_id=branch_id,
        name=f"PC {branch_id}",
        token_hash=hash_token(token),
        is_active=is_active,
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


def _raw_job(db_session, order_id, branch_id=1, expires_in_s=600, status=None):
    job = PrintJobModel(
        branch_id=branch_id,
        order_id=order_id,
        job_type="sheet",
        payload_format="pdf",
        payload_path=f"{branch_id}/dummy.pdf",
        status=(status or PrintJobStatus.pending.value),
        attempts=0,
        expires_at=datetime.utcnow() + timedelta(seconds=expires_in_s),
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


# --- service state machine --------------------------------------------------
def test_enqueue_claim_ack_happy_path(client, db_session):
    order = _create_order(client, db_session)
    piece = _a_piece(db_session, order.id)
    svc = PrintJobService(db_session)

    job = svc.enqueue_label(order.id, piece.id, created_by=None, branch_scope=None)
    assert job.status == PrintJobStatus.pending.value
    assert job.job_type == "label" and job.payload_format == "tspl"
    assert job.placed_piece_id == piece.id
    assert spool.read(job.payload_path).startswith(b"SIZE ")  # the TSPL payload

    agent = _make_agent(db_session)
    claimed = svc.claim_next(agent)
    assert claimed is not None and claimed.id == job.id
    assert claimed.status == PrintJobStatus.sent.value
    assert claimed.agent_id == agent.id and claimed.attempts == 1
    assert claimed.sent_at is not None
    assert agent.last_seen_at is not None  # presence stamped on poll

    acked = svc.ack(agent, job.id, "done")
    assert acked.status == PrintJobStatus.done.value and acked.done_at is not None
    # Spooled payload reclaimed on a terminal result.
    with pytest.raises(OSError):
        spool.read(job.payload_path)


def test_claim_is_isolated_by_branch(client, db_session):
    order = _create_order(client, db_session)
    piece = _a_piece(db_session, order.id)
    b2 = BranchModel(code="SUR", name="Sucursal Sur", is_active=True)
    db_session.add(b2)
    db_session.commit()

    svc = PrintJobService(db_session)
    job_b1 = svc.enqueue_label(order.id, piece.id, created_by=None, branch_scope=None)
    job_b2 = _raw_job(db_session, order.id, branch_id=b2.id)

    agent_b2 = _make_agent(db_session, branch_id=b2.id, token="tok-b2")
    claimed_b2 = svc.claim_next(agent_b2)
    assert claimed_b2 is not None and claimed_b2.id == job_b2.id

    agent_b1 = _make_agent(db_session, branch_id=1, token="tok-b1")
    claimed_b1 = svc.claim_next(agent_b1)
    assert claimed_b1 is not None and claimed_b1.id == job_b1.id

    # Nothing left for either branch.
    assert svc.claim_next(agent_b1) is None
    assert svc.claim_next(agent_b2) is None


def test_visibility_timeout_requeues_stale_sent(client, db_session):
    order = _create_order(client, db_session)
    svc = PrintJobService(db_session)
    job = _raw_job(db_session, order.id)
    agent = _make_agent(db_session)

    claimed = svc.claim_next(agent)
    assert claimed.status == PrintJobStatus.sent.value and claimed.attempts == 1

    # Simulate the agent dying mid-print: no ack, sent_at older than the timeout.
    job.sent_at = datetime.utcnow() - timedelta(
        seconds=config.PRINT_JOB_VISIBILITY_TIMEOUT_SECONDS + 5
    )
    db_session.commit()

    reclaimed = svc.claim_next(agent)  # sweep re-queues, then re-claims it
    assert reclaimed is not None and reclaimed.id == job.id
    assert reclaimed.status == PrintJobStatus.sent.value
    assert reclaimed.attempts == 2  # delivered again (at least once)


def test_ttl_expiry_drops_unclaimed_job(client, db_session):
    order = _create_order(client, db_session)
    svc = PrintJobService(db_session)
    job = _raw_job(db_session, order.id, expires_in_s=-1)  # already past its TTL
    agent = _make_agent(db_session)

    assert svc.claim_next(agent) is None  # nothing claimable
    db_session.refresh(job)
    assert job.status == PrintJobStatus.expired.value


def test_ack_is_idempotent_and_validated(client, db_session):
    order = _create_order(client, db_session)
    svc = PrintJobService(db_session)
    job = _raw_job(db_session, order.id)
    agent = _make_agent(db_session)
    svc.claim_next(agent)

    svc.ack(agent, job.id, "done")
    # A repeated (late) ack is a no-op: the job stays done, not overwritten.
    again = svc.ack(agent, job.id, "error", "boom")
    assert again.status == PrintJobStatus.done.value
    assert again.error_message is None

    with pytest.raises(ValidationError):
        svc.ack(agent, job.id, "printed")  # not a valid outcome


def test_ack_error_records_message(client, db_session):
    order = _create_order(client, db_session)
    svc = PrintJobService(db_session)
    job = _raw_job(db_session, order.id)
    agent = _make_agent(db_session)
    svc.claim_next(agent)

    acked = svc.ack(agent, job.id, "error", "printer offline")
    assert acked.status == PrintJobStatus.error.value
    assert acked.error_message == "printer offline"


# --- HTTP contract (what the agent + admin consume) -------------------------
def _register_agent(client, branch_id=1, name="Taller"):
    resp = client.post(
        "/api/v1/print/agents", json={"branchId": branch_id, "name": name}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["token"]


def test_http_full_flow_label(client, db_session):
    order = _create_order(client, db_session)
    piece = _a_piece(db_session, order.id)
    token = _register_agent(client)
    agent_auth = {"Authorization": f"Bearer {token}"}

    # User enqueues (admin has orders:cut).
    resp = client.post(
        "/api/v1/print/label", json={"orderId": order.id, "pieceId": piece.id}
    )
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["data"]["jobId"]

    # Agent long-polls: snake_case dict the agent expects.
    nxt = client.get("/api/v1/print/jobs/next", headers=agent_auth)
    assert nxt.status_code == 200
    body = nxt.json()
    assert body["id"] == job_id and body["job_type"] == "label"
    assert body["payload_url"] == f"/api/v1/print/jobs/{job_id}/payload"

    # Agent downloads the raw TSPL payload.
    payload = client.get(body["payload_url"], headers=agent_auth)
    assert payload.status_code == 200
    assert payload.content.startswith(b"SIZE ")

    # Agent acks; the user then sees the job done.
    ack = client.post(
        f"/api/v1/print/jobs/{job_id}/ack", json={"status": "done"}, headers=agent_auth
    )
    assert ack.status_code == 200
    status = client.get(f"/api/v1/print/jobs/{job_id}").json()["data"]
    assert status["status"] == "done"


def test_http_enqueue_consolidated_renders_pdf(client, db_session):
    order = _create_order(client, db_session)
    token = _register_agent(client)
    agent_auth = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/v1/print/consolidated", json={"orderId": order.id})
    assert resp.status_code == 202, resp.text

    nxt = client.get("/api/v1/print/jobs/next", headers=agent_auth).json()
    assert nxt["job_type"] == "sheet" and nxt["payload_format"] == "pdf"
    payload = client.get(nxt["payload_url"], headers=agent_auth)
    assert payload.content.startswith(b"%PDF")  # the merged consolidated packet


def test_agent_endpoints_reject_bad_token(client, db_session):
    _create_order(client, db_session)
    # No token.
    assert client.get("/api/v1/print/jobs/next").status_code == 401
    # Inactive agent's token doesn't authenticate.
    _make_agent(db_session, token="inactive-tok", is_active=False)
    resp = client.get(
        "/api/v1/print/jobs/next",
        headers={"Authorization": "Bearer inactive-tok"},
    )
    assert resp.status_code == 401


def test_next_returns_204_when_empty(client, db_session):
    token = _register_agent(client)
    resp = client.get(
        "/api/v1/print/jobs/next", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 204


# --- admin agent management -------------------------------------------------
def test_agent_lifecycle_register_rotate_deactivate(client, db_session):
    token = _register_agent(client, name="Taller Norte")
    auth = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/print/jobs/next", headers=auth).status_code == 204

    listed = client.get("/api/v1/print/agents").json()["data"]
    assert len(listed) == 1
    agent_id = listed[0]["id"]
    assert listed[0]["name"] == "Taller Norte"
    assert "token" not in listed[0]  # the raw token is never listed

    # Rotating issues a new token and revokes the old one.
    rotated = client.post(f"/api/v1/print/agents/{agent_id}/rotate-token")
    assert rotated.status_code == 200
    new_token = rotated.json()["data"]["token"]
    assert new_token != token
    assert client.get("/api/v1/print/jobs/next", headers=auth).status_code == 401
    new_auth = {"Authorization": f"Bearer {new_token}"}
    assert client.get("/api/v1/print/jobs/next", headers=new_auth).status_code == 204

    # Deactivating stops the token from authenticating.
    off = client.patch(f"/api/v1/print/agents/{agent_id}", json={"isActive": False})
    assert off.status_code == 200 and off.json()["data"]["isActive"] is False
    assert client.get("/api/v1/print/jobs/next", headers=new_auth).status_code == 401


def test_register_agent_unknown_branch_404(client, db_session):
    resp = client.post("/api/v1/print/agents", json={"branchId": 9999, "name": "x"})
    assert resp.status_code == 404


def test_agent_management_requires_admin(client, db_session):
    """The enqueue perms don't grant agent management; only admin (print:agents)."""
    from src.modules.users.schemas import UserCreate
    from src.modules.users.service import UserService
    from src.shared.security import create_access_token

    operator = UserService(db_session).create(
        UserCreate(
            email="op-print@empresa.com",
            password="password1",
            role="operador",
            full_name="Op",
            branch_id=1,
        )
    )
    op_auth = {
        "Authorization": f"Bearer {create_access_token(operator.id, operator.role)}"
    }
    assert client.get("/api/v1/print/agents", headers=op_auth).status_code == 403


def test_enqueue_label_unknown_order_and_piece_404(client, db_session):
    order = _create_order(client, db_session)
    piece = _a_piece(db_session, order.id)
    # Unknown order.
    assert (
        client.post(
            "/api/v1/print/label", json={"orderId": 99999, "pieceId": piece.id}
        ).status_code
        == 404
    )
    # Piece that isn't part of the order.
    assert (
        client.post(
            "/api/v1/print/label", json={"orderId": order.id, "pieceId": 99999}
        ).status_code
        == 404
    )
