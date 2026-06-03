"""Tests del módulo optimizations: flujo completo optimize + proforma."""

import pytest

from src.modules.optimizations.schemas import OptimizeRequest
from src.modules.optimizations.service import OptimizationService
from src.shared.exceptions import EntityNotFoundError, ValidationError


def _create_client(client):
    return client.post(
        "/api/v1/clients/",
        json={"identifier": "0991112233", "firstName": "Ada", "lastName": "Lovelace"},
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


def _optimize_payload(client_id, board_id):
    return {
        "clientId": client_id,
        "requirements": [
            {
                "priority": 0,
                "height": 400,
                "width": 600,
                "quantity": 2,
                "boardId": board_id,
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
    data = resp.json()
    assert data["client"]["id"] == created_client["id"]
    assert data["totalBoardsUsed"] >= 1
    assert len(data["layouts"]) >= 1
    layout = data["layouts"][0]
    assert "placedPieces" in layout
    assert layout["material"]["boardId"] == created_board["id"]
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
    optimization_hash = resp.json()["optimizationHash"]
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
    data = resp.json()
    assert data["totalBoardsUsed"] >= 1
    assert data["totalBoardsCost"] == pytest.approx(data["totalBoardsUsed"] * 45.5)
    assert data["totalBoardsCost"] > 0


def test_optimize_unknown_board_returns_404(client):
    created_client = _create_client(client)
    resp = client.post(
        "/api/v1/optimize/",
        json=_optimize_payload(created_client["id"], board_id=99999),
    )
    assert resp.status_code == 404
    assert "Board 99999" in resp.json()["detail"]


def test_proforma_pdf_and_base64(client):
    created_client = _create_client(client)
    created_board = _create_board(client)
    optimization = client.post(
        "/api/v1/optimize/",
        json=_optimize_payload(created_client["id"], created_board["id"]),
    ).json()
    opt_id = optimization["id"]

    pdf = client.get(f"/api/v1/optimize/{opt_id}/proforma")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert len(pdf.content) > 1000

    b64 = client.get(f"/api/v1/optimize/{opt_id}/proforma", params={"format": "base64"})
    assert b64.status_code == 200
    body = b64.json()
    assert body["format"] == "base64"
    assert body["mimeType"] == "application/pdf"
    assert len(body["content"]) > 0


def test_proforma_missing_optimization_returns_404(client):
    assert client.get("/api/v1/optimize/999999/proforma").status_code == 404


def test_service_rejects_empty_requirements(db_session):
    """La guarda defensiva de ``execute`` lanza ValidationError (422)."""
    request = OptimizeRequest.model_construct(requirements=[], client_id=1)
    with pytest.raises(ValidationError):
        OptimizationService(db_session).execute(request)


def test_service_get_or_404(db_session):
    with pytest.raises(EntityNotFoundError):
        OptimizationService(db_session).get_or_404(123456)


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
                "boardId": created_board["id"],
                "label": "",
                "canRotate": True,
            }
        ],
    }
    resp = client.post("/api/v1/optimize/", json=payload)
    assert resp.status_code == 200
    data = resp.json()

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
    assert group["boardId"] == created_board["id"]
    assert group["layout"]["material"]["boardId"] == created_board["id"]


def test_optimize_includes_materials_summary(client):
    """materials_summary agrupa por tipo de tablero con código, cantidad y costo."""
    created_client = _create_client(client)
    created_board = _create_board(client, code="MEL18")

    resp = client.post(
        "/api/v1/optimize/",
        json=_optimize_payload(created_client["id"], created_board["id"]),
    )
    assert resp.status_code == 200
    data = resp.json()

    summary = data.get("materialsSummary")
    assert summary is not None and len(summary) == 1

    entry = summary[0]
    assert entry["boardCode"] == "MEL18"
    assert entry["boardName"] == "Melamina MEL18"
    assert entry["count"] == data["totalBoardsUsed"]
    assert entry["totalCost"] == pytest.approx(data["totalBoardsCost"])
