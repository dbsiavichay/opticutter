"""Tests del módulo boards (CRUD vía CRUDService + rutas finas)."""


def _payload(code="MEL18", name="Melamina 18mm"):
    return {
        "code": code,
        "name": name,
        "description": "Tablero estándar",
        "height": 2440,
        "width": 1220,
        "thickness": 18,
        "grainDirection": "v",
        "price": 45.5,
    }


def test_create_and_get_board(client):
    resp = client.post("/api/v1/boards/", json=_payload())
    assert resp.status_code == 201
    created = resp.json()["data"]
    assert created["code"] == "MEL18"
    assert created["price"] == 45.5

    got = client.get(f"/api/v1/boards/{created['id']}")
    assert got.status_code == 200
    assert got.json()["data"]["name"] == "Melamina 18mm"


def test_create_duplicate_code_returns_409(client):
    client.post("/api/v1/boards/", json=_payload())
    dup = client.post("/api/v1/boards/", json=_payload(name="Otro nombre"))
    assert dup.status_code == 409
    error = dup.json()["errors"][0]
    assert error["code"] == "CONFLICT"
    assert error["message"] == "El código del tablero ya existe"


def test_create_duplicate_name_returns_409(client):
    client.post("/api/v1/boards/", json=_payload())
    dup = client.post("/api/v1/boards/", json=_payload(code="MEL15"))
    assert dup.status_code == 409
    assert dup.json()["errors"][0]["message"] == "El nombre del tablero ya existe"


def test_get_missing_board_returns_404(client):
    assert client.get("/api/v1/boards/999999").status_code == 404


def test_list_and_search_boards(client):
    client.post("/api/v1/boards/", json=_payload(code="MEL18", name="Blanco"))
    client.post("/api/v1/boards/", json=_payload(code="MDF15", name="Roble"))

    listed = client.get("/api/v1/boards/")
    body = listed.json()
    assert len(body["data"]) == 2
    assert body["meta"]["pagination"]["total"] == 2

    found = client.get("/api/v1/boards/", params={"search": "Roble"})
    assert [b["code"] for b in found.json()["data"]] == ["MDF15"]
    assert found.json()["meta"]["pagination"]["total"] == 1


def test_get_board_by_code(client):
    client.post("/api/v1/boards/", json=_payload(code="ABC123"))
    ok = client.get("/api/v1/boards/code/ABC123")
    assert ok.status_code == 200
    assert ok.json()["data"]["code"] == "ABC123"
    assert client.get("/api/v1/boards/code/NOPE").status_code == 404


def test_update_and_delete_board(client):
    created = client.post("/api/v1/boards/", json=_payload()).json()["data"]
    upd = client.put(f"/api/v1/boards/{created['id']}", json={"price": 60.0})
    assert upd.status_code == 200
    assert upd.json()["data"]["price"] == 60.0

    assert client.delete(f"/api/v1/boards/{created['id']}").status_code == 204
    assert client.get(f"/api/v1/boards/{created['id']}").status_code == 404
