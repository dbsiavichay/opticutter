"""Tests de tapacantos: metraje, validación, regla de rotación y cobro en órdenes."""

import math

import pytest

from src.modules.optimizations.schemas import EdgeBandingSpec, EdgeSide
from src.modules.optimizations.service import OptimizationService
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
    ).json()["data"]


def _create_board(client, code="MEL18", price=45.5):
    return client.post(
        "/api/v1/products/",
        json={
            "type": "board",
            "code": code,
            "name": f"Melamina {code}",
            "price": price,
            "attributes": {"height": 2440, "width": 1220, "thickness": 18},
        },
    ).json()["data"]


def _create_edge_banding(client, code="TAP22", price=2.0, color="Blanco"):
    return client.post(
        "/api/v1/products/",
        json={
            "type": "edge_banding",
            "code": code,
            "name": f"Tapacanto {code}",
            "price": price,
            "attributes": {
                "thickness": 0.45,
                "width": 22,
                "color": color,
                "length": 50000,
            },
        },
    ).json()["data"]


def _requirement(board_id, eb_id, sides, height=500, width=1000, quantity=1):
    return {
        "priority": 0,
        "height": height,
        "width": width,
        "quantity": quantity,
        "productId": board_id,
        "label": "Costado",
        "canRotate": True,
        "edgeBanding": {"productId": eb_id, "sides": sides},
    }


def _expected_meters(net_m: float):
    """Replica la fórmula del servicio: merma + redondeo al metro entero."""
    with_waste = net_m * (1 + config.EDGE_BANDING_WASTE_FACTOR)
    return round(with_waste, 2), math.ceil(with_waste)


