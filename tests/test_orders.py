"""Tests del módulo orders: creación (snapshot), idempotencia, estados.

Las órdenes ya no se crean por HTTP (``POST /orders`` se retiró): nacen al confirmar
una pre-orden. Aquí se mintan directamente por ``OrderService.create`` (la vía interna
que conserva el flujo) reusando la sesión del fixture ``client``, y se leen vía GET para
verificar la proyección API en camelCase.
"""

from datetime import datetime

import pytest

from src.modules.orders.schemas import OrderCreate
from src.modules.orders.service import OrderService
from src.shared.exceptions import BusinessRuleError, EntityNotFoundError


def _create_client(client, identifier="0991112233", phone="0991112233"):
    return client.post(
        "/api/v1/clients/",
        json={
            "identifier": identifier,
            "firstName": "Ada",
            "lastName": "Lovelace",
            "phone": phone,
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


# Sucursal por defecto sembrada por conftest (id=1).
_BRANCH = 1


def _order_payload(client_id, product_id, height=400, width=600, quantity=2):
    return {
        "clientId": client_id,
        "branchId": _BRANCH,
        "materials": [{"key": "b1", "source": "catalog", "productId": product_id}],
        "requirements": [
            {
                "priority": 0,
                "height": height,
                "width": width,
                "quantity": quantity,
                "materialKey": "b1",
                "label": "Puerta",
                "canRotate": True,
            }
        ],
    }


def _mint_order(db_session, payload):
    """Crea la orden por el servicio y devuelve el ``OrderModel``."""
    return OrderService(db_session).create(OrderCreate.model_validate(payload))


def _create_order(client, db_session, payload):
    """Mintea la orden y devuelve su proyección API (GET) en camelCase."""
    order = _mint_order(db_session, payload)
    return client.get(f"/api/v1/orders/{order.id}").json()["data"]


def test_create_order_freezes_snapshot_and_charges_boards(client, db_session):
    c = _create_client(client)
    b = _create_board(client)

    data = _create_order(client, db_session, _order_payload(c["id"], b["id"]))

    assert data["status"] == "confirmed"
    assert data["code"] == f"ORD-{datetime.utcnow().year}-{data['id']:04d}"
    assert data["client"]["id"] == c["id"]
    # La orden expone su sucursal dueña (referencia compacta) para el dashboard.
    assert data["branch"]["id"] == _BRANCH
    assert data["branch"]["code"] == "MATRIZ"
    assert data["branch"]["name"] == "Casa Matriz"
    assert len(data["optimizationHash"]) == 64

    # Cobro = tableros: una línea por tipo de tablero (desde materials_summary).
    assert len(data["lines"]) == 1
    line = data["lines"][0]
    assert line["productCode"] == "MEL18"
    assert line["quantity"] == data["totalBoardsUsed"]
    assert line["lineTotal"] == line["quantity"] * 45.5

    # Totales inmutables = suma por tableros.
    assert data["total"] == data["subtotal"] == line["lineTotal"]

    # La orden ya no lleva vigencia (la cotización mutable vive en la pre-orden).
    assert "expiresAt" not in data

    # Lista de corte = piezas (insumo de producción, no se cobra).
    assert len(data["pieces"]) == 1
    piece = data["pieces"][0]
    assert piece["height"] == 400 and piece["width"] == 600
    assert piece["quantity"] == 2

    # Historial inicial registra la creación.
    assert data["history"][0]["toStatus"] == "confirmed"
    assert data["history"][0]["fromStatus"] is None


def test_create_order_blocked_without_client_phone(client, db_session):
    """Regla de negocio: sin celular registrado no se crea el pedido (422)."""
    b = _create_board(client)
    no_phone = client.post(
        "/api/v1/clients/",
        json={"identifier": "0990000000", "firstName": "Sin", "lastName": "Tel"},
    ).json()["data"]

    with pytest.raises(BusinessRuleError) as exc:
        _mint_order(db_session, _order_payload(no_phone["id"], b["id"]))
    assert "celular" in str(exc.value).lower()
    # No se persistió ninguna orden.
    assert client.get("/api/v1/orders/").json()["data"] == []


def test_create_order_unknown_client_returns_404(client, db_session):
    """Un ``clientId`` inexistente da 404 limpio antes de congelar nada."""
    b = _create_board(client)
    with pytest.raises(EntityNotFoundError) as exc:
        _mint_order(db_session, _order_payload(99999, b["id"]))
    assert "Client 99999" in str(exc.value)


def test_create_order_is_idempotent(client, db_session):
    c = _create_client(client)
    b = _create_board(client)
    payload = _order_payload(c["id"], b["id"])

    first = _mint_order(db_session, payload)
    second = _mint_order(db_session, payload)

    assert first.id == second.id
    assert first.code == second.code
    # No se crean dos órdenes para el mismo (cliente, hash).
    assert len(client.get("/api/v1/orders/").json()["data"]) == 1


def test_status_transitions_valid_and_invalid(client, db_session):
    c = _create_client(client)
    b = _create_board(client)
    order = _create_order(client, db_session, _order_payload(c["id"], b["id"]))
    oid = order["id"]

    ok = client.patch(f"/api/v1/orders/{oid}/status", json={"status": "in_production"})
    assert ok.status_code == 200
    assert ok.json()["data"]["status"] == "in_production"

    ok2 = client.patch(f"/api/v1/orders/{oid}/status", json={"status": "cutting"})
    assert ok2.status_code == 200
    assert ok2.json()["data"]["status"] == "cutting"
    # Historial acumulado: creación + 2 transiciones.
    assert len(ok2.json()["data"]["history"]) == 3

    # cutting → completed no es una transición válida.
    bad = client.patch(f"/api/v1/orders/{oid}/status", json={"status": "completed"})
    assert bad.status_code == 422
    assert "inválida" in bad.json()["errors"][0]["message"]


def test_invalid_transition_from_confirmed(client, db_session):
    c = _create_client(client)
    b = _create_board(client)
    order = _create_order(client, db_session, _order_payload(c["id"], b["id"]))
    # confirmed → completed (salta estados) no es válido.
    bad = client.patch(
        f"/api/v1/orders/{order['id']}/status", json={"status": "completed"}
    )
    assert bad.status_code == 422


def test_list_orders_filter_by_status(client, db_session):
    c = _create_client(client)
    b = _create_board(client)
    o1 = _create_order(client, db_session, _order_payload(c["id"], b["id"], width=600))
    _create_order(client, db_session, _order_payload(c["id"], b["id"], width=500))

    # Enviar la primera a producción.
    client.patch(f"/api/v1/orders/{o1['id']}/status", json={"status": "in_production"})

    in_prod = client.get("/api/v1/orders/", params={"status": "in_production"}).json()
    assert [o["id"] for o in in_prod["data"]] == [o1["id"]]
    assert in_prod["meta"]["pagination"]["total"] == 1

    confirmed = client.get("/api/v1/orders/", params={"status": "confirmed"}).json()
    assert o1["id"] not in [o["id"] for o in confirmed["data"]]
    assert len(confirmed["data"]) == 1


def test_get_order_404(client):
    assert client.get("/api/v1/orders/999999").status_code == 404


def test_order_proforma_pdf_and_base64(client, db_session):
    c = _create_client(client)
    b = _create_board(client)
    order = _create_order(client, db_session, _order_payload(c["id"], b["id"]))
    oid = order["id"]

    pdf = client.get(f"/api/v1/orders/{oid}/proforma")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert len(pdf.content) > 1000

    # PDF/base64 exentos de la envoltura (transporte de archivo).
    b64 = client.get(f"/api/v1/orders/{oid}/proforma", params={"format": "base64"})
    assert b64.status_code == 200
    body = b64.json()
    assert body["format"] == "base64"
    assert body["mimeType"] == "application/pdf"
    assert order["code"] in body["filename"]


def test_order_production_sheet_pdf(client, db_session):
    c = _create_client(client)
    b = _create_board(client)
    order = _create_order(client, db_session, _order_payload(c["id"], b["id"]))

    sheet = client.get(f"/api/v1/orders/{order['id']}/production-sheet")
    assert sheet.status_code == 200
    assert sheet.headers["content-type"] == "application/pdf"
    assert len(sheet.content) > 1000


def test_order_documents_404(client):
    assert client.get("/api/v1/orders/999999/proforma").status_code == 404
    assert client.get("/api/v1/orders/999999/production-sheet").status_code == 404


def test_order_export_document(client, db_session):
    c = _create_client(client)
    b = _create_board(client)
    order = _create_order(client, db_session, _order_payload(c["id"], b["id"]))

    resp = client.get(f"/api/v1/orders/{order['id']}/export")
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["orderCode"] == order["code"]
    assert data["status"] == "confirmed"
    assert data["client"]["id"] == c["id"]
    assert data["currency"] == "USD"
    assert data["issuedAt"] is not None
    assert data["externalInvoiceId"] is None

    # Cobro por producto: una línea con descripción legible y el código.
    assert len(data["lines"]) == 1
    line = data["lines"][0]
    assert line["productCode"] == "MEL18"
    assert "MEL18" in line["description"]
    assert line["quantity"] == order["totalBoardsUsed"]
    assert line["unitPrice"] == 45.5
    assert line["lineTotal"] == line["quantity"] * 45.5
    assert data["subtotal"] == data["total"] == line["lineTotal"]


def test_set_external_invoice_id_and_reflect_in_export(client, db_session):
    c = _create_client(client)
    b = _create_board(client)
    order = _create_order(client, db_session, _order_payload(c["id"], b["id"]))
    oid = order["id"]

    resp = client.post(
        f"/api/v1/orders/{oid}/invoice", json={"externalInvoiceId": "FAC-001-42"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["externalInvoiceId"] == "FAC-001-42"

    # Idempotente con el mismo ID.
    again = client.post(
        f"/api/v1/orders/{oid}/invoice", json={"externalInvoiceId": "FAC-001-42"}
    )
    assert again.status_code == 200

    # El export refleja la factura asociada.
    exported = client.get(f"/api/v1/orders/{oid}/export").json()["data"]
    assert exported["externalInvoiceId"] == "FAC-001-42"


def test_set_external_invoice_id_conflict_on_different_id(client, db_session):
    c = _create_client(client)
    b = _create_board(client)
    order = _create_order(client, db_session, _order_payload(c["id"], b["id"]))
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


def _manual_material_payload(client_id):
    """Orden con un único material 'manual' (fuera del catálogo)."""
    return {
        "clientId": client_id,
        "branchId": _BRANCH,
        "materials": [
            {
                "key": "m1",
                "source": "manual",
                "height": 2000,
                "width": 1000,
                "thickness": 18,
                "costPerUnit": 30.0,
                "label": "Sobrante taller",
            }
        ],
        "requirements": [
            {
                "priority": 0,
                "height": 400,
                "width": 600,
                "quantity": 1,
                "materialKey": "m1",
            }
        ],
    }


def test_create_order_with_non_catalog_material(client, db_session):
    """Un material 'manual' se congela tal cual el snapshot: línea sin productId."""
    c = _create_client(client)

    data = _create_order(client, db_session, _manual_material_payload(c["id"]))

    # Cobro = el material manual, identificado por code/name (sin productId).
    assert len(data["lines"]) == 1
    line = data["lines"][0]
    assert line["productId"] is None
    assert line["productCode"] == "m1"
    assert line["productName"] == "Sobrante taller"
    assert line["unitPriceSnapshot"] == 30.0
    assert line["lineTotal"] == 30.0 * line["quantity"]
    assert data["total"] == data["subtotal"] == 30.0 * data["totalBoardsUsed"]

    # La pieza cortada del material manual también queda sin productId.
    assert len(data["pieces"]) == 1
    assert data["pieces"][0]["productId"] is None

    # Se persistió la orden.
    assert len(client.get("/api/v1/orders/").json()["data"]) == 1


def test_create_mixed_catalog_and_offcut_order(client, db_session):
    """Orden mixta: tablero de catálogo + retazo de empresa (costo 0)."""
    c = _create_client(client)
    b = _create_board(client)

    payload = {
        "clientId": c["id"],
        "branchId": _BRANCH,
        "materials": [
            {"key": "b1", "source": "catalog", "productId": b["id"]},
            {
                "key": "r1",
                "source": "companyOffcut",
                "height": 1200,
                "width": 600,
                "thickness": 15,
                "costPerUnit": 0,
            },
        ],
        "requirements": [
            {
                "priority": 0,
                "height": 400,
                "width": 600,
                "quantity": 1,
                "materialKey": "b1",
            },
            {
                "priority": 0,
                "height": 300,
                "width": 400,
                "quantity": 1,
                "materialKey": "r1",
            },
        ],
    }
    data = _create_order(client, db_session, payload)

    assert len(data["lines"]) == 2
    catalog_line = next(line for line in data["lines"] if line["productId"] is not None)
    offcut_line = next(line for line in data["lines"] if line["productId"] is None)
    assert catalog_line["productId"] == b["id"]
    assert catalog_line["productCode"] == "MEL18"
    assert offcut_line["productCode"] == "r1"
    # El retazo a costo 0 no suma al total; este = solo el tablero de catálogo.
    assert offcut_line["lineTotal"] == 0
    assert data["total"] == catalog_line["lineTotal"]

    # Cada pieza referencia su material: catálogo → productId, retazo → None.
    piece_product_ids = {p["productId"] for p in data["pieces"]}
    assert piece_product_ids == {b["id"], None}


def test_non_catalog_order_renders_proforma_and_production_sheet(client, db_session):
    """Proforma y hoja de producción se renderizan del snapshot, sin catálogo."""
    c = _create_client(client)
    order = _create_order(client, db_session, _manual_material_payload(c["id"]))

    proforma = client.get(f"/api/v1/orders/{order['id']}/proforma")
    assert proforma.status_code == 200
    assert proforma.headers["content-type"] == "application/pdf"
    assert len(proforma.content) > 1000

    sheet = client.get(f"/api/v1/orders/{order['id']}/production-sheet")
    assert sheet.status_code == 200
    assert sheet.headers["content-type"] == "application/pdf"
    assert len(sheet.content) > 1000
