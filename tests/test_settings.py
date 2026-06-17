"""Tests del módulo settings: configuración única persistida y editable vía API."""

from datetime import datetime

from src.shared.config import config


def _create_client(client):
    return client.post(
        "/api/v1/clients/",
        json={"identifier": "0991112233", "firstName": "Ada", "phone": "0991112233"},
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
        "branchId": 1,  # sucursal por defecto sembrada por conftest
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


# --- Parámetros de corte ------------------------------------------------------
def test_get_cutting_seeds_from_config(client):
    """El primer GET siembra la fila singleton con los defaults de ``config``."""
    resp = client.get("/api/v1/settings/cutting")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["kerf"] == config.KERF
    assert data["topTrim"] == config.TOP_TRIM
    assert data["edgeBandingWasteFactor"] == config.EDGE_BANDING_WASTE_FACTOR


def test_patch_cutting_persists_and_is_partial(client):
    """El PATCH parcial persiste solo lo enviado y no pisa el resto."""
    before = client.get("/api/v1/settings/cutting").json()["data"]

    resp = client.patch("/api/v1/settings/cutting", json={"kerf": 4.0})
    assert resp.status_code == 200
    assert resp.json()["data"]["kerf"] == 4.0

    after = client.get("/api/v1/settings/cutting").json()["data"]
    assert after["kerf"] == 4.0
    # Los demás parámetros quedan intactos.
    assert after["topTrim"] == before["topTrim"]
    assert after["rightTrim"] == before["rightTrim"]


def test_patch_cutting_rejects_negative(client):
    """Validación: los parámetros de corte no pueden ser negativos (422)."""
    assert (
        client.patch("/api/v1/settings/cutting", json={"kerf": -1}).status_code == 422
    )


def test_cutting_settings_drive_optimization(client):
    """Cambiar el kerf en BD cambia el hash de la optimización (lo usa el optimizador)."""
    created_client = _create_client(client)
    board = _create_board(client)
    payload = _optimize_payload(created_client["id"], board["id"])

    first = client.post("/api/v1/optimize/", json=payload).json()["data"]

    client.patch("/api/v1/settings/cutting", json={"kerf": 99.0})
    second = client.post("/api/v1/optimize/", json=payload).json()["data"]

    assert first["optimizationHash"] != second["optimizationHash"]


# --- Pre-órdenes (cotización mutable) -----------------------------------------
def test_get_preorders_seeds_from_config(client):
    """El primer GET siembra la sección preorders con los defaults de ``config``."""
    resp = client.get("/api/v1/settings/preorders")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["preorderValidityDays"] == config.PREORDER_VALIDITY_DAYS
    assert data["maxOpenPreordersPerClient"] == config.MAX_OPEN_PREORDERS_PER_CLIENT


def test_patch_preorders_persists_and_is_partial(client):
    """El PATCH parcial persiste solo lo enviado y no pisa el resto."""
    before = client.get("/api/v1/settings/preorders").json()["data"]

    resp = client.patch("/api/v1/settings/preorders", json={"preorderValidityDays": 30})
    assert resp.status_code == 200
    assert resp.json()["data"]["preorderValidityDays"] == 30

    after = client.get("/api/v1/settings/preorders").json()["data"]
    assert after["preorderValidityDays"] == 30
    # El tope queda intacto.
    assert after["maxOpenPreordersPerClient"] == before["maxOpenPreordersPerClient"]


def test_patch_preorders_rejects_below_one(client):
    """Validación: vigencia y tope deben ser ≥ 1 (422)."""
    assert (
        client.patch(
            "/api/v1/settings/preorders", json={"preorderValidityDays": 0}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/v1/settings/preorders", json={"maxOpenPreordersPerClient": 0}
        ).status_code
        == 422
    )


def test_preorder_validity_comes_from_settings(client):
    """La pre-orden toma su vigencia de settings (no de env): el gap = días config."""
    created_client = _create_client(client)
    board = _create_board(client)

    client.patch("/api/v1/settings/preorders", json={"preorderValidityDays": 7})
    pre = client.post(
        "/api/v1/preorders/", json=_optimize_payload(created_client["id"], board["id"])
    ).json()["data"]

    created = datetime.fromisoformat(pre["createdAt"])
    expires = datetime.fromisoformat(pre["expiresAt"])
    assert (expires - created).days == 7


# --- Datos de la empresa ------------------------------------------------------
def test_get_company_seeds_from_config(client):
    """El primer GET expone los datos de empresa sembrados desde ``config``."""
    resp = client.get("/api/v1/settings/company")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == config.COMPANY_NAME
    assert data["phone"] == config.COMPANY_PHONE
    assert isinstance(data["branches"], list)


def test_patch_company_persists(client):
    """El PATCH de empresa persiste teléfono y sucursales (lista de objetos)."""
    resp = client.patch(
        "/api/v1/settings/company",
        json={
            "phone": "0987654321",
            "branches": [{"name": "Matriz", "address": "Av. Siempre Viva 123"}],
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["phone"] == "0987654321"
    assert data["branches"] == [{"name": "Matriz", "address": "Av. Siempre Viva 123"}]

    after = client.get("/api/v1/settings/company").json()["data"]
    assert after["phone"] == "0987654321"
    assert after["branches"][0]["name"] == "Matriz"


def test_company_settings_render_in_proforma(client):
    """La proforma usa los datos de empresa vigentes en BD (membrete en vivo)."""
    created_client = _create_client(client)
    board = _create_board(client)
    optimization = client.post(
        "/api/v1/optimize/", json=_optimize_payload(created_client["id"], board["id"])
    ).json()["data"]

    client.patch("/api/v1/settings/company", json={"phone": "0999999999"})

    proforma = client.get(
        f"/api/v1/optimize/{optimization['optimizationHash']}/proforma",
        params={"clientId": created_client["id"]},
    )
    assert proforma.status_code == 200
    assert proforma.headers["content-type"] == "application/pdf"
    assert len(proforma.content) > 1000
