"""Tests for the shared shop-floor board endpoint ``GET /orders/workshop-queue``.

The board is a self-sufficient card list (client + board names + progress) for the
operator AND the canteador (who lacks ``orders:read``). It lists orders from the
queue up to ``cut``; ``confirmed``/``completed``/etc. are excluded. Reuses the
catalog/order/token helpers of the banding-track suite.
"""

from sqlalchemy.orm import Session

from src.modules.branches.model import BranchModel
from tests.test_order_banding import (
    _cut_all_pieces,
    _order_with_banding,
    _order_without_banding,
    _patch_banding,
    _patch_status,
    _to_cutting,
    _token_for,
)

_URL = "/api/v1/orders/workshop-queue"


def test_workshop_queue_lists_queued_through_cut(client, db_session):
    """Orders in queued / cutting / cut all appear, with a self-sufficient projection."""
    queued = _order_with_banding(client, db_session, identifier="0990000021")
    assert _patch_status(client, queued["id"], "queued").status_code == 200

    cutting = _order_with_banding(client, db_session, identifier="0990000022")
    _to_cutting(client, cutting["id"])

    cut = _order_with_banding(client, db_session, identifier="0990000023")
    _to_cutting(client, cut["id"])
    _cut_all_pieces(client, cut["id"])
    assert _patch_status(client, cut["id"], "cut").status_code == 200

    board = client.get(_URL).json()["data"]
    by_id = {i["orderId"]: i for i in board}
    assert {queued["id"], cutting["id"], cut["id"]} <= set(by_id)

    item = by_id[cut["id"]]
    assert item["status"] == "cut"
    assert item["bandingStatus"] == "pending"
    assert item["client"]["firstName"] == "Ada"
    assert item["boardNames"]  # non-empty (self-sufficient for the canteador)
    # suffix "0023" → product "Tapacanto TAP0023", bandType Suave.
    assert item["bandingNames"] == ["Tapacanto TAP0023 (Suave)"]
    # Every piece was cut → progress is complete.
    assert item["progress"]["totalPieces"] >= 1
    assert item["progress"]["cutPieces"] == item["progress"]["totalPieces"]

    # A still-queued order shows zero cut progress.
    assert by_id[queued["id"]]["progress"]["cutPieces"] == 0


def test_workshop_queue_excludes_confirmed_and_completed(client, db_session):
    """The board only spans the active shop-floor window (queued..cut)."""
    confirmed = _order_with_banding(client, db_session, identifier="0990000024")

    completed = _order_with_banding(client, db_session, identifier="0990000025")
    _to_cutting(client, completed["id"])
    assert _patch_banding(client, completed["id"], "in_progress").status_code == 200
    assert _patch_banding(client, completed["id"], "done").status_code == 200
    _cut_all_pieces(client, completed["id"])
    assert _patch_status(client, completed["id"], "cut").status_code == 200
    assert _patch_status(client, completed["id"], "completed").status_code == 200

    ids = {i["orderId"] for i in client.get(_URL).json()["data"]}
    assert confirmed["id"] not in ids  # not yet in the shop
    assert completed["id"] not in ids  # already closed


def test_workshop_queue_lists_banding_names(client, db_session):
    """The card lists the tapacanto names (+ Suave/Duro) so the canteador knows
    which material to apply; an order without banding yields an empty list."""
    banded = _order_with_banding(client, db_session, identifier="0990000030")
    assert _patch_status(client, banded["id"], "queued").status_code == 200

    plain = _order_without_banding(client, db_session)
    assert _patch_status(client, plain["id"], "queued").status_code == 200

    by_id = {i["orderId"]: i for i in client.get(_URL).json()["data"]}
    # suffix "0030" → product "Tapacanto TAP0030", bandType Suave.
    assert by_id[banded["id"]]["bandingNames"] == ["Tapacanto TAP0030 (Suave)"]
    assert by_id[plain["id"]]["bandingNames"] == []


def test_workshop_queue_is_fifo_oldest_first(client, db_session):
    o1 = _order_with_banding(client, db_session, identifier="0990000026")
    o2 = _order_with_banding(client, db_session, identifier="0990000027")
    _to_cutting(client, o1["id"])
    _to_cutting(client, o2["id"])
    board = client.get(_URL).json()["data"]
    seen = [i["orderId"] for i in board if i["orderId"] in {o1["id"], o2["id"]}]
    assert seen == [o1["id"], o2["id"]]


def test_workshop_queue_is_branch_scoped(client, db_session: Session):
    """The board is branch-isolated: workshop roles see only their own branch."""
    order = _order_with_banding(client, db_session, identifier="0990000029")
    _to_cutting(client, order["id"])

    db_session.add(BranchModel(code="SUCW", name="Sucursal Taller", is_active=True))
    db_session.commit()
    branch2 = db_session.query(BranchModel).filter(BranchModel.code == "SUCW").one()

    # A canteador from ANOTHER branch doesn't see this order.
    other = _token_for(
        client,
        db_session,
        "canteador",
        branch_id=branch2.id,
        email="canteadorw@empresa.com",
    )
    ids_other = {i["orderId"] for i in client.get(_URL, headers=other).json()["data"]}
    assert order["id"] not in ids_other

    # The operador from branch 1 (same as the order) does.
    same = _token_for(client, db_session, "operador")
    ids_same = {i["orderId"] for i in client.get(_URL, headers=same).json()["data"]}
    assert order["id"] in ids_same


def test_workshop_queue_rbac(client, db_session):
    """Operator + canteador reach the board; seller (no ``orders:workshop``) can't."""
    order = _order_with_banding(client, db_session, identifier="0990000028")
    _to_cutting(client, order["id"])

    # The canteador reaches it despite lacking ``orders:read`` (embedded client proves it).
    canteador = _token_for(client, db_session, "canteador")
    resp = client.get(_URL, headers=canteador)
    assert resp.status_code == 200
    item = next(i for i in resp.json()["data"] if i["orderId"] == order["id"])
    assert item["client"]["firstName"] == "Ada"

    assert (
        client.get(_URL, headers=_token_for(client, db_session, "operador")).status_code
        == 200
    )
    assert (
        client.get(_URL, headers=_token_for(client, db_session, "vendedor")).status_code
        == 403
    )
