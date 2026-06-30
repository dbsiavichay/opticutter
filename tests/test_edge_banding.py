"""Tests de tapacantos: metraje, validación, regla de rotación y cobro en órdenes."""

import math

import pytest

from src.modules.optimizations.labels import edge_banding_notation
from src.modules.optimizations.schemas import EdgeBandingSpec, EdgeSide
from src.modules.optimizations.service import OptimizationService
from src.modules.orders.schemas import OrderCreate
from src.modules.orders.service import OrderService
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


def _create_edge_banding(
    client, code="TAP22", price=2.0, color="Blanco", band_type=None
):
    attributes = {"thickness": 0.45, "width": 22, "color": color, "length": 50000}
    if band_type is not None:
        attributes["band_type"] = band_type
    return client.post(
        "/api/v1/products/",
        json={
            "type": "edge_banding",
            "code": code,
            "name": f"Tapacanto {code}",
            "price": price,
            "attributes": attributes,
        },
    ).json()["data"]


def _materials(board_id, key="b1"):
    """Stock de catálogo: un tablero referenciado por ``materialKey``."""
    return [{"key": key, "source": "catalog", "productId": board_id}]


def _requirement(eb_id, sides, height=500, width=1000, quantity=1, material_key="b1"):
    return {
        "priority": 0,
        "height": height,
        "width": width,
        "quantity": quantity,
        "materialKey": material_key,
        "label": "Costado",
        "canRotate": True,
        "edgeBanding": {"productId": eb_id, "sides": sides},
    }


def _expected_meters(net_m: float):
    """Replica la fórmula del servicio: merma + redondeo al metro entero."""
    with_waste = net_m * (1 + config.EDGE_BANDING_WASTE_FACTOR)
    return round(with_waste, 2), math.ceil(with_waste)


# --------------------------------------------------------------------------- #
# Notación de taller de los cantos (2L1C CS)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "sides, band_type, expected",
    [
        (["left", "right", "top"], "Soft", "2L1C CS"),  # 2 largos (alto) + 1 corto
        (["left"], "Soft", "1L CS"),  # solo largo: omite la parte en cero
        (["top", "bottom"], "Hard", "2C CD"),  # solo cortos (ancho), canto duro
        (["left", "right", "top", "bottom"], "Soft", "4L CS"),  # todos los lados
        ([], "Soft", ""),  # sin lados → vacío
        (["left", "right"], None, "2L"),  # sin band_type → sin sufijo
    ],
)
def test_edge_banding_notation(sides, band_type, expected):
    assert edge_banding_notation(sides, band_type) == expected


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
            "materials": _materials(b["id"]),
            "requirements": [_requirement(eb["id"], ["top", "bottom"])],
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


def test_optimize_reports_edge_banding_linear_m_per_sheet(client):
    """El metraje neto de canto se expone por plancha y como total general."""
    c = _create_client(client)
    b = _create_board(client)
    eb = _create_edge_banding(client, price=2.0)

    # top+bottom con width=1000 → 2×1000 = 2000 mm = 2.0 m neto (1 pieza, 1 plancha).
    resp = client.post(
        "/api/v1/optimize/",
        json={
            "clientId": c["id"],
            "materials": _materials(b["id"]),
            "requirements": [_requirement(eb["id"], ["top", "bottom"])],
        },
    )
    data = resp.json()["data"]
    assert data["totalEdgeBandingLinearM"] == pytest.approx(2.0)
    stats = data["layouts"][0]["statistics"]
    assert stats["edgeBandingLinearM"] == pytest.approx(2.0)


def test_unlabeled_piece_still_reports_edge_banding_per_sheet(client):
    """Regresión: una pieza SIN etiqueta y ``quantity=1`` usa el auto-label
    ``piece_1``; el metraje por plancha y los ``edges`` de la pieza no deben
    perderse (antes ``base_label`` mutilaba el ``_1`` y daba 0)."""
    c = _create_client(client)
    b = _create_board(client)
    eb = _create_edge_banding(client, price=2.0)

    resp = client.post(
        "/api/v1/optimize/",
        json={
            "clientId": c["id"],
            "materials": _materials(b["id"]),
            "requirements": [
                {
                    "priority": 0,
                    "height": 700,
                    "width": 1000,
                    "quantity": 1,
                    "materialKey": "b1",
                    "canRotate": True,
                    "edgeBanding": {"productId": eb["id"], "sides": ["top", "bottom"]},
                }
            ],
        },
    )
    data = resp.json()["data"]
    # top+bottom con width=1000 → 2×1000 = 2000 mm = 2.0 m neto.
    assert data["totalEdgeBandingLinearM"] == pytest.approx(2.0)
    layout = data["layouts"][0]
    assert layout["statistics"]["edgeBandingLinearM"] == pytest.approx(2.0)
    # El canto se propaga a la pieza colocada (para el diagrama / hoja de taller).
    placed = layout["placedPieces"][0]
    assert placed["edges"] is not None
    assert placed["edges"]["sides"] == ["top", "bottom"]


