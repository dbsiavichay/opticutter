"""Tests del flujo de revisión del cliente sobre pre-órdenes (enlace seguro).

El enlace y la confirmación viven en la pre-orden (mutable); confirmar mintea la
Orden inmutable y la enlaza. Cubre la criptografía del enlace, los endpoints
públicos token-gated y la creación idempotente de la orden.
"""

from datetime import datetime, timedelta

from src.modules.orders.model import OrderModel
from src.modules.preorders.model import PreOrderModel
from src.shared.config import config

from .test_orders import _create_board, _create_client, _order_payload


def _create_preorder(client, c, b, **kwargs):
    return client.post(
        "/api/v1/preorders/", json=_order_payload(c["id"], b["id"], **kwargs)
    ).json()["data"]


def _setup_preorder(client, **kwargs):
    c = _create_client(client)
    b = _create_board(client)
    return _create_preorder(client, c, b, **kwargs)


def _generate_link(client, preorder_id):
    resp = client.post(f"/api/v1/preorders/{preorder_id}/review-link")
    assert resp.status_code == 201
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# Generación del enlace de revisión
# ---------------------------------------------------------------------------


def test_generate_link_marks_sent_and_returns_token(client, monkeypatch):
    monkeypatch.setattr(config, "FRONTEND_BASE_URL", "https://maderable.ec")
    pre = _setup_preorder(client)
    link = _generate_link(client, pre["id"])

    assert link["status"] == "active"
    assert len(link["token"]) >= 40
    assert link["url"] == f"https://maderable.ec/review/{link['token']}"
    assert link["expiresAt"] is not None

    fetched = client.get(f"/api/v1/preorders/{pre['id']}").json()["data"]
    assert fetched["status"] == "sent"
    assert fetched["sentAt"] is not None

    info = client.get(f"/api/v1/preorders/{pre['id']}/review-link")
    assert info.status_code == 200
    body = info.json()["data"]
    assert body["status"] == "active"
    assert "token" not in body
    assert link["token"] not in info.text


def test_generate_link_requires_phone(client):
    c = client.post(
        "/api/v1/clients/",
        json={"identifier": "sin-celular", "firstName": "Sin", "lastName": "Celular"},
    ).json()["data"]
    b = _create_board(client)
    pre = client.post(
        "/api/v1/preorders/", json=_order_payload(c["id"], b["id"])
    ).json()["data"]

    resp = client.post(f"/api/v1/preorders/{pre['id']}/review-link")
    assert resp.status_code == 422
    assert "celular" in resp.json()["errors"][0]["message"]


def test_generate_link_requires_open_status(client):
    pre = _setup_preorder(client)
    link = _generate_link(client, pre["id"])
    client.post(f"/api/v1/public/review/{link['token']}/confirm")

    resp = client.post(f"/api/v1/preorders/{pre['id']}/review-link")
    assert resp.status_code == 422
    assert "abierta" in resp.json()["errors"][0]["message"]


def test_link_endpoints_404(client):
    assert client.post("/api/v1/preorders/999999/review-link").status_code == 404
    assert client.get("/api/v1/preorders/999999/review-link").status_code == 404
    pre = _setup_preorder(client)
    assert client.get(f"/api/v1/preorders/{pre['id']}/review-link").status_code == 404


def test_regenerate_revokes_previous_link(client):
    pre = _setup_preorder(client)
    first = _generate_link(client, pre["id"])
    second = _generate_link(client, pre["id"])

    assert client.get(f"/api/v1/public/review/{first['token']}").status_code == 404
    assert client.get(f"/api/v1/public/review/{second['token']}").status_code == 200


# ---------------------------------------------------------------------------
# Endpoints públicos (token como credencial)
# ---------------------------------------------------------------------------


