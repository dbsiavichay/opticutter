"""Tests del módulo clients (CRUD vía CRUDService + rutas finas)."""


def _payload(identifier="0991112233", first="Ada", last="Lovelace"):
    return {"identifier": identifier, "firstName": first, "lastName": last}


def test_create_and_get_client(client):
    resp = client.post("/api/v1/clients/", json=_payload())
    assert resp.status_code == 201
    created = resp.json()
    assert created["identifier"] == "0991112233"
    assert created["firstName"] == "Ada"
    assert "id" in created

    got = client.get(f"/api/v1/clients/{created['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == created["id"]


def test_create_duplicate_identifier_returns_409(client):
    client.post("/api/v1/clients/", json=_payload())
    dup = client.post("/api/v1/clients/", json=_payload(first="Other"))
    assert dup.status_code == 409
    assert dup.json()["detail"] == "El identificador ya existe"


def test_get_missing_client_returns_404(client):
    resp = client.get("/api/v1/clients/999999")
    assert resp.status_code == 404
    assert "no encontrado" in resp.json()["detail"]


def test_list_and_search_clients(client):
    client.post(
        "/api/v1/clients/", json=_payload(identifier="0990000001", first="Grace")
    )
    client.post(
        "/api/v1/clients/", json=_payload(identifier="0990000002", first="Alan")
    )

    listed = client.get("/api/v1/clients/")
    assert listed.status_code == 200
    assert len(listed.json()) == 2

    found = client.get("/api/v1/clients/", params={"search": "Grace"})
    assert found.status_code == 200
    names = [c["firstName"] for c in found.json()]
    assert names == ["Grace"]


def test_get_client_by_identifier(client):
    client.post("/api/v1/clients/", json=_payload(identifier="0995554433"))
    ok = client.get("/api/v1/clients/identifier/0995554433")
    assert ok.status_code == 200
    assert ok.json()["identifier"] == "0995554433"

    missing = client.get("/api/v1/clients/identifier/0000000000")
    assert missing.status_code == 404


def test_update_client(client):
    created = client.post("/api/v1/clients/", json=_payload()).json()
    resp = client.put(f"/api/v1/clients/{created['id']}", json={"firstName": "Augusta"})
    assert resp.status_code == 200
    assert resp.json()["firstName"] == "Augusta"
    assert resp.json()["lastName"] == "Lovelace"


def test_update_missing_client_returns_404(client):
    resp = client.put("/api/v1/clients/999999", json={"firstName": "Nobody"})
    assert resp.status_code == 404


def test_delete_client(client):
    created = client.post("/api/v1/clients/", json=_payload()).json()
    deleted = client.delete(f"/api/v1/clients/{created['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/clients/{created['id']}").status_code == 404
    assert client.delete(f"/api/v1/clients/{created['id']}").status_code == 404
