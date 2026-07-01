"""Tests for the preorders module: mutable CRUD, recompute, cap, and expiration."""

from datetime import datetime, timedelta

from src.modules.preorders.model import PreOrderModel

from .test_orders import _create_board, _create_client, _order_payload


def _setup(client):
    return _create_client(client), _create_board(client)


def _create_preorder(client, c, b, **kwargs):
    return client.post(
        "/api/v1/preorders/", json=_order_payload(c["id"], b["id"], **kwargs)
    )


def test_create_preorder_is_draft_with_live_optimization(client):
    c, b = _setup(client)
    resp = _create_preorder(client, c, b)
    assert resp.status_code == 201
    data = resp.json()["data"]

    assert data["status"] == "draft"
    assert data["code"].startswith("PRE-")
    assert data["orderId"] is None
    assert data["client"]["id"] == c["id"]
    # The pre-order exposes its owning branch (compact reference).
    assert data["branch"]["id"] == 1
    assert data["branch"]["code"] == "MATRIZ"
    assert data["expiresAt"] is not None

    # Raw editable inputs (what the optimizer form re-renders).
    assert len(data["materials"]) == 1
    assert data["materials"][0]["key"] == "b1"
    assert data["materials"][0]["source"] == "catalog"
    assert data["materials"][0]["productId"] == b["id"]
    assert len(data["requirements"]) == 1
    assert data["requirements"][0]["materialKey"] == "b1"
    assert data["requirements"][0]["height"] == 800

    # Embedded recomputed optimization (live prices, nothing frozen).
    opt = data["optimization"]
    assert opt["totalBoardsUsed"] >= 1
    assert len(opt["materialsSummary"]) == 1
    assert opt["materialsSummary"][0]["productCode"] == "MEL18"


def test_update_preorder_recomputes_totals(client):
    c, b = _setup(client)
    pre = _create_preorder(client, c, b, quantity=2).json()["data"]
    boards_before = pre["optimization"]["totalBoardsUsed"]

    upd = client.put(
        f"/api/v1/preorders/{pre['id']}",
        json={
            "requirements": [
                {
                    "priority": 0,
                    "height": 400,
                    "width": 600,
                    "quantity": 40,
                    "materialKey": "b1",
                    "label": "Puerta",
                    "canRotate": True,
                }
            ]
        },
    )
    assert upd.status_code == 200
    assert upd.json()["data"]["optimization"]["totalBoardsUsed"] > boards_before


def test_update_blocked_when_not_open(client, db_session):
    c, b = _setup(client)
    pre = _create_preorder(client, c, b).json()["data"]

    # Expire the pre-order: reading it marks it 'expired' and it can no longer be edited.
    db_pre = db_session.get(PreOrderModel, pre["id"])
    db_pre.expires_at = datetime.utcnow() - timedelta(days=1)
    db_session.commit()

    resp = client.put(f"/api/v1/preorders/{pre['id']}", json={"notes": "x"})
    assert resp.status_code == 422
    assert "ya no puede editarse" in resp.json()["errors"][0]["message"]


def test_open_cap_enforced(client):
    # The cap is read from settings (not env): lower it to 2 via the settings API.
    patched = client.patch(
        "/api/v1/settings/preorders", json={"maxOpenPreordersPerClient": 2}
    )
    assert patched.status_code == 200
    c, b = _setup(client)
    assert _create_preorder(client, c, b, width=600).status_code == 201
    assert _create_preorder(client, c, b, width=500).status_code == 201

    blocked = _create_preorder(client, c, b, width=400)
    assert blocked.status_code == 422
    assert "abierta" in blocked.json()["errors"][0]["message"]


def test_list_filter_and_summary_omits_optimization(client):
    c, b = _setup(client)
    _create_preorder(client, c, b)
    listed = client.get("/api/v1/preorders/?status=draft").json()
    assert listed["meta"]["pagination"]["total"] >= 1
    assert all(item["status"] == "draft" for item in listed["data"])
    # The lightweight summary doesn't include the full optimization.
    assert "optimization" not in listed["data"][0]


def test_delete_preorder(client):
    c, b = _setup(client)
    pre = _create_preorder(client, c, b).json()["data"]
    assert client.delete(f"/api/v1/preorders/{pre['id']}").status_code == 204
    assert client.get(f"/api/v1/preorders/{pre['id']}").status_code == 404


def test_create_preorder_unknown_client_404(client):
    _, b = _setup(client)
    resp = client.post("/api/v1/preorders/", json=_order_payload(999999, b["id"]))
    assert resp.status_code == 404


def test_preorder_proforma_pdf(client):
    c, b = _setup(client)
    pre = _create_preorder(client, c, b).json()["data"]
    pdf = client.get(f"/api/v1/preorders/{pre['id']}/proforma")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert len(pdf.content) > 1000


def test_preorder_persists_strategy_and_recomputes_with_it(client):
    """The strategy is saved and the recompute (cache-first) uses it on every read."""
    c, b = _setup(client)
    data = _create_preorder(client, c, b, strategy="longOffcuts").json()["data"]
    assert data["strategy"] == "longOffcuts"
    assert data["optimization"]["strategy"] == "longOffcuts"

    # Re-reading the pre-order recomputes again and keeps the strategy.
    reread = client.get(f"/api/v1/preorders/{data['id']}").json()["data"]
    assert reread["strategy"] == "longOffcuts"
    assert reread["optimization"]["strategy"] == "longOffcuts"

    # Omitting the strategy falls back to the default behavior.
    other = _create_preorder(client, c, b, width=500).json()["data"]
    assert other["strategy"] == "default"
    assert other["optimization"]["strategy"] == "default"


def test_update_preorder_changes_strategy(client):
    c, b = _setup(client)
    pre = _create_preorder(client, c, b).json()["data"]
    assert pre["strategy"] == "default"

    upd = client.put(f"/api/v1/preorders/{pre['id']}", json={"strategy": "longOffcuts"})
    assert upd.status_code == 200
    data = upd.json()["data"]
    assert data["strategy"] == "longOffcuts"
    assert data["optimization"]["strategy"] == "longOffcuts"