def test_optimize_edge_banding_without_product_reports_length_only(client):
    """Canto solo-geometría: ``edgeBanding`` con lados pero SIN ``productId`` calcula la
    longitud de canto (lo que importa en el optimizador) sin resolver ni cobrar un
    producto; este se asigna recién al cotizar."""
    c = _create_client(client)
    b = _create_board(client)

    resp = client.post(
        "/api/v1/optimize/",
        json={
            "clientId": c["id"],
            "materials": _materials(b["id"]),
            "requirements": [
                {
                    "priority": 0,
                    "height": 700,
                    "width": 1000,
                    "quantity": 1,
                    "materialKey": "b1",
                    "canRotate": True,
                    "edgeBanding": {"sides": ["top", "bottom"]},
                }
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    # La longitud sí se computa: top+bottom con width=1000 → 2.0 m neto.
    assert data["totalEdgeBandingLinearM"] == pytest.approx(2.0)
    # Sin producto: no hay costo de canto y el resumen va sin identidad ni precio.
    assert data["totalEdgeBandingCost"] == 0.0
    entry = data["edgeBandingsSummary"][0]
    assert entry["productId"] is None
    assert entry["productCode"] is None
    assert entry["pricePerM"] == 0.0
    assert entry["netLinearM"] == pytest.approx(2.0)
    # El canto se propaga a la pieza colocada (para el diagrama) sin producto.
    # ``edges`` es un dict crudo (no modelo Pydantic): sus claves van en snake_case.
    placed = data["layouts"][0]["placedPieces"][0]
    assert placed["edges"]["sides"] == ["top", "bottom"]
    assert placed["edges"]["product_id"] is None


def test_same_label_pieces_keep_their_own_edge_banding(client):
    """Regresión: varias piezas con la MISMA etiqueta y ``quantity=1`` pero cantos
    distintos NO se colapsan. Antes el canto se indexaba por etiqueta, así que todas
    heredaban el último spec (los 4 lados) y el metraje por plancha salía inflado;
    ahora cada pieza colocada conserva sus propios lados gracias al id único."""
    c = _create_client(client)
    b = _create_board(client)
    eb = _create_edge_banding(client, price=2.0)

    # Mismo label "Puerta", ancho distinto por pieza (identidad geométrica) y cantos
    # distintos; canRotate=False para que el lado geométrico == nominal.
    sides_by_width = {
        300: {"left"},
        301: {"left", "right"},
        302: {"top"},
        303: {"top", "bottom", "left", "right"},
    }
    requirements = [
        {
            "priority": 0,
            "height": 500,
            "width": w,
            "quantity": 1,
            "materialKey": "b1",
            "label": "Puerta",
            "canRotate": False,
            "edgeBanding": {"productId": eb["id"], "sides": list(sides)},
        }
        for w, sides in sides_by_width.items()
    ]
    resp = client.post(
        "/api/v1/optimize/",
        json={
            "clientId": c["id"],
            "materials": _materials(b["id"]),
            "requirements": requirements,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]

    # Cada pieza colocada conserva SUS lados, no los 4 del último requerimiento.
    placed = data["layouts"][0]["placedPieces"]
    assert len(placed) == len(sides_by_width)
    got = {p["originalWidth"]: set(p["edges"]["sides"]) for p in placed}
    assert got == sides_by_width

    # El metraje por plancha coincide con el neto del resumen (no inflado ×nº piezas).
    # net por pieza: 500 + 1000 + 302 + (303+303+500+500) = 3408 mm = 3.41 m.
    net_summary = data["edgeBandingsSummary"][0]["netLinearM"]
    assert net_summary == pytest.approx(3.41)
    stats = data["layouts"][0]["statistics"]
    assert stats["edgeBandingLinearM"] == pytest.approx(net_summary)
    assert data["totalEdgeBandingLinearM"] == pytest.approx(net_summary)


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
            "materials": _materials(b["id"]),
            "requirements": [_requirement(eb["id"], ["left", "right"])],
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
            "materials": _materials(b["id"]),
            "requirements": [
                _requirement(eb1["id"], ["top", "bottom"]),
                _requirement(eb2["id"], ["left", "right"], height=1000),
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
            "materials": _materials(b["id"]),
            "requirements": [
                {
                    "priority": 0,
                    "height": 400,
                    "width": 600,
                    "quantity": 1,
                    "materialKey": "b1",
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
            "materials": _materials(b["id"]),
            "requirements": [_requirement(99999, ["top"])],
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
            "materials": _materials(b["id"]),
            "requirements": [_requirement(other_board["id"], ["top"])],
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
            "materials": _materials(b["id"]),
            "requirements": [_requirement(eb["id"], ["top", "top"])],
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


def test_geometric_edges_notation_is_rotation_invariant(db_session):
    """La notación se calcula desde los lados NOMINALES, así que no cambia al rotar."""
    svc = OptimizationService(db_session)
    # top+left+right: 2 largos (left/right=alto) + 1 corto (top=ancho). Sin producto
    # en el mapa → sin band_type → sin sufijo CS/CD.
    spec = EdgeBandingSpec(
        product_id=2, sides=[EdgeSide.top, EdgeSide.left, EdgeSide.right]
    )
    assert svc._geometric_edges(spec, {}, False)["notation"] == "2L1C"
    assert svc._geometric_edges(spec, {}, True)["notation"] == "2L1C"


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
            "materials": _materials(b["id"]),
            "requirements": [
                _requirement(eb["id"], ["top", "left"], height=1000, width=2000)
            ],
        },
    )
    placed = resp.json()["data"]["layouts"][0]["placedPieces"][0]
    assert placed["rotated"] is True
    # CW: top→right, left→top ⇒ lados geométricos {top, right}.
    assert placed["edges"]["sides"] == ["top", "right"]
    assert placed["edges"]["code"] == "TAP22"


def test_placed_piece_notation_includes_band_type(client):
    """La pieza colocada lleva la notación de cantos con sufijo CS/CD del band_type."""
    c = _create_client(client)
    b = _create_board(client)
    eb = _create_edge_banding(client, band_type="Soft")

    # alto=500, ancho=1000, sin rotar: left+right = 2 largos, top = 1 corto; Soft → CS.
    req = _requirement(eb["id"], ["left", "right", "top"])
    req["canRotate"] = False
    resp = client.post(
        "/api/v1/optimize/",
        json={
            "clientId": c["id"],
            "materials": _materials(b["id"]),
            "requirements": [req],
        },
    )
    placed = resp.json()["data"]["layouts"][0]["placedPieces"][0]
    assert placed["rotated"] is False
    assert placed["edges"]["notation"] == "2L1C CS"
    # El tipo canónico viaja en la pieza colocada (diferencia suave/duro en el diagrama).
    # ``edges`` es un dict crudo → la clave se serializa tal cual (snake_case).
    assert placed["edges"]["band_type"] == "Soft"


# --------------------------------------------------------------------------- #
# Cobro durable en órdenes
# --------------------------------------------------------------------------- #
def _mint_order(client, db_session, payload):
    """Mintea una orden por el servicio (la creación HTTP se retiró) y la lee vía GET."""
    order = OrderService(db_session).create(OrderCreate.model_validate(payload))
    return client.get(f"/api/v1/orders/{order.id}").json()["data"]


def test_order_charges_edge_banding(client, db_session):
    c = _create_client(client)
    b = _create_board(client, price=45.5)
    eb = _create_edge_banding(client, price=2.0)

    data = _mint_order(
        client,
        db_session,
        {
            "clientId": c["id"],
            "branchId": 1,
            "materials": _materials(b["id"]),
            "requirements": [_requirement(eb["id"], ["top", "bottom"])],
        },
    )

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


def test_order_document_with_edge_banding_renders(client, db_session):
    c = _create_client(client)
    b = _create_board(client)
    eb = _create_edge_banding(client)
    order = _mint_order(
        client,
        db_session,
        {
            "clientId": c["id"],
            "branchId": 1,
            "materials": _materials(b["id"]),
            "requirements": [_requirement(eb["id"], ["top", "bottom"])],
        },
    )

    document = client.get(f"/api/v1/orders/{order['id']}/document")
    assert document.status_code == 200
    assert len(document.content) > 1000

    sheet = client.get(f"/api/v1/orders/{order['id']}/production-sheet")
    assert sheet.status_code == 200
    assert len(sheet.content) > 1000


def test_production_sheet_renders_soft_and_hard_bands(client, db_session):
    """La hoja de producción (B/N) renderiza piezas con canto suave y duro: ejercita
    el rayado del canto duro y ambas entradas de leyenda. El summary expone bandType."""
    c = _create_client(client)
    b = _create_board(client)
    soft = _create_edge_banding(client, code="TAP-SOFT", price=2.0, band_type="Soft")
    hard = _create_edge_banding(client, code="TAP-HARD", price=3.0, band_type="Hard")

    payload = {
        "clientId": c["id"],
        "branchId": 1,
        "materials": _materials(b["id"]),
        "requirements": [
            _requirement(soft["id"], ["top", "bottom"]),
            _requirement(hard["id"], ["left", "right"]),
        ],
    }

    # El resumen de tapacantos expone el tipo (campo Pydantic → camelCase ``bandType``).
    summary = client.post("/api/v1/optimize/", json=payload).json()["data"][
        "edgeBandingsSummary"
    ]
    by_code = {entry["productCode"]: entry for entry in summary}
    assert by_code["TAP-SOFT"]["bandType"] == "Soft"
    assert by_code["TAP-HARD"]["bandType"] == "Hard"

    order = _mint_order(client, db_session, payload)
    sheet = client.get(f"/api/v1/orders/{order['id']}/production-sheet")
    assert sheet.status_code == 200
    assert len(sheet.content) > 1000
