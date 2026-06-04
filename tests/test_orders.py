"""Tests del módulo orders: creación (snapshot), idempotencia, tope, estados."""

from datetime import datetime

from src.shared.config import config


def _create_client(client, identifier="0991112233", phone="0991112233"):
    return client.post(
        "/api/v1/clients/",
        json={
            "identifier": identifier,
            "firstName": "Ada",
            "lastName": "Lovelace",
            "phone": phone,
        },
    ).json()


def _create_board(client, code="MEL18"):
    return client.post(
        "/api/v1/boards/",
        json={
            "code": code,
            "name": f"Melamina {code}",
            "height": 2440,
            "width": 1220,
            "thickness": 18,
            "price": 45.5,
        },
    ).json()


def _order_payload(client_id, board_id, height=400, width=600, quantity=2):
    return {
        "clientId": client_id,
        "requirements": [
            {
                "priority": 0,
                "height": height,
                "width": width,
                "quantity": quantity,
                "boardId": board_id,
                "label": "Puerta",
                "canRotate": True,
            }
        ],
    }


def test_create_order_freezes_snapshot_and_charges_boards(client):
    c = _create_client(client)
    b = _create_board(client)

    resp = client.post("/api/v1/orders/", json=_order_payload(c["id"], b["id"]))
    assert resp.status_code == 201
    data = resp.json()

    assert data["status"] == "confirmed"
    assert data["code"] == f"ORD-{datetime.utcnow().year}-{data['id']:04d}"
    assert data["client"]["id"] == c["id"]
    assert len(data["optimizationHash"]) == 64

    # Cobro = tableros: una línea por tipo de tablero (desde materials_summary).
    assert len(data["lines"]) == 1
    line = data["lines"][0]
    assert line["boardCode"] == "MEL18"
    assert line["quantity"] == data["totalBoardsUsed"]
    assert line["lineTotal"] == line["quantity"] * 45.5

    # Totales inmutables = suma por tableros.
    assert data["total"] == data["subtotal"] == line["lineTotal"]

    # Lista de corte = piezas (insumo de producción, no se cobra).
    assert len(data["pieces"]) == 1
    piece = data["pieces"][0]
    assert piece["height"] == 400 and piece["width"] == 600
    assert piece["quantity"] == 2

    # Historial inicial registra la creación.
    assert data["history"][0]["toStatus"] == "confirmed"
    assert data["history"][0]["fromStatus"] is None


def test_create_order_blocked_without_client_phone(client):
    """Regla de negocio: sin celular registrado no se crea el pedido (422)."""
    b = _create_board(client)
    no_phone = client.post(
        "/api/v1/clients/",
        json={"identifier": "0990000000", "firstName": "Sin", "lastName": "Tel"},
    ).json()

    resp = client.post("/api/v1/orders/", json=_order_payload(no_phone["id"], b["id"]))
    assert resp.status_code == 422
    assert "celular" in resp.json()["detail"].lower()
    # No se persistió ninguna orden.
    assert client.get("/api/v1/orders/").json() == []


def test_create_order_unknown_client_returns_404(client):
    """Un ``clientId`` inexistente da 404 limpio antes de congelar nada."""
    b = _create_board(client)
    resp = client.post("/api/v1/orders/", json=_order_payload(99999, b["id"]))
    assert resp.status_code == 404
    assert "Client 99999" in resp.json()["detail"]


def test_create_order_is_idempotent(client):
    c = _create_client(client)
    b = _create_board(client)
    payload = _order_payload(c["id"], b["id"])

    first = client.post("/api/v1/orders/", json=payload).json()
    second = client.post("/api/v1/orders/", json=payload).json()

    assert first["id"] == second["id"]
    assert first["code"] == second["code"]
    # No se crean dos órdenes para el mismo (cliente, hash).
    assert len(client.get("/api/v1/orders/").json()) == 1


