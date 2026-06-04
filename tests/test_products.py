"""Tests del módulo products (catálogo multi-tipo: CRUD + validación por tipo)."""


def _board_payload(code="MEL18", name="Melamina 18mm"):
    return {
        "type": "board",
        "code": code,
        "name": name,
        "description": "Tablero estándar",
        "price": 45.5,
        "attributes": {
            "height": 2440,
            "width": 1220,
            "thickness": 18,
            "grainDirection": "v",
        },
    }


def _edge_banding_payload(code="TAP22", name="Tapacanto PVC 22mm"):
    return {
        "type": "edge_banding",
        "code": code,
        "name": name,
        "price": 0.8,
        "attributes": {"length": 50000, "width": 22, "thickness": 1, "color": "blanco"},
    }


def test_create_and_get_board_product(client):
    resp = client.post("/api/v1/products/", json=_board_payload())
    assert resp.status_code == 201
    created = resp.json()["data"]
    assert created["type"] == "board"
    assert created["code"] == "MEL18"
    assert created["price"] == 45.5
    # Los atributos se persisten/devuelven en la forma canónica camelCase.
    assert created["attributes"]["height"] == 2440
    assert created["attributes"]["grainDirection"] == "v"

    got = client.get(f"/api/v1/products/{created['id']}")
    assert got.status_code == 200
    assert got.json()["data"]["name"] == "Melamina 18mm"


def test_create_edge_banding_product(client):
    resp = client.post("/api/v1/products/", json=_edge_banding_payload())
    assert resp.status_code == 201
    created = resp.json()["data"]
    assert created["type"] == "edge_banding"
    assert created["attributes"]["length"] == 50000
    assert created["attributes"]["color"] == "blanco"


def test_board_missing_required_attribute_returns_422(client):
    """El discriminador valida los ``attributes`` según el tipo (board sin alto)."""
    payload = _board_payload()
    del payload["attributes"]["height"]
    resp = client.post("/api/v1/products/", json=payload)
    assert resp.status_code == 422
    errors = resp.json()["errors"]
    assert errors[0]["code"] == "VALIDATION_ERROR"
    assert any(e["field"] and e["field"].startswith("body.") for e in errors)


def test_unknown_product_type_returns_422(client):
    payload = _board_payload()
    payload["type"] = "hammer"
    assert client.post("/api/v1/products/", json=payload).status_code == 422


def test_create_duplicate_code_returns_409(client):
    client.post("/api/v1/products/", json=_board_payload())
    dup = client.post("/api/v1/products/", json=_board_payload(name="Otro nombre"))
    assert dup.status_code == 409
    error = dup.json()["errors"][0]
    assert error["code"] == "CONFLICT"
    assert error["message"] == "El código del producto ya existe"


def test_create_duplicate_name_returns_409(client):
    client.post("/api/v1/products/", json=_board_payload())
    dup = client.post("/api/v1/products/", json=_board_payload(code="MEL15"))
    assert dup.status_code == 409
    assert dup.json()["errors"][0]["message"] == "El nombre del producto ya existe"


def test_get_missing_product_returns_404(client):
    assert client.get("/api/v1/products/999999").status_code == 404


def test_list_search_and_filter_by_type(client):
    client.post("/api/v1/products/", json=_board_payload(code="MEL18", name="Blanco"))
    client.post("/api/v1/products/", json=_board_payload(code="MDF15", name="Roble"))
    client.post("/api/v1/products/", json=_edge_banding_payload())

    listed = client.get("/api/v1/products/")
    body = listed.json()
    assert body["meta"]["pagination"]["total"] == 3

    boards = client.get("/api/v1/products/", params={"type": "board"}).json()
    assert boards["meta"]["pagination"]["total"] == 2
    assert all(p["type"] == "board" for p in boards["data"])

    found = client.get(
        "/api/v1/products/", params={"type": "board", "search": "Roble"}
    ).json()
    assert [p["code"] for p in found["data"]] == ["MDF15"]
    assert found["meta"]["pagination"]["total"] == 1


def test_get_product_by_code(client):
    client.post("/api/v1/products/", json=_board_payload(code="ABC123"))
    ok = client.get("/api/v1/products/code/ABC123")
    assert ok.status_code == 200
    assert ok.json()["data"]["code"] == "ABC123"
    assert client.get("/api/v1/products/code/NOPE").status_code == 404


def test_update_common_fields_and_attributes(client):
    created = client.post("/api/v1/products/", json=_board_payload()).json()["data"]

    upd = client.put(
        f"/api/v1/products/{created['id']}",
        json={
            "price": 60.0,
            "attributes": {"height": 2500, "width": 1220, "thickness": 18},
        },
    )
    assert upd.status_code == 200
    data = upd.json()["data"]
    assert data["price"] == 60.0
    assert data["attributes"]["height"] == 2500


def test_delete_product(client):
    created = client.post("/api/v1/products/", json=_board_payload()).json()["data"]
    assert client.delete(f"/api/v1/products/{created['id']}").status_code == 204
    assert client.get(f"/api/v1/products/{created['id']}").status_code == 404
