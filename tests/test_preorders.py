"""Tests del módulo preorders: CRUD mutable, recálculo, tope y expiración."""

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
    assert data["expiresAt"] is not None

    # Inputs crudos editables (lo que el formulario del optimizador re-renderiza).
    assert len(data["materials"]) == 1
    assert data["materials"][0]["key"] == "b1"
    assert data["materials"][0]["source"] == "catalog"
    assert data["materials"][0]["productId"] == b["id"]
    assert len(data["requirements"]) == 1
    assert data["requirements"][0]["materialKey"] == "b1"
    assert data["requirements"][0]["height"] == 400

    # Optimización recalculada embebida (precios vivos, nada congelado).
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

    # Vence la pre-orden: al leerla se marca 'expired' y ya no se puede editar.
    db_pre = db_session.get(PreOrderModel, pre["id"])
    db_pre.expires_at = datetime.utcnow() - timedelta(days=1)
    db_session.commit()

    resp = client.put(f"/api/v1/preorders/{pre['id']}", json={"notes": "x"})
    assert resp.status_code == 422
    assert "ya no puede editarse" in resp.json()["errors"][0]["message"]


def test_open_cap_enforced(client):
    # El tope se lee de settings (no de env): bajarlo a 2 vía la API de configuración.
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
    # El resumen liviano no trae la optimización completa.
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