def test_pending_cap_blocks_excess_orders(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_PENDING_ORDERS_PER_CLIENT", 2)
    c = _create_client(client)
    b = _create_board(client)

    # Dos órdenes distintas (distinto hash) → ambas quedan pendientes.
    assert (
        client.post(
            "/api/v1/orders/", json=_order_payload(c["id"], b["id"], width=600)
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/orders/", json=_order_payload(c["id"], b["id"], width=500)
        ).status_code
        == 201
    )

    # La tercera excede el tope de pendientes.
    third = client.post(
        "/api/v1/orders/", json=_order_payload(c["id"], b["id"], width=450)
    )
    assert third.status_code == 422
    assert "pendiente" in third.json()["detail"]


def test_status_transitions_valid_and_invalid(client):
    c = _create_client(client)
    b = _create_board(client)
    order = client.post("/api/v1/orders/", json=_order_payload(c["id"], b["id"])).json()
    oid = order["id"]

    ok = client.patch(f"/api/v1/orders/{oid}/status", json={"status": "approved"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "approved"

    ok2 = client.patch(f"/api/v1/orders/{oid}/status", json={"status": "in_production"})
    assert ok2.status_code == 200
    assert ok2.json()["status"] == "in_production"
    # Historial acumulado: creación + 2 transiciones.
    assert len(ok2.json()["history"]) == 3

    # in_production → completed no es una transición válida.
    bad = client.patch(f"/api/v1/orders/{oid}/status", json={"status": "completed"})
    assert bad.status_code == 422
    assert "inválida" in bad.json()["detail"]


def test_invalid_transition_from_confirmed(client):
    c = _create_client(client)
    b = _create_board(client)
    order = client.post("/api/v1/orders/", json=_order_payload(c["id"], b["id"])).json()
    # confirmed → completed (salta estados) no es válido.
    bad = client.patch(
        f"/api/v1/orders/{order['id']}/status", json={"status": "completed"}
    )
    assert bad.status_code == 422


def test_list_orders_filter_by_status(client):
    c = _create_client(client)
    b = _create_board(client)
    o1 = client.post(
        "/api/v1/orders/", json=_order_payload(c["id"], b["id"], width=600)
    ).json()
    client.post("/api/v1/orders/", json=_order_payload(c["id"], b["id"], width=500))

    # Aprobar solo la primera.
    client.patch(f"/api/v1/orders/{o1['id']}/status", json={"status": "approved"})

    approved = client.get("/api/v1/orders/", params={"status": "approved"}).json()
    assert [o["id"] for o in approved] == [o1["id"]]

    confirmed = client.get("/api/v1/orders/", params={"status": "confirmed"}).json()
    assert o1["id"] not in [o["id"] for o in confirmed]
    assert len(confirmed) == 1


def test_get_order_404(client):
    assert client.get("/api/v1/orders/999999").status_code == 404


def test_order_proforma_pdf_and_base64(client):
    c = _create_client(client)
    b = _create_board(client)
    order = client.post("/api/v1/orders/", json=_order_payload(c["id"], b["id"])).json()
    oid = order["id"]

    pdf = client.get(f"/api/v1/orders/{oid}/proforma")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert len(pdf.content) > 1000

    b64 = client.get(f"/api/v1/orders/{oid}/proforma", params={"format": "base64"})
    assert b64.status_code == 200
    body = b64.json()
    assert body["format"] == "base64"
    assert body["mimeType"] == "application/pdf"
    assert order["code"] in body["filename"]


def test_order_production_sheet_pdf(client):
    c = _create_client(client)
    b = _create_board(client)
    order = client.post("/api/v1/orders/", json=_order_payload(c["id"], b["id"])).json()

    sheet = client.get(f"/api/v1/orders/{order['id']}/production-sheet")
    assert sheet.status_code == 200
    assert sheet.headers["content-type"] == "application/pdf"
    assert len(sheet.content) > 1000


def test_order_documents_404(client):
    assert client.get("/api/v1/orders/999999/proforma").status_code == 404
    assert client.get("/api/v1/orders/999999/production-sheet").status_code == 404


def test_order_export_document(client):
    c = _create_client(client)
    b = _create_board(client)
    order = client.post("/api/v1/orders/", json=_order_payload(c["id"], b["id"])).json()

    resp = client.get(f"/api/v1/orders/{order['id']}/export")
    assert resp.status_code == 200
    data = resp.json()

    assert data["orderCode"] == order["code"]
    assert data["status"] == "confirmed"
    assert data["client"]["id"] == c["id"]
    assert data["currency"] == "USD"
    assert data["issuedAt"] is not None
    assert data["externalInvoiceId"] is None

    # Cobro por tablero: una línea con descripción legible y el código.
    assert len(data["lines"]) == 1
    line = data["lines"][0]
    assert line["boardCode"] == "MEL18"
    assert "MEL18" in line["description"]
    assert line["quantity"] == order["totalBoardsUsed"]
    assert line["unitPrice"] == 45.5
    assert line["lineTotal"] == line["quantity"] * 45.5
    assert data["subtotal"] == data["total"] == line["lineTotal"]


def test_set_external_invoice_id_and_reflect_in_export(client):
    c = _create_client(client)
    b = _create_board(client)
    order = client.post("/api/v1/orders/", json=_order_payload(c["id"], b["id"])).json()
    oid = order["id"]

    resp = client.post(
        f"/api/v1/orders/{oid}/invoice", json={"externalInvoiceId": "FAC-001-42"}
    )
    assert resp.status_code == 200
    assert resp.json()["externalInvoiceId"] == "FAC-001-42"

    # Idempotente con el mismo ID.
    again = client.post(
        f"/api/v1/orders/{oid}/invoice", json={"externalInvoiceId": "FAC-001-42"}
    )
    assert again.status_code == 200

    # El export refleja la factura asociada.
    exported = client.get(f"/api/v1/orders/{oid}/export").json()
    assert exported["externalInvoiceId"] == "FAC-001-42"


def test_set_external_invoice_id_conflict_on_different_id(client):
    c = _create_client(client)
    b = _create_board(client)
    order = client.post("/api/v1/orders/", json=_order_payload(c["id"], b["id"])).json()
    oid = order["id"]

    client.post(
        f"/api/v1/orders/{oid}/invoice", json={"externalInvoiceId": "FAC-001-42"}
    )
    # Otro ID sobre una orden ya facturada → 409 (no pisa la factura emitida).
    conflict = client.post(
        f"/api/v1/orders/{oid}/invoice", json={"externalInvoiceId": "FAC-999-00"}
    )
    assert conflict.status_code == 409


def test_billing_seam_404(client):
    assert client.get("/api/v1/orders/999999/export").status_code == 404
    assert (
        client.post(
            "/api/v1/orders/999999/invoice", json={"externalInvoiceId": "X"}
        ).status_code
        == 404
    )


def test_order_expires_lazily_on_read(client, monkeypatch):
    """Una orden vencida se transiciona a ``expired`` al leerla (barrido perezoso)."""
    monkeypatch.setattr(config, "ORDER_VALIDITY_DAYS", -1)
    c = _create_client(client)
    b = _create_board(client)
    order = client.post("/api/v1/orders/", json=_order_payload(c["id"], b["id"])).json()
    # Nace confirmed, pero su vigencia ya está vencida (expiresAt en el pasado).
    assert order["status"] == "confirmed"

    fetched = client.get(f"/api/v1/orders/{order['id']}").json()
    assert fetched["status"] == "expired"
    assert fetched["history"][-1]["toStatus"] == "expired"
    assert fetched["history"][-1]["fromStatus"] == "confirmed"


def test_expired_order_frees_pending_cap(client, monkeypatch):
    """Las pendientes vencidas no cuentan para el tope: se expiran al evaluarlo."""
    monkeypatch.setattr(config, "MAX_PENDING_ORDERS_PER_CLIENT", 1)
    monkeypatch.setattr(config, "ORDER_VALIDITY_DAYS", -1)
    c = _create_client(client)
    b = _create_board(client)

    first = client.post(
        "/api/v1/orders/", json=_order_payload(c["id"], b["id"], width=600)
    )
    assert first.status_code == 201
    # La primera está vencida; la segunda (distinto hash) no choca con el tope.
    second = client.post(
        "/api/v1/orders/", json=_order_payload(c["id"], b["id"], width=500)
    )
    assert second.status_code == 201
