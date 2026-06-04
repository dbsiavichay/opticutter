"""Tests del módulo optimizations: flujo completo optimize + proforma."""

import pytest

from src.modules.optimizations.schemas import OptimizeRequest
from src.modules.optimizations.service import OptimizationService
from src.shared.exceptions import EntityNotFoundError, ValidationError


def _create_client(client):
    return client.post(
        "/api/v1/clients/",
        json={
            "identifier": "0991112233",
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


def _optimize_payload(client_id, product_id):
    return {
        "clientId": client_id,
        "requirements": [
            {
                "priority": 0,
                "height": 400,
                "width": 600,
                "quantity": 2,
                "productId": product_id,
                "label": "Puerta",
                "canRotate": True,
            }
        ],
    }


def test_optimize_returns_layouts(client):
    created_client = _create_client(client)
    created_board = _create_board(client)

    resp = client.post(
        "/api/v1/optimize/",
        json=_optimize_payload(created_client["id"], created_board["id"]),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["client"]["id"] == created_client["id"]
    assert data["totalBoardsUsed"] >= 1
    assert len(data["layouts"]) >= 1
    layout = data["layouts"][0]
    assert "placedPieces" in layout
    assert layout["material"]["materialId"] == created_board["id"]
    assert layout["material"]["sheetNumber"] == 1
    assert "efficiency" in layout["statistics"]
    assert layout["placedPieces"][0]["originalWidth"] == 600


def test_optimize_returns_optimization_hash(client):
    """La respuesta expone el hash determinista de las entradas."""
    created_client = _create_client(client)
    created_board = _create_board(client)

    resp = client.post(
        "/api/v1/optimize/",
        json=_optimize_payload(created_client["id"], created_board["id"]),
    )
    assert resp.status_code == 200
    optimization_hash = resp.json()["data"]["optimizationHash"]
    assert isinstance(optimization_hash, str) and len(optimization_hash) == 64


def test_optimize_computes_total_boards_cost(client):
    """El costo total debe ser nº de tableros usados * precio del tablero."""
    created_client = _create_client(client)
    created_board = _create_board(client)

    resp = client.post(
        "/api/v1/optimize/",
        json=_optimize_payload(created_client["id"], created_board["id"]),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["totalBoardsUsed"] >= 1
    assert data["totalBoardsCost"] == pytest.approx(data["totalBoardsUsed"] * 45.5)
    assert data["totalBoardsCost"] > 0


def test_optimize_unknown_product_returns_404(client):
    created_client = _create_client(client)
    resp = client.post(
        "/api/v1/optimize/",
        json=_optimize_payload(created_client["id"], product_id=99999),
    )
    assert resp.status_code == 404
    assert "Product 99999" in resp.json()["errors"][0]["message"]


def test_optimize_non_board_product_is_rejected(client):
    """Un producto que no es tablero no es optimizable (regla de negocio 422)."""
    created_client = _create_client(client)
    tapacanto = client.post(
        "/api/v1/products/",
        json={
            "type": "edge_banding",
            "code": "TAP22",
            "name": "Tapacanto PVC 22mm",
            "price": 0.8,
            "attributes": {"length": 50000, "width": 22, "thickness": 1},
        },
    ).json()["data"]

    resp = client.post(
        "/api/v1/optimize/",
        json=_optimize_payload(created_client["id"], tapacanto["id"]),
    )
    assert resp.status_code == 422
    assert "no es un tablero" in resp.json()["errors"][0]["message"].lower()


def test_proforma_pdf_and_base64(client):
    created_client = _create_client(client)
    created_board = _create_board(client)
    optimization = client.post(
        "/api/v1/optimize/",
        json=_optimize_payload(created_client["id"], created_board["id"]),
    ).json()["data"]
    opt_hash = optimization["optimizationHash"]

    pdf = client.get(
        f"/api/v1/optimize/{opt_hash}/proforma",
        params={"clientId": created_client["id"]},
    )
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert len(pdf.content) > 1000

    # La proforma PDF/base64 queda exenta de la envoltura (transporte de archivo).
    b64 = client.get(
        f"/api/v1/optimize/{opt_hash}/proforma",
        params={"clientId": created_client["id"], "format": "base64"},
    )
    assert b64.status_code == 200
    body = b64.json()
    assert body["format"] == "base64"
    assert body["mimeType"] == "application/pdf"
    assert len(body["content"]) > 0


def test_proforma_missing_optimization_returns_404(client):
    """Un hash que no está en caché (expiró o nunca existió) responde 404."""
    resp = client.get(f"/api/v1/optimize/{'0' * 64}/proforma", params={"clientId": 1})
    assert resp.status_code == 404


def test_proforma_requires_client_id(client):
    """La proforma exige ``clientId`` (la optimización es anónima)."""
    assert client.get(f"/api/v1/optimize/{'0' * 64}/proforma").status_code == 422


def test_proforma_blocked_without_client_phone(client):
    """Regla de negocio: sin celular registrado no se genera la proforma (422)."""
    created_board = _create_board(client)
    no_phone = client.post(
        "/api/v1/clients/",
        json={"identifier": "0990000000", "firstName": "Sin", "lastName": "Tel"},
    ).json()["data"]
    optimization = client.post(
        "/api/v1/optimize/",
        json=_optimize_payload(no_phone["id"], created_board["id"]),
    ).json()["data"]
    opt_hash = optimization["optimizationHash"]

    resp = client.get(
        f"/api/v1/optimize/{opt_hash}/proforma",
        params={"clientId": no_phone["id"]},
    )
    assert resp.status_code == 422
    assert "celular" in resp.json()["errors"][0]["message"].lower()


def test_optimize_without_client_is_anonymous(client):
    """``POST /optimize`` sin ``clientId`` responde 200 con ``client`` nulo y el
    mismo hash que con cliente (el cómputo es agnóstico del cliente)."""
    created_client = _create_client(client)
    created_board = _create_board(client)

    with_client = client.post(
        "/api/v1/optimize/",
        json=_optimize_payload(created_client["id"], created_board["id"]),
    ).json()["data"]

    anon_payload = _optimize_payload(created_client["id"], created_board["id"])
    anon_payload.pop("clientId")
    anon = client.post("/api/v1/optimize/", json=anon_payload)

    assert anon.status_code == 200
    data = anon.json()["data"]
    assert data["client"] is None
    assert data["optimizationHash"] == with_client["optimizationHash"]


def test_optimize_unknown_client_returns_404(client):
    """Si se envía un ``clientId`` inexistente, la respuesta es 404."""
    created_board = _create_board(client)
    resp = client.post(
        "/api/v1/optimize/",
        json=_optimize_payload(client_id=99999, product_id=created_board["id"]),
    )
    assert resp.status_code == 404
    assert "Client 99999" in resp.json()["errors"][0]["message"]


def test_optimize_does_not_persist(client, db_session):
    """El dual-write se retiró: ``POST /optimize`` no escribe en BD."""
    from src.modules.optimizations.model import OptimizationModel

    created_client = _create_client(client)
    created_board = _create_board(client)
    resp = client.post(
        "/api/v1/optimize/",
        json=_optimize_payload(created_client["id"], created_board["id"]),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] is None
    assert db_session.query(OptimizationModel).count() == 0


def test_service_rejects_empty_requirements(db_session):
    """La guarda defensiva de ``compute`` lanza ValidationError (422)."""
    request = OptimizeRequest.model_construct(requirements=[], client_id=1)
    with pytest.raises(ValidationError):
        OptimizationService(db_session).compute(request)


def test_service_cached_payload_404(db_session):
    with pytest.raises(EntityNotFoundError):
        OptimizationService(db_session).get_cached_payload("nope")


def test_optimize_deduplicates_identical_patterns(client):
    """Varias hojas con el mismo patrón se colapsan en un grupo con su conteo."""
    created_client = _create_client(client)
    created_board = _create_board(client)

    # Una pieza grande (1700×670) entra una sola vez por tablero → 5 hojas idénticas.
    payload = {
        "clientId": created_client["id"],
        "requirements": [
            {
                "priority": 0,
                "height": 1700,
                "width": 670,
                "quantity": 5,
                "productId": created_board["id"],
                "label": "",
                "canRotate": True,
            }
        ],
    }
    resp = client.post("/api/v1/optimize/", json=payload)
    assert resp.status_code == 200
    data = resp.json()["data"]

    # El conteo físico se mantiene en 5 (layouts, totales y resumen de materiales).
    assert data["totalBoardsUsed"] == 5
    assert len(data["layouts"]) == 5
    assert data["materialsSummary"][0]["count"] == 5

    # Pero los patrones se deduplican en un único grupo con count == 5.
    groups = data["layoutGroups"]
    assert len(groups) == 1
    group = groups[0]
    assert group["patternId"] == 1
    assert group["count"] == 5
    assert len(group["sheetNumbers"]) == 5
    assert group["materialId"] == created_board["id"]
    assert group["layout"]["material"]["materialId"] == created_board["id"]


def test_optimize_includes_materials_summary(client):
    """materials_summary agrupa por tipo de tablero con código, cantidad y costo."""
    created_client = _create_client(client)
    created_board = _create_board(client, code="MEL18")

    resp = client.post(
        "/api/v1/optimize/",
        json=_optimize_payload(created_client["id"], created_board["id"]),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]

    summary = data.get("materialsSummary")
    assert summary is not None and len(summary) == 1

    entry = summary[0]
    assert entry["productCode"] == "MEL18"
    assert entry["productName"] == "Melamina MEL18"
    assert entry["count"] == data["totalBoardsUsed"]
    assert entry["totalCost"] == pytest.approx(data["totalBoardsCost"])