def test_public_review_detail_is_sanitized(client):
    pre = _setup_preorder(client)
    link = _generate_link(client, pre["id"])

    resp = client.get(f"/api/v1/public/review/{link['token']}")
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["reference"] == pre["code"]
    assert data["status"] == "sent"
    assert data["orderCode"] is None
    assert data["clientName"] == "Ada Lovelace"
    assert data["total"] == pre["optimization"]["totalBoardsCost"]
    assert len(data["lines"]) == 1
    assert data["lines"][0]["productCode"] == "MEL18"
    assert len(data["pieces"]) == 1
    assert data["pieces"][0]["height"] == 800

    # Sanitización: nada de contacto, identificadores internos ni inputs crudos.
    assert "0991112233" not in resp.text
    for leaked in ("identifier", "phone", "email", "clientId", "materials"):
        assert leaked not in data


def test_public_review_unknown_token_404(client):
    resp = client.get("/api/v1/public/review/un-token-que-no-existe")
    assert resp.status_code == 404
    assert resp.json()["errors"][0]["message"] == "Enlace de revisión no válido"


def test_confirm_creates_immutable_order(client):
    pre = _setup_preorder(client)
    link = _generate_link(client, pre["id"])

    resp = client.post(f"/api/v1/public/review/{link['token']}/confirm")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "confirmed"
    assert data["orderCode"] and data["orderCode"].startswith("ORD-")

    pre_after = client.get(f"/api/v1/preorders/{pre['id']}").json()["data"]
    assert pre_after["status"] == "confirmed"
    assert pre_after["confirmedAt"] is not None
    assert pre_after["orderId"] is not None

    order = client.get(f"/api/v1/orders/{pre_after['orderId']}").json()["data"]
    assert order["status"] == "confirmed"
    assert order["code"] == data["orderCode"]

    info = client.get(f"/api/v1/preorders/{pre['id']}/review-link").json()["data"]
    assert info["status"] == "used"
    assert info["usedAt"] is not None


def test_confirm_inherits_preorder_strategy(client, db_session):
    """Al confirmar, la orden hereda y congela la estrategia de la pre-orden."""
    pre = _setup_preorder(client, strategy="longOffcuts")
    assert pre["strategy"] == "longOffcuts"
    link = _generate_link(client, pre["id"])

    resp = client.post(f"/api/v1/public/review/{link['token']}/confirm")
    assert resp.status_code == 200

    order_id = client.get(f"/api/v1/preorders/{pre['id']}").json()["data"]["orderId"]
    db_session.expire_all()
    order = db_session.get(OrderModel, order_id)
    assert order.optimization_snapshot["strategy"] == "longOffcuts"


def test_reconfirm_is_benign_and_does_not_duplicate_order(client):
    pre = _setup_preorder(client)
    link = _generate_link(client, pre["id"])
    first = client.post(f"/api/v1/public/review/{link['token']}/confirm").json()["data"]

    again = client.post(f"/api/v1/public/review/{link['token']}/confirm")
    assert again.status_code == 200
    assert again.json()["data"]["orderCode"] == first["orderCode"]

    # No se creó una segunda orden para el cliente.
    orders = client.get("/api/v1/orders/").json()
    assert orders["meta"]["pagination"]["total"] == 1