# --------------------------------------------------------------------------- #
# Metraje y costo (endpoint /optimize)
# --------------------------------------------------------------------------- #
def test_optimize_aggregates_edge_banding_meters_and_cost(client):
    c = _create_client(client)
    b = _create_board(client)
    eb = _create_edge_banding(client, price=2.0)

    # height=500 (alto), width=1000 (ancho); lados top+bottom = 2×ancho = 2000 mm.
    resp = client.post(
        "/api/v1/optimize/",
        json={
            "clientId": c["id"],
            "requirements": [_requirement(b["id"], eb["id"], ["top", "bottom"])],
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]

    summary = data["edgeBandingsSummary"]
    assert summary is not None and len(summary) == 1
    entry = summary[0]
    assert entry["productCode"] == "TAP22"
    assert entry["color"] == "Blanco"
    assert entry["netLinearM"] == pytest.approx(2.0)

    linear_m, billed = _expected_meters(2.0)
    assert entry["linearM"] == pytest.approx(linear_m)
    assert entry["billedLinearM"] == billed
    assert entry["pricePerM"] == 2.0
    assert entry["totalCost"] == pytest.approx(round(billed * 2.0, 2))
    assert data["totalEdgeBandingCost"] == pytest.approx(round(billed * 2.0, 2))


def test_optimize_uses_height_for_left_right_sides(client):
    """left/right miden el alto; top/bottom el ancho."""
    c = _create_client(client)
    b = _create_board(client)
    eb = _create_edge_banding(client, price=1.0)

    # alto=500: left+right = 2×500 = 1000 mm = 1.0 m neto.
    resp = client.post(
        "/api/v1/optimize/",
        json={
            "clientId": c["id"],
            "requirements": [_requirement(b["id"], eb["id"], ["left", "right"])],
        },
    )
    data = resp.json()["data"]
    assert data["edgeBandingsSummary"][0]["netLinearM"] == pytest.approx(1.0)


def test_optimize_aggregates_multiple_edge_banding_types(client):
    c = _create_client(client)
    b = _create_board(client)
    eb1 = _create_edge_banding(client, code="TAP22", price=2.0)
    eb2 = _create_edge_banding(client, code="TAP15", price=3.0, color="Nogal")

    resp = client.post(
        "/api/v1/optimize/",
        json={
            "clientId": c["id"],
            "requirements": [
                _requirement(b["id"], eb1["id"], ["top", "bottom"]),
                _requirement(b["id"], eb2["id"], ["left", "right"], height=1000),
            ],
        },
    )
    data = resp.json()["data"]
    summary = {e["productCode"]: e for e in data["edgeBandingsSummary"]}
    assert set(summary) == {"TAP22", "TAP15"}
    total = sum(e["totalCost"] for e in data["edgeBandingsSummary"])
    assert data["totalEdgeBandingCost"] == pytest.approx(round(total, 2))


def test_optimize_without_edge_banding_has_empty_summary(client):
    c = _create_client(client)
    b = _create_board(client)
    resp = client.post(
        "/api/v1/optimize/",
        json={
            "clientId": c["id"],
            "requirements": [
                {
                    "priority": 0,
                    "height": 400,
                    "width": 600,
                    "quantity": 1,
                    "productId": b["id"],
                    "label": "P",
                    "canRotate": True,
                }
            ],
        },
    )
    data = resp.json()["data"]
    assert data["totalEdgeBandingCost"] == 0.0
    assert data["edgeBandingsSummary"] in (None, [])


# --------------------------------------------------------------------------- #
# Validación del producto de tapacanto
# --------------------------------------------------------------------------- #
def test_edge_banding_unknown_product_returns_404(client):
    c = _create_client(client)
    b = _create_board(client)
    resp = client.post(
        "/api/v1/optimize/",
        json={
            "clientId": c["id"],
            "requirements": [_requirement(b["id"], 99999, ["top"])],
        },
    )
    assert resp.status_code == 404
    assert "Product 99999" in resp.json()["errors"][0]["message"]


def test_edge_banding_non_edge_banding_product_rejected(client):
    """Si edgeBanding.productId apunta a un tablero → regla de negocio 422."""
    c = _create_client(client)
    b = _create_board(client)
    other_board = _create_board(client, code="MEL15")
    resp = client.post(
        "/api/v1/optimize/",
        json={
            "clientId": c["id"],
            "requirements": [_requirement(b["id"], other_board["id"], ["top"])],
        },
    )
    assert resp.status_code == 422
    assert "no es un tapacanto" in resp.json()["errors"][0]["message"].lower()


def test_edge_banding_rejects_duplicate_sides(client):
    c = _create_client(client)
    b = _create_board(client)
    eb = _create_edge_banding(client)
    resp = client.post(
        "/api/v1/optimize/",
        json={
            "clientId": c["id"],
            "requirements": [_requirement(b["id"], eb["id"], ["top", "top"])],
        },
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# Lados geométricos y remapeo al rotar
# --------------------------------------------------------------------------- #
def test_geometric_edges_mapping(db_session):
    svc = OptimizationService(db_session)
    spec_tb = EdgeBandingSpec(product_id=2, sides=[EdgeSide.top, EdgeSide.bottom])
    spec_lr = EdgeBandingSpec(product_id=2, sides=[EdgeSide.left, EdgeSide.right])
    spec_asym = EdgeBandingSpec(
        product_id=2, sides=[EdgeSide.top, EdgeSide.left, EdgeSide.right]
    )

    # Sin rotar: identidad.
    assert svc._geometric_edges(spec_tb, {}, False)["sides"] == ["top", "bottom"]
    assert svc._geometric_edges(spec_asym, {}, False)["sides"] == [
        "top",
        "left",
        "right",
    ]
    # Rotada (giro 90° horario): top→right, right→bottom, bottom→left, left→top.
    assert svc._geometric_edges(spec_tb, {}, True)["sides"] == ["left", "right"]
    assert svc._geometric_edges(spec_lr, {}, True)["sides"] == ["top", "bottom"]
    # Asimétrico también se remapea (no se bloquea la rotación).
    assert svc._geometric_edges(spec_asym, {}, True)["sides"] == [
        "top",
        "bottom",
        "right",
    ]


def test_asymmetric_banding_rotates_and_swaps_edges(client):
    """Canteado asimétrico NO bloquea la rotación: si la pieza sale rotada, los
    cantos se intercambian al lado físico correspondiente."""
    c = _create_client(client)
    b = _create_board(client)  # 2440 (alto) × 1220 (ancho)
    eb = _create_edge_banding(client)

    # Pieza 1000(alto) × 2000(ancho): solo entra rotada (ancho 2000 > tablero 1220).
    resp = client.post(
        "/api/v1/optimize/",
        json={
            "clientId": c["id"],
            "requirements": [
                _requirement(
                    b["id"], eb["id"], ["top", "left"], height=1000, width=2000
                )
            ],
        },
    )
    placed = resp.json()["data"]["layouts"][0]["placedPieces"][0]
    assert placed["rotated"] is True
    # CW: top→right, left→top ⇒ lados geométricos {top, right}.
    assert placed["edges"]["sides"] == ["top", "right"]
    assert placed["edges"]["code"] == "TAP22"


# --------------------------------------------------------------------------- #
# Cobro durable en órdenes
# --------------------------------------------------------------------------- #
def test_order_charges_edge_banding(client):
    c = _create_client(client)
    b = _create_board(client, price=45.5)
    eb = _create_edge_banding(client, price=2.0)

    resp = client.post(
        "/api/v1/orders/",
        json={
            "clientId": c["id"],
            "requirements": [_requirement(b["id"], eb["id"], ["top", "bottom"])],
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]

    # Dos líneas de cobro: tablero + tapacanto.
    lines = {line["productCode"]: line for line in data["lines"]}
    assert "MEL18" in lines and "TAP22" in lines

    _, billed = _expected_meters(2.0)
    eb_line = lines["TAP22"]
    assert eb_line["quantity"] == billed
    assert eb_line["unitPriceSnapshot"] == 2.0
    assert eb_line["lineTotal"] == pytest.approx(round(billed * 2.0, 2))
    assert eb_line["linearM"] is not None

    # Totales inmutables = tableros + tapacantos.
    expected_total = round(sum(line["lineTotal"] for line in data["lines"]), 2)
    assert data["subtotal"] == data["total"] == pytest.approx(expected_total)

    # La pieza congela su canteado (lados nominales).
    assert data["pieces"][0]["edges"]["sides"] == ["top", "bottom"]

    # El export de facturación incluye la línea de tapacanto.
    exported = client.get(f"/api/v1/orders/{data['id']}/export").json()["data"]
    codes = {line["productCode"] for line in exported["lines"]}
    assert {"MEL18", "TAP22"} <= codes


def test_order_proforma_with_edge_banding_renders(client):
    c = _create_client(client)
    b = _create_board(client)
    eb = _create_edge_banding(client)
    order = client.post(
        "/api/v1/orders/",
        json={
            "clientId": c["id"],
            "requirements": [_requirement(b["id"], eb["id"], ["top", "bottom"])],
        },
    ).json()["data"]

    proforma = client.get(f"/api/v1/orders/{order['id']}/proforma")
    assert proforma.status_code == 200
    assert len(proforma.content) > 1000

    sheet = client.get(f"/api/v1/orders/{order['id']}/production-sheet")
    assert sheet.status_code == 200
    assert len(sheet.content) > 1000
