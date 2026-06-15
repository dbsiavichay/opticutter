"""Tests del módulo optimization_drafts (CRUD vía CRUDService + rutas finas)."""

# Estado de formulario tal cual lo enviaría el frontend, con una pieza a medio
# llenar (width vacío): el backend debe persistirlo sin validar su forma interna.
FORM_PAYLOAD = {
    "materials": [
        {"uid": "mat-0-abc", "source": "catalog", "boardId": "12"},
        {
            "uid": "mat-1-def",
            "source": "manual",
            "label": "Retazo",
            "height": 2400,
            "width": 1200,
            "thickness": 18,
        },
    ],
    "requirements": [
        {"materialUid": "mat-0-abc", "height": 720, "width": 400, "quantity": 2},
        {"materialUid": "mat-0-abc", "height": 500, "width": "", "quantity": 1},
    ],
}


def _payload(name="Cocina Pérez", payload=None, client_id=None):
    body = {"name": name, "payload": payload if payload is not None else FORM_PAYLOAD}
    if client_id is not None:
        body["clientId"] = client_id
    return body


def _make_client(client, identifier="0991112233"):
    return client.post(
        "/api/v1/clients/",
        json={"identifier": identifier, "firstName": "Ada"},
    ).json()["data"]


def test_create_and_get_draft_roundtrips_payload(client):
    """El detalle devuelve el ``payload`` idéntico, incluidas filas incompletas."""
    resp = client.post("/api/v1/optimization-drafts/", json=_payload())
    assert resp.status_code == 201
    created = resp.json()["data"]
    assert created["name"] == "Cocina Pérez"
    assert created["clientId"] is None
    assert "id" in created
    assert "createdAt" in created and "updatedAt" in created

    got = client.get(f"/api/v1/optimization-drafts/{created['id']}")
    assert got.status_code == 200
    data = got.json()["data"]
    assert data["id"] == created["id"]
    # El bag JSON se conserva tal cual (incluida la pieza con width vacío).
    assert data["payload"] == FORM_PAYLOAD


def test_create_draft_with_client(client):
    created_client = _make_client(client)
    resp = client.post(
        "/api/v1/optimization-drafts/",
        json=_payload(client_id=created_client["id"]),
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["clientId"] == created_client["id"]


def test_create_draft_requires_name_and_payload(client):
    assert (
        client.post(
            "/api/v1/optimization-drafts/", json={"payload": FORM_PAYLOAD}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/optimization-drafts/", json={"name": "", "payload": FORM_PAYLOAD}
        ).status_code
        == 422
    )
    assert (
        client.post("/api/v1/optimization-drafts/", json={"name": "x"}).status_code
        == 422
    )


def test_list_drafts_omits_payload_and_paginates(client):
    client.post("/api/v1/optimization-drafts/", json=_payload(name="A"))
    client.post("/api/v1/optimization-drafts/", json=_payload(name="B"))

    listed = client.get("/api/v1/optimization-drafts/")
    assert listed.status_code == 200
    body = listed.json()
    assert len(body["data"]) == 2
    assert body["meta"]["pagination"]["total"] == 2
    # El resumen es liviano: no expone el payload.
    assert all("payload" not in item for item in body["data"])
    assert {item["name"] for item in body["data"]} == {"A", "B"}

    paged = client.get("/api/v1/optimization-drafts/", params={"limit": 1, "offset": 0})
    assert len(paged.json()["data"]) == 1
    assert paged.json()["meta"]["pagination"]["total"] == 2


def test_update_draft_overwrites_partially(client):
    created = client.post("/api/v1/optimization-drafts/", json=_payload()).json()[
        "data"
    ]

    # Solo el nombre: el payload no se toca.
    renamed = client.put(
        f"/api/v1/optimization-drafts/{created['id']}", json={"name": "Cocina v2"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["data"]["name"] == "Cocina v2"
    assert renamed.json()["data"]["payload"] == FORM_PAYLOAD

    # Solo el payload: el nombre se conserva.
    new_payload = {"materials": [], "requirements": []}
    repayloaded = client.put(
        f"/api/v1/optimization-drafts/{created['id']}", json={"payload": new_payload}
    )
    assert repayloaded.status_code == 200
    assert repayloaded.json()["data"]["name"] == "Cocina v2"
    assert repayloaded.json()["data"]["payload"] == new_payload


def test_get_missing_draft_returns_404(client):
    resp = client.get("/api/v1/optimization-drafts/999999")
    assert resp.status_code == 404
    assert resp.json()["errors"][0]["code"] == "NOT_FOUND"


def test_update_missing_draft_returns_404(client):
    resp = client.put("/api/v1/optimization-drafts/999999", json={"name": "Nope"})
    assert resp.status_code == 404


def test_delete_draft(client):
    created = client.post("/api/v1/optimization-drafts/", json=_payload()).json()[
        "data"
    ]
    deleted = client.delete(f"/api/v1/optimization-drafts/{created['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/optimization-drafts/{created['id']}").status_code == 404
    assert (
        client.delete(f"/api/v1/optimization-drafts/{created['id']}").status_code == 404
    )