def test_reject_via_token(client):
    pre = _setup_preorder(client)
    link = _generate_link(client, pre["id"])

    resp = client.post(
        f"/api/v1/public/review/{link['token']}/reject", json={"note": "Muy caro"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "rejected"

    # Rechazo repetido: benigno.
    assert (
        client.post(f"/api/v1/public/review/{link['token']}/reject").status_code == 200
    )


def test_reject_after_confirm_conflicts(client):
    pre = _setup_preorder(client)
    link = _generate_link(client, pre["id"])
    client.post(f"/api/v1/public/review/{link['token']}/confirm")

    resp = client.post(f"/api/v1/public/review/{link['token']}/reject")
    assert resp.status_code == 409
    assert "ventas" in resp.json()["errors"][0]["message"]


# ---------------------------------------------------------------------------
# Solicitar cambios (lazo de edición sin descartar la cotización)
# ---------------------------------------------------------------------------


def test_request_changes_keeps_link_alive_and_records_note(client):
    pre = _setup_preorder(client)
    link = _generate_link(client, pre["id"])

    resp = client.post(
        f"/api/v1/public/review/{link['token']}/request-changes",
        json={"note": "Cámbiame el alto a 450"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "changes_requested"
    assert data["clientNote"] == "Cámbiame el alto a 450"

    # El enlace sigue vivo: el cliente puede volver a abrirlo.
    again = client.get(f"/api/v1/public/review/{link['token']}")
    assert again.status_code == 200
    assert again.json()["data"]["status"] == "changes_requested"

    # El taller ve la solicitud en el detalle interno.
    detail = client.get(f"/api/v1/preorders/{pre['id']}").json()["data"]
    assert detail["status"] == "changes_requested"
    assert detail["clientNote"] == "Cámbiame el alto a 450"


def test_shop_edit_after_request_returns_to_sent_and_clears_note(client):
    pre = _setup_preorder(client)
    link = _generate_link(client, pre["id"])
    client.post(
        f"/api/v1/public/review/{link['token']}/request-changes",
        json={"note": "Otra medida"},
    )

    edited = client.put(
        f"/api/v1/preorders/{pre['id']}",
        json={
            "requirements": [
                {
                    "priority": 0,
                    "height": 450,
                    "width": 600,
                    "quantity": 2,
                    "materialKey": "b1",
                    "label": "Puerta",
                    "canRotate": True,
                }
            ]
        },
    )
    assert edited.status_code == 200
    data = edited.json()["data"]
    assert data["status"] == "sent"
    assert data["clientNote"] is None

    # El mismo enlace muestra la versión editada (precios/medidas vivos).
    review = client.get(f"/api/v1/public/review/{link['token']}").json()["data"]
    assert review["status"] == "sent"
    assert review["pieces"][0]["height"] == 450


def test_confirm_after_request_changes(client):
    pre = _setup_preorder(client)
    link = _generate_link(client, pre["id"])
    client.post(f"/api/v1/public/review/{link['token']}/request-changes")

    resp = client.post(f"/api/v1/public/review/{link['token']}/confirm")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "confirmed"
    assert resp.json()["data"]["orderCode"].startswith("ORD-")


def test_request_changes_after_confirm_conflicts(client):
    pre = _setup_preorder(client)
    link = _generate_link(client, pre["id"])
    client.post(f"/api/v1/public/review/{link['token']}/confirm")

    resp = client.post(f"/api/v1/public/review/{link['token']}/request-changes")
    assert resp.status_code == 409
    assert "ventas" in resp.json()["errors"][0]["message"]


def test_confirm_expired_quote_fails(client, db_session):
    pre = _setup_preorder(client)
    link = _generate_link(client, pre["id"])

    db_pre = db_session.get(PreOrderModel, pre["id"])
    db_pre.expires_at = datetime.utcnow() - timedelta(days=1)
    db_session.commit()

    resp = client.post(f"/api/v1/public/review/{link['token']}/confirm")
    assert resp.status_code == 422
    assert "expiró" in resp.json()["errors"][0]["message"]

    # GET con token válido sobre cotización vencida NO es 404: página amigable.
    detail = client.get(f"/api/v1/public/review/{link['token']}")
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "expired"


def test_public_proforma_by_token(client):
    pre = _setup_preorder(client)
    link = _generate_link(client, pre["id"])

    pdf = client.get(f"/api/v1/public/review/{link['token']}/proforma")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert len(pdf.content) > 1000

    assert client.get("/api/v1/public/review/token-falso/proforma").status_code == 404


def test_confirmed_order_continues_state_machine(client):
    """Tras la confirmación del cliente, la orden sigue el flujo operativo normal."""
    pre = _setup_preorder(client)
    link = _generate_link(client, pre["id"])
    client.post(f"/api/v1/public/review/{link['token']}/confirm")
    pre_after = client.get(f"/api/v1/preorders/{pre['id']}").json()["data"]

    ok = client.patch(
        f"/api/v1/orders/{pre_after['orderId']}/status",
        json={"status": "queued", "payment": {"cashAmount": 100.0}},
    )
    assert ok.status_code == 200
    assert ok.json()["data"]["status"] == "queued"
