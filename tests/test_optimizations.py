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
            "length": 2440,
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
                "index": 0,
                "width": 600,
                "height": 400,
                "quantity": 2,
                "boardId": board_id,
                "label": "Puerta",
                "allowRotation": True,
            }
        ],
    }


def test_optimize_returns_solution(client):
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
    assert len(data["solution"]) >= 1
    assert "placedPieces" in data["solution"][0]


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
