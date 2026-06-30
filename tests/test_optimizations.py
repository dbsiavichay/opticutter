"""Tests del módulo optimizations: flujo de optimize (geometría + costos)."""

import pytest

from src.modules.optimizations.schemas import OptimizeRequest
from src.modules.optimizations.service import OptimizationService
from src.shared.exceptions import ValidationError


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
        "materials": [{"key": "b1", "source": "catalog", "productId": product_id}],
        "requirements": [
            {
                "priority": 0,
                "height": 400,
                "width": 600,
                "quantity": 2,
                "materialKey": "b1",
                "label": "Puerta",
                "canRotate": True,
            }
        ],
    }


def _full_board_payload(client_id, product_id, quantity=2):
    """Job que exige tablero(s) completo(s): pieza con ambos lados > medio ancho (610)."""
    return {
        "clientId": client_id,
        "materials": [{"key": "b1", "source": "catalog", "productId": product_id}],
        "requirements": [
            {
                "priority": 0,
                "height": 800,
                "width": 700,
                "quantity": quantity,
                "materialKey": "b1",
                "label": "Costado",
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
    assert layout["material"]["materialKey"] == "b1"
    assert layout["material"]["sheetNumber"] == 1
    assert "efficiency" in layout["statistics"]
    assert layout["placedPieces"][0]["originalWidth"] == 600
    # Cortes de guillotina expuestos para dibujar las líneas de sierra.
    assert layout["cuts"], "colocar piezas genera recorridos de sierra"
    assert set(layout["cuts"][0]) == {"x", "y", "length", "isHorizontal"}


def test_optimize_reports_cut_linear_meters(client):
    """La respuesta expone metros de corte por plancha y el total general (= suma)."""
    created_client = _create_client(client)
    created_board = _create_board(client)

    resp = client.post(
        "/api/v1/optimize/",
        json=_optimize_payload(created_client["id"], created_board["id"]),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["totalCutLinearM"] > 0
    assert "totalEdgeBandingLinearM" in data

    stats = data["layouts"][0]["statistics"]
    assert stats["cutLinearM"] > 0
    assert "edgeBandingLinearM" in stats

    total_sheets = sum(lay["statistics"]["cutLinearM"] for lay in data["layouts"])
    assert data["totalCutLinearM"] == pytest.approx(total_sheets, abs=0.02)


def test_carrier_exposes_linear_meter_totals():
    """``from_payload`` expone los totales nuevos; un payload viejo cae a 0.0."""
    from src.modules.optimizations.carrier import ProformaCarrier

    carrier = ProformaCarrier.from_payload(
        {"total_cut_linear_m": 12.5, "total_edge_banding_linear_m": 3.2},
        client=None,
        reference="OPT-x",
    )
    assert carrier.total_cut_linear_m == 12.5
    assert carrier.total_edge_banding_linear_m == 3.2

    legacy = ProformaCarrier.from_payload({}, client=None, reference="OPT-y")
    assert legacy.total_cut_linear_m == 0.0
    assert legacy.total_edge_banding_linear_m == 0.0


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


def test_optimize_strategy_changes_hash_and_is_echoed(client):
    """La heurística `strategy` afecta el hash (cache key distinta) y se refleja.

    Omitirla equivale a `default`; pasar `longOffcuts` produce otro hash para que
    no colisione en caché con el acomodo por defecto.
    """
    created_client = _create_client(client)
    created_board = _create_board(client)

    base = _optimize_payload(created_client["id"], created_board["id"])
    default_resp = client.post("/api/v1/optimize/", json=base).json()["data"]

    explicit_default = client.post(
        "/api/v1/optimize/", json={**base, "strategy": "default"}
    ).json()["data"]

    long_off = client.post(
        "/api/v1/optimize/", json={**base, "strategy": "longOffcuts"}
    ).json()["data"]

    # Echo de la estrategia aplicada.
    assert default_resp["strategy"] == "default"
    assert long_off["strategy"] == "longOffcuts"
    # Omitir == default explícito (mismo hash de caché).
    assert explicit_default["optimizationHash"] == default_resp["optimizationHash"]
    # Otra estrategia => otro hash (no colisiona la caché).
    assert long_off["optimizationHash"] != default_resp["optimizationHash"]


def test_optimize_computes_total_boards_cost(client):
    """El costo total debe ser nº de tableros usados * precio del tablero."""
    created_client = _create_client(client)
    created_board = _create_board(client)

    resp = client.post(
        "/api/v1/optimize/",
        json=_full_board_payload(created_client["id"], created_board["id"]),
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


def test_optimize_deduplicates_identical_patterns(client):
    """Varias hojas con el mismo patrón se colapsan en un grupo con su conteo."""
    created_client = _create_client(client)
    created_board = _create_board(client)

    # Una pieza grande (1700×670) entra una sola vez por tablero → 5 hojas idénticas.
    payload = {
        "clientId": created_client["id"],
        "materials": [
            {"key": "b1", "source": "catalog", "productId": created_board["id"]}
        ],
        "requirements": [
            {
                "priority": 0,
                "height": 1700,
                "width": 670,
                "quantity": 5,
                "materialKey": "b1",
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
    assert group["materialKey"] == "b1"
    assert group["layout"]["material"]["materialKey"] == "b1"


def test_optimize_includes_materials_summary(client):
    """materials_summary agrupa por tipo de tablero con código, cantidad y costo."""
    created_client = _create_client(client)
    created_board = _create_board(client, code="MEL18")

    resp = client.post(
        "/api/v1/optimize/",
        json=_full_board_payload(created_client["id"], created_board["id"]),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]

    summary = data.get("materialsSummary")
    assert summary is not None and len(summary) == 1

    entry = summary[0]
    assert entry["materialKey"] == "b1"
    assert entry["source"] == "catalog"
    assert entry["productCode"] == "MEL18"
    assert entry["productName"] == "Melamina MEL18"
    assert entry["halfBoard"] is False
    assert entry["count"] == data["totalBoardsUsed"]
    assert entry["totalCost"] == pytest.approx(data["totalBoardsCost"])


# --------------------------------------------------------------------------- #
# Material agnóstico al origen (catálogo / manual / retazo / mixto)
# --------------------------------------------------------------------------- #
def _manual_material(key="m1", height=2000, width=1000, thickness=18, cost=30.0):
    return {
        "key": key,
        "source": "manual",
        "height": height,
        "width": width,
        "thickness": thickness,
        "costPerUnit": cost,
        "label": "Sobrante taller",
    }


def test_optimize_with_manual_material(client):
    """Una medida manual (sin catálogo) se optimiza por dimensiones y costo."""
    c = _create_client(client)
    payload = {
        "clientId": c["id"],
        "materials": [_manual_material(cost=30.0)],
        "requirements": [
            {
                "priority": 0,
                "height": 400,
                "width": 600,
                "quantity": 2,
                "materialKey": "m1",
                "label": "Puerta",
                "canRotate": True,
            }
        ],
    }
    resp = client.post("/api/v1/optimize/", json=payload)
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["totalBoardsUsed"] >= 1
    assert data["layouts"][0]["material"]["materialKey"] == "m1"

    entry = data["materialsSummary"][0]
    assert entry["materialKey"] == "m1"
    assert entry["source"] == "manual"
    assert entry["productId"] is None
    assert entry["costPerUnit"] == 30.0
    assert entry["totalCost"] == pytest.approx(data["totalBoardsUsed"] * 30.0)


def test_optimize_with_company_offcut_material(client):
    """Un retazo de empresa se trata igual: dimensiones inline, sin producto."""
    c = _create_client(client)
    payload = {
        "clientId": c["id"],
        "materials": [
            {
                "key": "r1",
                "source": "companyOffcut",
                "height": 1200,
                "width": 600,
                "thickness": 15,
                "costPerUnit": 0,
            }
        ],
        "requirements": [
            {
                "priority": 0,
                "height": 400,
                "width": 300,
                "quantity": 1,
                "materialKey": "r1",
                "canRotate": True,
            }
        ],
    }
    resp = client.post("/api/v1/optimize/", json=payload)
    assert resp.status_code == 200
    entry = resp.json()["data"]["materialsSummary"][0]
    assert entry["source"] == "companyOffcut"
    assert entry["productId"] is None
    # Sin label ni código de catálogo cae a la key / dimensiones legibles.
    assert entry["productCode"] == "r1"
    assert entry["productName"] == "600×1200"


def test_optimize_mixed_catalog_and_manual(client):
    """Catálogo y manual conviven en una misma optimización (stock heterogéneo)."""
    c = _create_client(client)
    board = _create_board(client)
    payload = {
        "clientId": c["id"],
        "materials": [
            {"key": "b1", "source": "catalog", "productId": board["id"]},
            _manual_material(key="m1", cost=20.0),
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
                "width": 300,
                "quantity": 1,
                "materialKey": "m1",
            },
        ],
    }
    resp = client.post("/api/v1/optimize/", json=payload)
    assert resp.status_code == 200
    data = resp.json()["data"]

    by_key = {e["materialKey"]: e for e in data["materialsSummary"]}
    assert set(by_key) == {"b1", "m1"}
    assert by_key["b1"]["source"] == "catalog"
    assert by_key["b1"]["productId"] == board["id"]
    assert by_key["m1"]["source"] == "manual"
    assert by_key["m1"]["productId"] is None


def test_optimize_unknown_material_key_returns_422(client):
    """Un requerimiento que referencia una key inexistente es 422 (validación)."""
    c = _create_client(client)
    board = _create_board(client)
    payload = {
        "clientId": c["id"],
        "materials": [{"key": "b1", "source": "catalog", "productId": board["id"]}],
        "requirements": [
            {
                "priority": 0,
                "height": 400,
                "width": 600,
                "quantity": 1,
                "materialKey": "zzz",
            }
        ],
    }
    resp = client.post("/api/v1/optimize/", json=payload)
    assert resp.status_code == 422


def test_optimize_manual_material_hash_is_deterministic(client):
    """Dos peticiones idénticas con material manual comparten hash (cache-first)."""
    c = _create_client(client)
    payload = {
        "clientId": c["id"],
        "materials": [_manual_material()],
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
    first = client.post("/api/v1/optimize/", json=payload).json()["data"]
    second = client.post("/api/v1/optimize/", json=payload).json()["data"]
    assert first["optimizationHash"] == second["optimizationHash"]


def test_material_resolver_resolves_each_source(db_session):
    """El resolver traduce catálogo y fuentes inline a un ResolvedMaterial uniforme."""
    from src.modules.optimizations.materials import MaterialResolver
    from src.modules.optimizations.schemas import (
        CatalogMaterialInput,
        InlineMaterialInput,
        MaterialSource,
    )
    from src.modules.products.model import ProductModel, ProductType

    board = ProductModel(
        type=ProductType.BOARD.value,
        code="MELX",
        name="Melamina X",
        price=50.0,
        attributes={"height": 2440, "width": 1220, "thickness": 18},
    )
    db_session.add(board)
    db_session.commit()

    resolver = MaterialResolver(db_session)

    catalog = resolver.resolve(
        CatalogMaterialInput(
            key="b1", source=MaterialSource.catalog, product_id=board.id
        )
    )
    assert catalog.is_catalog
    assert (catalog.width, catalog.height, catalog.thickness) == (1220, 2440, 18)
    assert catalog.cost_per_unit == 50.0
    assert catalog.product_id == board.id and catalog.code == "MELX"

    manual = resolver.resolve(
        InlineMaterialInput(
            key="m1",
            source=MaterialSource.manual,
            height=2000,
            width=1000,
            thickness=15,
            cost_per_unit=12.5,
            label="Sobrante",
        )
    )
    assert not manual.is_catalog
    assert manual.product_id is None and manual.code is None
    assert manual.name == "Sobrante" and manual.cost_per_unit == 12.5
    assert manual.to_dict()["source"] == "manual"


# --- Medios tableros (cobro a la mitad) ------------------------------------


def _full_layouts(pieces, width=1220, height=2440, cost=45.5):
    """Optimiza ``pieces`` sobre un tablero completo y devuelve los layouts."""
    from src.cutting import (
        CuttingParameters,
        Material,
        MultiSheetGuillotineOptimizer,
        PackingStrategy,
    )

    template = Material(
        id="b1", width=width, height=height, thickness=18, cost_per_unit=cost
    )
    optimizer = MultiSheetGuillotineOptimizer(
        material_template=template,
        cutting_params=CuttingParameters(kerf=5),
        strategy=PackingStrategy.MAX_EFFICIENCY,
    )
    return optimizer.optimize(pieces)[0]


def _resolved(source="catalog", product_id=1, width=1220, height=2440, cost=45.5):
    from src.modules.optimizations.materials import ResolvedMaterial

    return {
        "b1": ResolvedMaterial(
            key="b1",
            width=width,
            height=height,
            thickness=18,
            cost_per_unit=cost,
            source=source,
            product_id=product_id,
            code="MEL18",
            name="Melamina",
        )
    }


def test_apply_half_boards_downgrades_fitting_board():
    """Una plancha de catálogo cuyo contenido cabe en medio pasa a medio tablero."""
    from src.cutting import CuttingParameters, PackingStrategy, Piece
    from src.modules.optimizations.half_boards import apply_half_boards

    layouts = _full_layouts([Piece(id="p1", width=300, height=300)])
    results = [({}, {}, layouts)]
    apply_half_boards(
        results, _resolved(), CuttingParameters(kerf=5), PackingStrategy.MAX_EFFICIENCY
    )

    out = results[0][2]
    assert len(out) == 1
    board = out[0]
    assert board.material.half_board is True
    assert board.material.width == 610  # ancho/2, largo intacto
    assert board.material.height == 2440
    assert board.material.cost_per_unit == 22.75  # precio/2
    assert len(board.placed_pieces) == 1  # no se pierden piezas


def test_apply_half_boards_keeps_wide_board_full():
    """Una pieza más ancha que medio (en ambos ejes) mantiene el tablero completo."""
    from src.cutting import CuttingParameters, PackingStrategy, Piece
    from src.modules.optimizations.half_boards import apply_half_boards

    # 700×800: ambos lados > 610, no entra en un medio (610 de ancho).
    layouts = _full_layouts([Piece(id="p1", width=700, height=800)])
    results = [({}, {}, layouts)]
    apply_half_boards(
        results, _resolved(), CuttingParameters(kerf=5), PackingStrategy.MAX_EFFICIENCY
    )

    board = results[0][2][0]
    assert board.material.half_board is False
    assert board.material.width == 1220
    assert board.material.cost_per_unit == 45.5


def test_apply_half_boards_skips_non_catalog():
    """Retazos/manual no se vuelven medio aunque su contenido quepa (van a costo)."""
    from src.cutting import CuttingParameters, PackingStrategy, Piece
    from src.modules.optimizations.half_boards import apply_half_boards

    layouts = _full_layouts([Piece(id="p1", width=300, height=300)])
    results = [({}, {}, layouts)]
    apply_half_boards(
        results,
        _resolved(source="manual", product_id=None),
        CuttingParameters(kerf=5),
        PackingStrategy.MAX_EFFICIENCY,
    )

    board = results[0][2][0]
    assert board.material.half_board is False
    assert board.material.width == 1220


def test_optimize_charges_half_board_for_sparse_job(client):
    """Un trabajo chico de catálogo se cobra como medio tablero (precio/2)."""
    created_client = _create_client(client)
    created_board = _create_board(client)  # 2440×1220, precio 45.5

    payload = {
        "clientId": created_client["id"],
        "materials": [
            {"key": "b1", "source": "catalog", "productId": created_board["id"]}
        ],
        "requirements": [
            {
                "priority": 0,
                "height": 300,
                "width": 300,
                "quantity": 1,
                "materialKey": "b1",
                "label": "Repisa",
                "canRotate": True,
            }
        ],
    }
    resp = client.post("/api/v1/optimize/", json=payload)
    assert resp.status_code == 200
    data = resp.json()["data"]

    summary = data["materialsSummary"]
    assert len(summary) == 1
    assert summary[0]["halfBoard"] is True
    assert summary[0]["costPerUnit"] == 22.75
    assert summary[0]["productName"].endswith("(medio tablero)")
    assert data["totalBoardsCost"] == 22.75

    material = data["layouts"][0]["material"]
    assert material["halfBoard"] is True
    assert material["width"] == 610


def test_optimize_keeps_full_board_for_wide_job(client):
    """Un trabajo con una pieza ancha se cobra como tablero completo."""
    created_client = _create_client(client)
    created_board = _create_board(client)

    payload = {
        "clientId": created_client["id"],
        "materials": [
            {"key": "b1", "source": "catalog", "productId": created_board["id"]}
        ],
        "requirements": [
            {
                "priority": 0,
                "height": 800,
                "width": 700,
                "quantity": 1,
                "materialKey": "b1",
                "label": "Costado",
                "canRotate": True,
            }
        ],
    }
    data = client.post("/api/v1/optimize/", json=payload).json()["data"]
    summary = data["materialsSummary"]
    assert len(summary) == 1
    assert summary[0]["halfBoard"] is False
    assert summary[0]["costPerUnit"] == 45.5
    assert data["totalBoardsCost"] == 45.5
