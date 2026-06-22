"""Tests del aislamiento multi-sucursal.

Cubre: CRUD de sucursales (solo admin), la lectura global del admin y el vendedor
con filtro ``branchId``, el alta del vendedor con su sucursal base por defecto y
override por ``branchId``, el aislamiento del operador (atado a su sucursal), la
herencia de sucursal de la orden (hecho histórico inmutable) y el comparativo de
analítica por sucursal.

El ``client`` de conftest está autenticado como admin (su header de sesión); para
actuar como staff de una sucursal se pasa ``headers=`` por request (httpx da
precedencia al header explícito sobre el de sesión).
"""

from src.modules.orders.schemas import OrderCreate
from src.modules.orders.service import OrderService
from src.modules.users.schemas import UserCreate
from src.modules.users.service import UserService

from .test_orders import _create_board, _create_client, _order_payload

_PWD = "supersecret123"
_MATRIZ = 1  # sucursal por defecto sembrada por conftest


def _staff_headers(client, db_session, role, email, branch_id):
    """Siembra un usuario staff (rol + sucursal) y devuelve sus headers Bearer."""
    svc = UserService(db_session)
    if svc.get_by_email(email) is None:
        svc.create(
            UserCreate(
                email=email,
                password=_PWD,
                role=role,
                full_name=email,
                branch_id=branch_id,
            )
        )
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": _PWD}
    ).json()["data"]["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def _payload_no_branch(client_id, product_id, **kw):
    """``_order_payload`` sin ``branchId`` (para ejercitar el default de sucursal)."""
    payload = _order_payload(client_id, product_id, **kw)
    payload.pop("branchId", None)
    return payload


def _make_branch(client, code="NORTE", name="Sucursal Norte"):
    return client.post("/api/v1/branches/", json={"code": code, "name": name}).json()[
        "data"
    ]


def _mint_order(db_session, client_id, product_id, branch_id, width=600):
    payload = _order_payload(client_id, product_id, width=width)
    payload["branchId"] = branch_id
    return OrderService(db_session).create(OrderCreate.model_validate(payload))


# --------------------------------------------------------------- branches CRUD
def test_branch_crud_is_admin_only(client, db_session):
    seller = _staff_headers(client, db_session, "vendedor", "s@e.com", _MATRIZ)

    # Admin crea; el vendedor no puede administrar pero sí leer (poblar selectores).
    created = client.post("/api/v1/branches/", json={"code": "NORTE", "name": "Norte"})
    assert created.status_code == 201
    assert (
        client.post(
            "/api/v1/branches/", json={"code": "X", "name": "X"}, headers=seller
        ).status_code
        == 403
    )
    assert client.get("/api/v1/branches/", headers=seller).status_code == 200


def test_branch_duplicate_code_returns_409(client):
    client.post("/api/v1/branches/", json={"code": "DUP", "name": "Uno"})
    dup = client.post("/api/v1/branches/", json={"code": "DUP", "name": "Dos"})
    assert dup.status_code == 409


# ----------------------------------------------- vendedor global (lectura + alta)
def test_seller_reads_all_branches_and_create_defaults_to_base(client, db_session):
    """El vendedor es global: ve todas las sucursales y crea por defecto en la suya."""
    norte = _make_branch(client)
    a = _staff_headers(client, db_session, "vendedor", "a@e.com", _MATRIZ)
    b = _staff_headers(client, db_session, "vendedor", "b@e.com", norte["id"])
    c = _create_client(client)
    board = _create_board(client)

    # Sin branchId en el body, cada vendedor cae en su sucursal base.
    pre_a = client.post(
        "/api/v1/preorders/", json=_payload_no_branch(c["id"], board["id"]), headers=a
    ).json()["data"]
    pre_b = client.post(
        "/api/v1/preorders/", json=_payload_no_branch(c["id"], board["id"]), headers=b
    ).json()["data"]
    assert pre_a["branch"]["id"] == _MATRIZ
    assert pre_b["branch"]["id"] == norte["id"]

    # A (base Matriz) ahora VE ambas y accede a la de otra sucursal (ya no 404).
    a_ids = {
        p["id"] for p in client.get("/api/v1/preorders/", headers=a).json()["data"]
    }
    assert {pre_a["id"], pre_b["id"]} <= a_ids
    assert client.get(f"/api/v1/preorders/{pre_b['id']}", headers=a).status_code == 200

    # Puede estrechar con branchId (antes era exclusivo del admin).
    filtered = client.get(
        "/api/v1/preorders/", params={"branchId": norte["id"]}, headers=a
    ).json()["data"]
    assert [p["id"] for p in filtered] == [pre_b["id"]]


def test_seller_can_create_in_another_branch_with_branch_id(client, db_session):
    """El vendedor sobrescribe su sucursal base indicando branchId en el alta."""
    norte = _make_branch(client)
    a = _staff_headers(client, db_session, "vendedor", "a@e.com", _MATRIZ)
    c = _create_client(client)
    board = _create_board(client)

    payload = _order_payload(c["id"], board["id"])
    payload["branchId"] = norte["id"]
    pre = client.post("/api/v1/preorders/", json=payload, headers=a).json()["data"]
    assert pre["branch"]["id"] == norte["id"]


def test_admin_must_specify_branch_on_preorder_create(client, db_session):
    """El admin no tiene sucursal base: crear sin branchId es un 422."""
    c = _create_client(client)
    board = _create_board(client)
    # ``client`` está autenticado como admin (sin sucursal): falta branchId.
    resp = client.post(
        "/api/v1/preorders/", json=_payload_no_branch(c["id"], board["id"])
    )
    assert resp.status_code == 422


# ------------------------------------------------------------ órdenes aislamiento
def test_seller_sees_orders_across_branches(client, db_session):
    """El vendedor (global) ve y accede a órdenes de cualquier sucursal."""
    norte = _make_branch(client)
    a = _staff_headers(client, db_session, "vendedor", "a@e.com", _MATRIZ)
    c = _create_client(client)
    board = _create_board(client)

    order_a = _mint_order(db_session, c["id"], board["id"], _MATRIZ, width=600)
    order_b = _mint_order(db_session, c["id"], board["id"], norte["id"], width=500)
    assert order_a.branch_id == _MATRIZ and order_b.branch_id == norte["id"]

    # A (base Matriz) ve AMBAS y accede a la de Norte (ya no 404).
    a_ids = {o["id"] for o in client.get("/api/v1/orders/", headers=a).json()["data"]}
    assert {order_a.id, order_b.id} <= a_ids
    assert client.get(f"/api/v1/orders/{order_b.id}", headers=a).status_code == 200

    # El admin ve todas; ``branchId`` estrecha a una (igual que el vendedor).
    assert len(client.get("/api/v1/orders/").json()["data"]) == 2
    only_norte = client.get(
        "/api/v1/orders/", params={"branchId": norte["id"]}, headers=a
    ).json()["data"]
    assert [o["id"] for o in only_norte] == [order_b.id]


def test_orders_isolated_for_operator(client, db_session):
    """El operador sigue atado a su sucursal: no ve ni accede a las de otra."""
    norte = _make_branch(client)
    op = _staff_headers(client, db_session, "operador", "op@e.com", _MATRIZ)
    c = _create_client(client)
    board = _create_board(client)

    order_a = _mint_order(db_session, c["id"], board["id"], _MATRIZ, width=600)
    order_b = _mint_order(db_session, c["id"], board["id"], norte["id"], width=500)

    op_ids = [o["id"] for o in client.get("/api/v1/orders/", headers=op).json()["data"]]
    assert op_ids == [order_a.id]
    assert client.get(f"/api/v1/orders/{order_b.id}", headers=op).status_code == 404
    assert client.get(f"/api/v1/orders/{order_a.id}", headers=op).status_code == 200


def test_reassigning_branch_changes_operator_visibility_not_history(client, db_session):
    """Mover de sucursal a un operador cambia lo que ve, no la sucursal de las órdenes."""
    norte = _make_branch(client)
    op_email = "mover@e.com"
    op = _staff_headers(client, db_session, "operador", op_email, _MATRIZ)
    c = _create_client(client)
    board = _create_board(client)
    order_matriz = _mint_order(db_session, c["id"], board["id"], _MATRIZ)

    assert [
        o["id"] for o in client.get("/api/v1/orders/", headers=op).json()["data"]
    ] == [order_matriz.id]

    # El admin reasigna al operador a Norte; surte efecto al instante (rol/sucursal
    # se leen de la BD en cada request, no del JWT).
    svc = UserService(db_session)
    user = svc.get_by_email(op_email)
    client.put(f"/api/v1/users/{user.id}", json={"branchId": norte["id"]})

    # Ya no ve la orden de Matriz (sigue siendo de Matriz: hecho histórico).
    assert client.get("/api/v1/orders/", headers=op).json()["data"] == []
    assert order_matriz.branch_id == _MATRIZ


def test_operator_without_branch_is_forbidden(client, db_session):
    """Un operador sin sucursal asignada (estado inválido) recibe 403 al operar."""
    headers = _staff_headers(client, db_session, "operador", "huerfano@e.com", _MATRIZ)
    # Se le quita la sucursal directamente en BD (la API no permite dejarlo sin una).
    svc = UserService(db_session)
    user = svc.get_by_email("huerfano@e.com")
    user.branch_id = None
    db_session.commit()
    assert client.get("/api/v1/orders/", headers=headers).status_code == 403


# ------------------------------------------------------------------- analytics
def test_analytics_breakdown_by_branch(client, db_session):
    norte = _make_branch(client)
    c = _create_client(client)
    board = _create_board(client)
    _mint_order(db_session, c["id"], board["id"], _MATRIZ, width=600)
    _mint_order(db_session, c["id"], board["id"], norte["id"], width=500)

    rng = {"from": "2020-01-01", "to": "2999-12-31"}
    items = client.get("/api/v1/analytics/breakdown/branch", params=rng).json()["data"][
        "items"
    ]
    by_label = {i["label"]: i for i in items}
    # Densifica todas las sucursales; cada una con su conteo de órdenes.
    assert by_label["Casa Matriz"]["orderCount"] == 1
    assert by_label["Sucursal Norte"]["orderCount"] == 1

    # El filtro branchId acota el summary a una sola sucursal.
    only_norte = client.get(
        "/api/v1/analytics/summary", params={**rng, "branchId": norte["id"]}
    ).json()["data"]
    assert only_norte["orderCount"] == 1
