"""Tests de la pista PARALELA de canteado: estado inicial, solapamiento con el
corte, gate de cierre, guards, idempotencia, cola del canteador y RBAC del rol."""

from sqlalchemy.orm import Session

from src.modules.branches.model import BranchModel
from src.modules.orders.schemas import OrderCreate
from src.modules.orders.service import OrderService
from src.modules.users.schemas import UserCreate
from src.modules.users.service import UserService

_PWD = "pw-supersecret"
_BRANCH = 1  # sucursal por defecto sembrada por conftest


# --------------------------------------------------------------------------- #
# Helpers de catálogo / órdenes (mismo patrón que test_edge_banding.py)
# --------------------------------------------------------------------------- #
def _create_client(client, identifier="0991112233"):
    return client.post(
        "/api/v1/clients/",
        json={
            "identifier": identifier,
            "firstName": "Ada",
            "lastName": "Lovelace",
            "phone": identifier,
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


def _create_edge_banding(client, code="TAP22", price=2.0):
    return client.post(
        "/api/v1/products/",
        json={
            "type": "edge_banding",
            "code": code,
            "name": f"Tapacanto {code}",
            "price": price,
            "attributes": {
                "thickness": 0.45,
                "width": 22,
                "color": "Blanco",
                "length": 50000,
            },
        },
    ).json()["data"]


def _mint_order(client, db_session, payload):
    """Mintea por el servicio (la creación HTTP se retiró) y lee vía GET."""
    order = OrderService(db_session).create(OrderCreate.model_validate(payload))
    return client.get(f"/api/v1/orders/{order.id}").json()["data"]


def _order_with_banding(client, db_session, branch_id=_BRANCH, identifier="0991112233"):
    c = _create_client(client, identifier=identifier)
    suffix = identifier[-4:]  # códigos de producto únicos por orden (evita 409)
    b = _create_board(client, code=f"MEL{suffix}")
    eb = _create_edge_banding(client, code=f"TAP{suffix}")
    return _mint_order(
        client,
        db_session,
        {
            "clientId": c["id"],
            "branchId": branch_id,
            "materials": [{"key": "b1", "source": "catalog", "productId": b["id"]}],
            "requirements": [
                {
                    "priority": 0,
                    "height": 500,
                    "width": 1000,
                    "quantity": 1,
                    "materialKey": "b1",
                    "label": "Costado",
                    "canRotate": True,
                    "edgeBanding": {"productId": eb["id"], "sides": ["top", "bottom"]},
                }
            ],
        },
    )


def _order_without_banding(client, db_session):
    c = _create_client(client)
    b = _create_board(client)
    return _mint_order(
        client,
        db_session,
        {
            "clientId": c["id"],
            "branchId": _BRANCH,
            "materials": [{"key": "b1", "source": "catalog", "productId": b["id"]}],
            "requirements": [
                {
                    "priority": 0,
                    "height": 400,
                    "width": 600,
                    "quantity": 1,
                    "materialKey": "b1",
                    "label": "Puerta",
                    "canRotate": True,
                }
            ],
        },
    )


def _patch_status(client, oid, status, **kw):
    return client.patch(f"/api/v1/orders/{oid}/status", json={"status": status}, **kw)


def _patch_banding(client, oid, status, **kw):
    return client.patch(f"/api/v1/orders/{oid}/banding", json={"status": status}, **kw)


def _to_cutting(client, oid):
    assert _patch_status(client, oid, "queued").status_code == 200
    assert _patch_status(client, oid, "cutting").status_code == 200


def _cut_all_pieces(client, oid):
    plan = client.get(f"/api/v1/orders/{oid}/cutting-plan").json()["data"]
    for board in plan["boards"]:
        for piece in board["pieces"]:
            client.patch(
                f"/api/v1/orders/{oid}/cutting-plan/pieces/{piece['id']}",
                json={"cut": True},
            )


def _token_for(client, db_session, role, branch_id=_BRANCH, email=None):
    """Siembra un usuario del rol y devuelve un header Bearer (login real)."""
    email = email or f"{role}@empresa.com"
    svc = UserService(db_session)
    if svc.get_by_email(email) is None:
        svc.create(
            UserCreate(
                email=email,
                password=_PWD,
                role=role,
                full_name=role.title(),
                branch_id=None if role == "administrador" else branch_id,
            )
        )
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": _PWD}
    ).json()["data"]["accessToken"]
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# Estado inicial de la pista de canteado
# --------------------------------------------------------------------------- #
def test_order_with_edge_banding_starts_pending(client, db_session):
    order = _order_with_banding(client, db_session)
    assert order["bandingStatus"] == "pending"
    assert order["bandingStartedAt"] is None
    assert order["bandingFinishedAt"] is None


def test_order_without_edge_banding_is_not_applicable(client, db_session):
    order = _order_without_banding(client, db_session)
    assert order["bandingStatus"] == "not_applicable"


# --------------------------------------------------------------------------- #
# Solapamiento: cantear mientras el corte sigue abierto
# --------------------------------------------------------------------------- #
def test_banding_runs_in_parallel_with_cutting(client, db_session):
    """El canteado inicia mientras la orden sigue en 'cutting' (sin cerrar el corte)."""
    order = _order_with_banding(client, db_session)
    _to_cutting(client, order["id"])

    started = _patch_banding(client, order["id"], "in_progress")
    assert started.status_code == 200
    data = started.json()["data"]
    assert data["bandingStatus"] == "in_progress"
    assert data["bandingStartedAt"] is not None

    # La orden sigue en corte y el plan de corte se puede seguir marcando en paralelo.
    detail = client.get(f"/api/v1/orders/{order['id']}").json()["data"]
    assert detail["status"] == "cutting"
    assert detail["bandingStartedByLabel"]  # actor congelado


def test_banding_finish_then_order_completes(client, db_session):
    order = _order_with_banding(client, db_session)
    _to_cutting(client, order["id"])
    assert _patch_banding(client, order["id"], "in_progress").status_code == 200
    finished = _patch_banding(client, order["id"], "done")
    assert finished.status_code == 200
    assert finished.json()["data"]["bandingFinishedAt"] is not None

    # Cerrar el corte y completar: con el canteado terminado, el gate pasa.
    _cut_all_pieces(client, order["id"])
    assert _patch_status(client, order["id"], "cut").status_code == 200
    assert _patch_status(client, order["id"], "completed").status_code == 200


# --------------------------------------------------------------------------- #
# Gate de cierre: solo si lleva tapacantos
# --------------------------------------------------------------------------- #
def test_complete_blocked_until_banding_done(client, db_session):
    order = _order_with_banding(client, db_session)
    _to_cutting(client, order["id"])
    _cut_all_pieces(client, order["id"])
    assert _patch_status(client, order["id"], "cut").status_code == 200

    # Canteado aún pendiente → no se puede completar.
    blocked = _patch_status(client, order["id"], "completed")
    assert blocked.status_code == 422
    assert "canteado" in blocked.json()["errors"][0]["message"].lower()

    # Tras terminar el canteado (válido en estado 'cut'), el cierre pasa.
    assert _patch_banding(client, order["id"], "in_progress").status_code == 200
    assert _patch_banding(client, order["id"], "done").status_code == 200
    assert _patch_status(client, order["id"], "completed").status_code == 200


def test_complete_without_edge_banding_needs_no_banding(client, db_session):
    """Una orden sin tapacantos (not_applicable) cierra sin paso de canteado."""
    order = _order_without_banding(client, db_session)
    _to_cutting(client, order["id"])
    _cut_all_pieces(client, order["id"])
    assert _patch_status(client, order["id"], "cut").status_code == 200
    assert _patch_status(client, order["id"], "completed").status_code == 200


# --------------------------------------------------------------------------- #
# Guards de la transición de canteado
# --------------------------------------------------------------------------- #
def test_banding_requires_order_in_cutting_or_cut(client, db_session):
    """Antes de cortar (queued) no hay piezas liberadas que cantear → 422."""
    order = _order_with_banding(client, db_session)
    assert _patch_status(client, order["id"], "queued").status_code == 200
    resp = _patch_banding(client, order["id"], "in_progress")
    assert resp.status_code == 422
    assert "corte" in resp.json()["errors"][0]["message"].lower()


def test_banding_not_applicable_order_rejected(client, db_session):
    """Una orden sin tapacantos no admite registro de canteado → 422."""
    order = _order_without_banding(client, db_session)
    _to_cutting(client, order["id"])
    resp = _patch_banding(client, order["id"], "in_progress")
    assert resp.status_code == 422
    assert "tapacantos" in resp.json()["errors"][0]["message"].lower()


def test_banding_invalid_transition_skipping_in_progress(client, db_session):
    order = _order_with_banding(client, db_session)
    _to_cutting(client, order["id"])
    resp = _patch_banding(client, order["id"], "done")  # pending → done (salta inicio)
    assert resp.status_code == 422
    assert "inválida" in resp.json()["errors"][0]["message"].lower()


def test_banding_in_progress_is_idempotent(client, db_session):
    order = _order_with_banding(client, db_session)
    _to_cutting(client, order["id"])
    first = _patch_banding(client, order["id"], "in_progress").json()["data"]
    again = _patch_banding(client, order["id"], "in_progress").json()["data"]
    # Re-aplicar no re-sella el inicio.
    assert again["bandingStartedAt"] == first["bandingStartedAt"]
    assert again["bandingStatus"] == "in_progress"


# --------------------------------------------------------------------------- #
# Cola de canteado + aislamiento por sucursal
# --------------------------------------------------------------------------- #
def test_banding_queue_lists_pending_orders(client, db_session):
    order = _order_with_banding(client, db_session)
    _to_cutting(client, order["id"])

    queue = client.get("/api/v1/orders/banding-queue").json()["data"]
    ids = {item["orderId"] for item in queue}
    assert order["id"] in ids
    item = next(i for i in queue if i["orderId"] == order["id"])
    assert item["bandingStatus"] == "pending"
    assert item["status"] == "cutting"


def test_banding_queue_excludes_finished_and_unstarted(client, db_session):
    """Solo entran órdenes con canteado pendiente y corte ya iniciado."""
    # Pendiente pero aún en 'queued' (corte no inició) → fuera.
    not_cutting = _order_with_banding(client, db_session, identifier="0990000001")
    assert _patch_status(client, not_cutting["id"], "queued").status_code == 200

    # En corte y con canteado terminado → fuera.
    done = _order_with_banding(client, db_session, identifier="0990000002")
    _to_cutting(client, done["id"])
    _patch_banding(client, done["id"], "in_progress")
    _patch_banding(client, done["id"], "done")

    ids = {
        i["orderId"] for i in client.get("/api/v1/orders/banding-queue").json()["data"]
    }
    assert not_cutting["id"] not in ids
    assert done["id"] not in ids


def test_banding_queue_is_branch_scoped(client, db_session: Session):
    """El canteador solo ve la cola de su sucursal."""
    # Orden con canteado pendiente en la sucursal por defecto (1), en corte.
    order = _order_with_banding(client, db_session)
    _to_cutting(client, order["id"])

    # Un canteador de OTRA sucursal no ve esa orden en su cola.
    db_session.add(BranchModel(code="SUC2", name="Sucursal Dos", is_active=True))
    db_session.commit()
    branch2 = db_session.query(BranchModel).filter(BranchModel.code == "SUC2").one()
    headers = _token_for(
        client,
        db_session,
        "canteador",
        branch_id=branch2.id,
        email="canteador2@empresa.com",
    )
    queue = client.get("/api/v1/orders/banding-queue", headers=headers).json()["data"]
    assert order["id"] not in {i["orderId"] for i in queue}

    # El canteador de la sucursal 1 sí la ve.
    h1 = _token_for(client, db_session, "canteador")
    q1 = client.get("/api/v1/orders/banding-queue", headers=h1).json()["data"]
    assert order["id"] in {i["orderId"] for i in q1}


# --------------------------------------------------------------------------- #
# RBAC del rol canteador
# --------------------------------------------------------------------------- #
def test_canteador_can_band_but_not_read_order_detail(client, db_session):
    order = _order_with_banding(client, db_session)
    _to_cutting(client, order["id"])
    headers = _token_for(client, db_session, "canteador")

    # Puede registrar el canteado y ver su cola...
    assert (
        _patch_banding(client, order["id"], "in_progress", headers=headers).status_code
        == 200
    )
    assert (
        client.get("/api/v1/orders/banding-queue", headers=headers).status_code == 200
    )
    # ...pero NO el detalle de la orden (sin orders:read).
    assert (
        client.get(f"/api/v1/orders/{order['id']}", headers=headers).status_code == 403
    )


def test_operator_and_seller_cannot_band(client, db_session):
    order = _order_with_banding(client, db_session)
    _to_cutting(client, order["id"])
    for role in ("operador", "vendedor"):
        headers = _token_for(client, db_session, role)
        resp = _patch_banding(client, order["id"], "in_progress", headers=headers)
        assert resp.status_code == 403, role
