"""Tests del flujo de revisión del cliente: cotización, enlace seguro y públicos."""

from datetime import datetime, timedelta

from src.modules.orders.model import OrderModel
from src.shared.config import config

from .test_orders import _create_board, _create_client, _order_payload


def _quoted_payload(client_id, product_id, **kwargs):
    payload = _order_payload(client_id, product_id, **kwargs)
    payload["status"] = "quoted"
    return payload


def _create_quoted_order(client, **kwargs):
    c = _create_client(client)
    b = _create_board(client)
    order = client.post(
        "/api/v1/orders/", json=_quoted_payload(c["id"], b["id"], **kwargs)
    ).json()["data"]
    return order


def _generate_link(client, order_id):
    resp = client.post(f"/api/v1/orders/{order_id}/review-link")
    assert resp.status_code == 201
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# Ciclo de vida de la cotización (orden nacida en quoted)
# ---------------------------------------------------------------------------


def test_create_quoted_order(client):
    order = _create_quoted_order(client)

    assert order["status"] == "quoted"
    assert order["confirmedAt"] is None
    assert order["expiresAt"] is not None
    assert order["code"].startswith("ORD-")
    # Historial inicial: creación de la cotización por ventas.
    assert order["history"][0]["fromStatus"] is None
    assert order["history"][0]["toStatus"] == "quoted"
    assert order["history"][0]["actor"] == "sales"


def test_create_order_default_status_remains_confirmed(client):
    """Retrocompatibilidad: sin ``status`` la orden nace confirmed (flujo bot)."""
    c = _create_client(client)
    b = _create_board(client)
    order = client.post(
        "/api/v1/orders/", json=_order_payload(c["id"], b["id"])
    ).json()["data"]
    assert order["status"] == "confirmed"
    assert order["confirmedAt"] is not None


def test_quoted_order_expires_lazily(client, monkeypatch):
    monkeypatch.setattr(config, "ORDER_VALIDITY_DAYS", -1)
    order = _create_quoted_order(client)
    fetched = client.get(f"/api/v1/orders/{order['id']}").json()["data"]
    assert fetched["status"] == "expired"
    assert fetched["history"][-1]["fromStatus"] == "quoted"


