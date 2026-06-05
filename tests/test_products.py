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


# --- Emparejamiento tablero -> tapacanto coordinado --------------------------


def _seed_board(client, code, name, thickness):
    return client.post(
        "/api/v1/products/",
        json={
            "type": "board",
            "code": code,
            "name": name,
            "price": 50.0,
            "attributes": {"height": 2800, "width": 2070, "thickness": thickness},
        },
    ).json()["data"]


def _seed_edge(client, code, name, band_type, thickness, width, color):
    return client.post(
        "/api/v1/products/",
        json={
            "type": "edge_banding",
            "code": code,
            "name": name,
            "price": 12.0,
            "attributes": {
                "bandType": band_type,
                "thickness": thickness,
                "width": width,
                "color": color,
            },
        },
    ).json()["data"]


def _seed_cashmere_catalog(client):
    """Tablero Cashmere 15 y 36 + sus tapacantos coordinados (estilo seed real)."""
    _seed_board(client, "MDP-SL-CSH-15", "MDP 15mm Cashmere", 15)
    _seed_board(client, "MDP-SL-CSH-36", "MDP 36mm Cashmere", 36)
    _seed_edge(
        client,
        "TAP-SL-CSH-045",
        "Tapacanto Cashmere Suave 0.45x19mm",
        "Soft",
        0.45,
        19,
        "Cashmere",
    )
    _seed_edge(
        client,
        "TAP-SL-CSH-100",
        "Tapacanto Cashmere Duro 1x40mm",
        "Hard",
        1.0,
        40,
        "Cashmere",
    )
    _seed_edge(
        client,
        "TAP-SL-CSH-150",
        "Tapacanto Cashmere Duro 1.5x19mm",
        "Hard",
        1.5,
        19,
        "Cashmere",
    )


def test_edge_bandings_for_15mm_board(client):
    _seed_cashmere_catalog(client)
    board = client.get("/api/v1/products/code/MDP-SL-CSH-15").json()["data"]

    resp = client.get(f"/api/v1/products/{board['id']}/edge-bandings")
    assert resp.status_code == 200
    bands = resp.json()["data"]
    # 15mm -> ancho 19: Soft 0.45 y Hard 1.5 (ordenados por grosor)
    assert [b["attributes"]["width"] for b in bands] == [19, 19]
    assert [b["attributes"]["bandType"] for b in bands] == ["Soft", "Hard"]

    # El enum BandType acepta la entrada sin distinguir mayúsculas ("soft") y el
    # alias en español ("suave"), ambos normalizados al valor canónico inglés.
    for value in ("soft", "suave"):
        soft = client.get(
            f"/api/v1/products/{board['id']}/edge-bandings",
            params={"band_type": value},
        ).json()["data"]
        assert len(soft) == 1
        assert soft[0]["code"] == "TAP-SL-CSH-045"


def test_edge_bandings_for_36mm_board_only_hard(client):
    _seed_cashmere_catalog(client)
    board = client.get("/api/v1/products/code/MDP-SL-CSH-36").json()["data"]

    bands = client.get(f"/api/v1/products/{board['id']}/edge-bandings").json()["data"]
    # 36mm -> ancho 40: solo existe el Duro 1.0x40
    assert len(bands) == 1
    assert bands[0]["code"] == "TAP-SL-CSH-100"
    assert bands[0]["attributes"]["width"] == 40

    # No hay canto suave (Soft) para 36mm: hueco real del catálogo -> lista vacía
    soft = client.get(
        f"/api/v1/products/{board['id']}/edge-bandings", params={"band_type": "Soft"}
    ).json()["data"]
    assert soft == []


def test_edge_bandings_excludes_other_designs(client):
    """No debe traer tapacantos de otro diseño aunque compartan tokens de nombre."""
    _seed_cashmere_catalog(client)
    # Otro diseño con nombre que comparte token pero distinto code (abreviatura)
    _seed_board(client, "MDP-RO-BRD-15", "MDP 15mm Barroco Dorado", 15)
    _seed_edge(
        client,
        "TAP-RO-BRR-045",
        "Tapacanto Barroco Ristretto Suave",
        "Soft",
        0.45,
        19,
        "Roble Barroco Ristretto",
    )
    board = client.get("/api/v1/products/code/MDP-RO-BRD-15").json()["data"]

    bands = client.get(f"/api/v1/products/{board['id']}/edge-bandings").json()["data"]
    # BRD no tiene tapacanto coordinado sembrado; BRR no debe colarse
    assert bands == []


def test_edge_bandings_invalid_band_type_returns_422(client):
    """El query param está cerrado al enum BandType: un valor fuera de él falla."""
    _seed_cashmere_catalog(client)
    board = client.get("/api/v1/products/code/MDP-SL-CSH-15").json()["data"]
    resp = client.get(
        f"/api/v1/products/{board['id']}/edge-bandings",
        params={"band_type": "Medio"},
    )
    assert resp.status_code == 422


def test_edge_banding_invalid_band_type_on_create_returns_422(client):
    """El atributo band_type también queda cerrado al enum al crear el producto."""
    resp = client.post(
        "/api/v1/products/",
        json={
            "type": "edge_banding",
            "code": "TAP-XX-YY-045",
            "name": "Tapacanto inválido",
            "price": 1.0,
            "attributes": {"bandType": "Medio", "thickness": 0.45, "width": 19},
        },
    )
    assert resp.status_code == 422


def test_edge_bandings_board_not_found(client):
    assert client.get("/api/v1/products/999999/edge-bandings").status_code == 404


def test_edge_bandings_for_non_board_returns_business_rule_error(client):
    _seed_cashmere_catalog(client)
    edge = client.get("/api/v1/products/code/TAP-SL-CSH-045").json()["data"]

    resp = client.get(f"/api/v1/products/{edge['id']}/edge-bandings")
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["code"] == "BUSINESS_RULE_ERROR"
