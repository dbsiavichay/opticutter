"""Tests for the clients module (CRUD via CRUDService + thin routes)."""


def _payload(identifier="0991112233", first="Ada", last="Lovelace"):
    return {"identifier": identifier, "firstName": first, "lastName": last}


def test_create_and_get_client(client):
    resp = client.post("/api/v1/clients/", json=_payload())
    assert resp.status_code == 201
    created = resp.json()["data"]
    assert created["identifier"] == "0991112233"
    assert created["firstName"] == "Ada"
    assert "id" in created

    got = client.get(f"/api/v1/clients/{created['id']}")
    assert got.status_code == 200
    assert got.json()["data"]["id"] == created["id"]


def test_create_duplicate_identifier_returns_409(client):
    client.post("/api/v1/clients/", json=_payload())
    dup = client.post("/api/v1/clients/", json=_payload(first="Other"))
    assert dup.status_code == 409
    assert dup.json()["errors"][0]["message"] == "El identificador ya existe"


def test_get_missing_client_returns_404(client):
    resp = client.get("/api/v1/clients/999999")
    assert resp.status_code == 404
    error = resp.json()["errors"][0]
    assert error["code"] == "NOT_FOUND"
    assert "no encontrado" in error["message"]


def test_resolve_creates_then_is_idempotent(client):
    """``POST /clients/resolve`` creates the first time, then returns the same id."""
    first = client.post("/api/v1/clients/resolve", json=_payload())
    assert first.status_code == 200
    created = first.json()["data"]
    assert created["identifier"] == "0991112233"

    second = client.post("/api/v1/clients/resolve", json=_payload(first="Ignored"))
    assert second.status_code == 200
    assert second.json()["data"]["id"] == created["id"]
    # The existing client is neither duplicated nor overwritten.
    assert second.json()["data"]["firstName"] == "Ada"
    assert len(client.get("/api/v1/clients/").json()["data"]) == 1


def test_resolve_returns_existing_created_client(client):
    """If the client already exists (created via POST /clients), resolve reuses it."""
    created = client.post("/api/v1/clients/", json=_payload()).json()["data"]
    resolved = client.post("/api/v1/clients/resolve", json=_payload())
    assert resolved.status_code == 200
    assert resolved.json()["data"]["id"] == created["id"]


def test_list_and_search_clients(client):
    client.post(
        "/api/v1/clients/", json=_payload(identifier="0990000001", first="Grace")
    )
    client.post(
        "/api/v1/clients/", json=_payload(identifier="0990000002", first="Alan")
    )

    listed = client.get("/api/v1/clients/")
    assert listed.status_code == 200
    body = listed.json()
    assert len(body["data"]) == 2
    assert body["meta"]["pagination"]["total"] == 2

    found = client.get("/api/v1/clients/", params={"search": "Grace"})
    assert found.status_code == 200
    names = [c["firstName"] for c in found.json()["data"]]
    assert names == ["Grace"]


def test_get_client_by_identifier(client):
    client.post("/api/v1/clients/", json=_payload(identifier="0995554433"))
    ok = client.get("/api/v1/clients/identifier/0995554433")
    assert ok.status_code == 200
    assert ok.json()["data"]["identifier"] == "0995554433"

    missing = client.get("/api/v1/clients/identifier/0000000000")
    assert missing.status_code == 404


def test_update_client(client):
    created = client.post("/api/v1/clients/", json=_payload()).json()["data"]
    resp = client.put(f"/api/v1/clients/{created['id']}", json={"firstName": "Augusta"})
    assert resp.status_code == 200
    assert resp.json()["data"]["firstName"] == "Augusta"
    assert resp.json()["data"]["lastName"] == "Lovelace"


def test_create_client_stores_phone_and_email(client):
    """``phone`` and ``email`` are stored and returned (email is optional)."""
    payload = {**_payload(), "phone": "0991112233", "email": "ada@example.com"}
    created = client.post("/api/v1/clients/", json=payload).json()["data"]
    assert created["phone"] == "0991112233"
    assert created["email"] == "ada@example.com"


def test_client_phone_and_email_are_optional_on_create(client):
    """The client is created fine without ``phone``/``email`` (the rule applies when quoting)."""
    created = client.post("/api/v1/clients/", json=_payload()).json()["data"]
    assert created["phone"] is None
    assert created["email"] is None


def test_update_client_phone(client):
    """``PUT`` allows registering the phone number later (used by the bot after sharing)."""
    created = client.post("/api/v1/clients/", json=_payload()).json()["data"]
    resp = client.put(f"/api/v1/clients/{created['id']}", json={"phone": "0987654321"})
    assert resp.status_code == 200
    assert resp.json()["data"]["phone"] == "0987654321"
    # Doesn't overwrite the rest of the fields.
    assert resp.json()["data"]["firstName"] == "Ada"


def test_update_missing_client_returns_404(client):
    resp = client.put("/api/v1/clients/999999", json={"firstName": "Nobody"})
    assert resp.status_code == 404


def test_delete_client(client):
    created = client.post("/api/v1/clients/", json=_payload()).json()["data"]
    deleted = client.delete(f"/api/v1/clients/{created['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/clients/{created['id']}").status_code == 404
    assert client.delete(f"/api/v1/clients/{created['id']}").status_code == 404