def test_quoted_order_counts_towards_pending_cap(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_PENDING_ORDERS_PER_CLIENT", 1)
    c = _create_client(client)
    b = _create_board(client)
    assert (
        client.post(
            "/api/v1/orders/", json=_quoted_payload(c["id"], b["id"], width=600)
        ).status_code
        == 201
    )
    blocked = client.post(
        "/api/v1/orders/", json=_quoted_payload(c["id"], b["id"], width=500)
    )
    assert blocked.status_code == 422
    assert "pendiente" in blocked.json()["errors"][0]["message"]


# ---------------------------------------------------------------------------
# Generación del enlace de revisión
# ---------------------------------------------------------------------------


def test_generate_review_link(client, monkeypatch):
    monkeypatch.setattr(config, "FRONTEND_BASE_URL", "https://maderable.ec")
    order = _create_quoted_order(client)
    link = _generate_link(client, order["id"])

    assert link["status"] == "active"
    assert len(link["token"]) >= 40
    assert link["url"] == f"https://maderable.ec/review/{link['token']}"
    assert link["expiresAt"] is not None

    # GET de metadatos no expone el token.
    info = client.get(f"/api/v1/orders/{order['id']}/review-link")
    assert info.status_code == 200
    body = info.json()["data"]
    assert body["status"] == "active"
    assert "token" not in body
    assert link["token"] not in info.text


def test_review_link_url_supports_hash_router_base(client, monkeypatch):
    """El dashboard usa HashRouter: una base terminada en ``/#`` (con o sin
    slash final) compone ``{base}/review/{token}`` sin romper el fragmento."""
    monkeypatch.setattr(config, "FRONTEND_BASE_URL", "https://maderable.ec/#/")
    order = _create_quoted_order(client)
    link = _generate_link(client, order["id"])
    assert link["url"] == f"https://maderable.ec/#/review/{link['token']}"


def test_generate_review_link_requires_quoted_status(client):
    c = _create_client(client)
    b = _create_board(client)
    confirmed = client.post(
        "/api/v1/orders/", json=_order_payload(c["id"], b["id"])
    ).json()["data"]

    resp = client.post(f"/api/v1/orders/{confirmed['id']}/review-link")
    assert resp.status_code == 422
    assert "quoted" in resp.json()["errors"][0]["message"]


def test_review_link_endpoints_404(client):
    assert client.post("/api/v1/orders/999999/review-link").status_code == 404
    assert client.get("/api/v1/orders/999999/review-link").status_code == 404
    # Orden sin enlace generado aún.
    order = _create_quoted_order(client)
    assert client.get(f"/api/v1/orders/{order['id']}/review-link").status_code == 404


def test_regenerate_revokes_previous_link(client):
    order = _create_quoted_order(client)
    first = _generate_link(client, order["id"])
    second = _generate_link(client, order["id"])

    # El token anterior queda revocado → 404 uniforme.
    old = client.get(f"/api/v1/public/review/{first['token']}")
    assert old.status_code == 404
    # El nuevo funciona.
    fresh = client.get(f"/api/v1/public/review/{second['token']}")
    assert fresh.status_code == 200


# ---------------------------------------------------------------------------
# Endpoints públicos (token como credencial)
# ---------------------------------------------------------------------------


def test_public_review_detail_is_sanitized(client):
    order = _create_quoted_order(client)
    link = _generate_link(client, order["id"])

    resp = client.get(f"/api/v1/public/review/{link['token']}")
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["orderCode"] == order["code"]
    assert data["status"] == "quoted"
    assert data["clientName"] == "Ada Lovelace"
    assert data["total"] == order["total"]
    assert len(data["lines"]) == 1
    assert data["lines"][0]["productCode"] == "MEL18"
    assert len(data["pieces"]) == 1
    assert data["pieces"][0]["height"] == 400

    # Sanitización: nada de contacto, identificadores internos ni snapshot.
    body = resp.text
    assert "0991112233" not in body  # identifier/phone del cliente
    for leaked in ("identifier", "phone", "email", "optimizationHash", "history"):
        assert leaked not in data


def test_public_review_unknown_token_404(client):
    resp = client.get("/api/v1/public/review/un-token-que-no-existe")
    assert resp.status_code == 404
    assert resp.json()["errors"][0]["message"] == "Enlace de revisión no válido"


def test_confirm_via_token(client):
    order = _create_quoted_order(client)
    link = _generate_link(client, order["id"])

    resp = client.post(f"/api/v1/public/review/{link['token']}/confirm")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "confirmed"
    assert data["confirmedAt"] is not None

    # Historial: la transición la hizo el cliente; el enlace quedó usado.
    fetched = client.get(f"/api/v1/orders/{order['id']}").json()["data"]
    assert fetched["history"][-1]["actor"] == "client"
    assert fetched["history"][-1]["toStatus"] == "confirmed"
    info = client.get(f"/api/v1/orders/{order['id']}/review-link").json()["data"]
    assert info["status"] == "used"
    assert info["usedAt"] is not None


def test_confirm_extends_validity(client):
    order = _create_quoted_order(client)
    link = _generate_link(client, order["id"])
    confirmed = client.post(f"/api/v1/public/review/{link['token']}/confirm").json()[
        "data"
    ]
    # La vigencia corre desde la confirmación (≥ que la de la cotización).
    assert confirmed["expiresAt"] >= order["expiresAt"]


def test_reconfirm_is_benign(client):
    order = _create_quoted_order(client)
    link = _generate_link(client, order["id"])
    client.post(f"/api/v1/public/review/{link['token']}/confirm")

    again = client.post(f"/api/v1/public/review/{link['token']}/confirm")
    assert again.status_code == 200
    assert again.json()["data"]["status"] == "confirmed"

    # Sin doble transición en el historial.
    fetched = client.get(f"/api/v1/orders/{order['id']}").json()["data"]
    confirms = [h for h in fetched["history"] if h["toStatus"] == "confirmed"]
    assert len(confirms) == 1


def test_reject_via_token(client):
    order = _create_quoted_order(client)
    link = _generate_link(client, order["id"])

    resp = client.post(
        f"/api/v1/public/review/{link['token']}/reject",
        json={"note": "Muy caro"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "cancelled"

    fetched = client.get(f"/api/v1/orders/{order['id']}").json()["data"]
    assert fetched["history"][-1]["actor"] == "client"
    assert fetched["history"][-1]["note"] == "Muy caro"

    # Rechazo repetido: benigno.
    again = client.post(f"/api/v1/public/review/{link['token']}/reject")
    assert again.status_code == 200


def test_reject_after_confirm_conflicts(client):
    order = _create_quoted_order(client)
    link = _generate_link(client, order["id"])
    client.post(f"/api/v1/public/review/{link['token']}/confirm")

    resp = client.post(f"/api/v1/public/review/{link['token']}/reject")
    assert resp.status_code == 409
    assert "ventas" in resp.json()["errors"][0]["message"]


def test_confirm_expired_quote_fails(client, db_session):
    order = _create_quoted_order(client)
    link = _generate_link(client, order["id"])

    # Vence la cotización: el enlace se generó cuando aún estaba vigente.
    db_order = db_session.get(OrderModel, order["id"])
    db_order.expires_at = datetime.utcnow() - timedelta(days=1)
    db_session.commit()

    resp = client.post(f"/api/v1/public/review/{link['token']}/confirm")
    assert resp.status_code == 422
    assert "expiró" in resp.json()["errors"][0]["message"]
    # GET con token válido sobre cotización vencida NO es 404: página amigable.
    detail = client.get(f"/api/v1/public/review/{link['token']}")
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "expired"


def test_confirm_cancelled_quote_fails(client):
    order = _create_quoted_order(client)
    link = _generate_link(client, order["id"])
    # Ventas retira la cotización.
    client.patch(f"/api/v1/orders/{order['id']}/status", json={"status": "cancelled"})

    resp = client.post(f"/api/v1/public/review/{link['token']}/confirm")
    assert resp.status_code == 422
    assert "retirada" in resp.json()["errors"][0]["message"]


def test_public_proforma_by_token(client):
    order = _create_quoted_order(client)
    link = _generate_link(client, order["id"])

    pdf = client.get(f"/api/v1/public/review/{link['token']}/proforma")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert len(pdf.content) > 1000

    assert client.get("/api/v1/public/review/token-falso/proforma").status_code == 404


def test_confirmed_order_continues_existing_state_machine(client):
    """Tras la confirmación del cliente, la orden sigue el flujo operativo normal."""
    order = _create_quoted_order(client)
    link = _generate_link(client, order["id"])
    client.post(f"/api/v1/public/review/{link['token']}/confirm")

    ok = client.patch(
        f"/api/v1/orders/{order['id']}/status", json={"status": "approved"}
    )
    assert ok.status_code == 200
    assert ok.json()["data"]["status"] == "approved"
