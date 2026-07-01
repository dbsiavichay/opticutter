"""Tests for the price tier system (discount by client type).

Covers: the pure ``build_pricing`` transform, the settings config (GET/PATCH), the
selection in the pre-order (quote), the freeze + dedupe in the order, and the
public review projection.
"""

from src.modules.optimizations.pricing import build_pricing
from src.modules.orders.model import OrderModel
from src.modules.orders.schemas import OrderCreate
from src.modules.orders.service import OrderService

from .test_orders import _create_board, _create_client, _order_payload


# --- build_pricing (pure layer) -----------------------------------------------
def _payload(*, catalog_boards=100.0, offcut_boards=0.0, edge=0.0):
    """Minimal payload with one catalog board and (optionally) one off-catalog board."""
    materials_summary = [
        {"product_id": 5, "total_cost": catalog_boards},
    ]
    if offcut_boards:
        materials_summary.append({"product_id": None, "total_cost": offcut_boards})
    return {
        "total_boards_cost": round(catalog_boards + offcut_boards, 2),
        "total_edge_banding_cost": edge,
        "materials_summary": materials_summary,
    }


def test_build_pricing_consumidor_is_no_discount():
    tier = {"code": "consumidor", "name": "Precio Consumidor", "rate": 0.0}
    p = build_pricing(_payload(catalog_boards=100.0, edge=20.0), tier)
    assert p["subtotal"] == 120.0
    assert p["discount_amount"] == 0.0
    assert p["total"] == 120.0
    assert p["price_tier_code"] == "consumidor"


def test_build_pricing_discounts_only_catalog_boards():
    # 100 catalog + 50 offcut (product_id None) + 20 edge banding. The 2% applies
    # only to the 100 catalog amount => 2.0 discount.
    tier = {"code": "carpintero", "name": "Precio Carpintero", "rate": 0.02}
    p = build_pricing(
        _payload(catalog_boards=100.0, offcut_boards=50.0, edge=20.0), tier
    )
    assert p["discount_base"] == 100.0
    assert p["subtotal"] == 170.0  # everything at list price
    assert p["discount_amount"] == 2.0
    assert p["total"] == 168.0


def test_build_pricing_efectivo_rounds_to_cents():
    tier = {"code": "efectivo", "name": "Precio Efectivo", "rate": 0.05}
    p = build_pricing(_payload(catalog_boards=45.5), tier)
    assert p["discount_amount"] == round(45.5 * 0.05, 2)
    assert p["total"] == round(45.5 - p["discount_amount"], 2)


# --- Tier config in settings -------------------------------------------
def test_get_price_tiers_lists_active_sorted(client):
    resp = client.get("/api/v1/settings/price-tiers")
    assert resp.status_code == 200
    tiers = resp.json()["data"]
    assert [t["code"] for t in tiers] == ["consumidor", "carpintero", "efectivo"]
    assert tiers[1]["rate"] == 0.02
    assert all(t["isActive"] for t in tiers)


def test_patch_price_tiers_changes_rate(client):
    new_tiers = [
        {
            "code": "consumidor",
            "name": "Precio Consumidor",
            "rate": 0.0,
            "isActive": True,
            "sortOrder": 1,
        },
        {
            "code": "carpintero",
            "name": "Precio Carpintero",
            "rate": 0.03,
            "isActive": True,
            "sortOrder": 2,
        },
    ]
    resp = client.patch("/api/v1/settings/price-tiers", json={"priceTiers": new_tiers})
    assert resp.status_code == 200
    after = client.get("/api/v1/settings/price-tiers").json()["data"]
    assert {t["code"]: t["rate"] for t in after} == {
        "consumidor": 0.0,
        "carpintero": 0.03,
    }


# --- Pre-order (quote): live selection ----------------------------------
def test_preorder_create_applies_discount_to_optimization(client):
    c = _create_client(client)
    b = _create_board(client)  # price 45.5, 1 board used
    payload = _order_payload(c["id"], b["id"])
    payload["priceTierCode"] = "carpintero"

    resp = client.post("/api/v1/preorders/", json=payload)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["priceTierCode"] == "carpintero"

    pricing = data["optimization"]["pricing"]
    assert pricing["priceTierCode"] == "carpintero"
    assert pricing["discountRate"] == 0.02
    assert pricing["subtotal"] == 45.5  # at list price
    assert pricing["discountAmount"] == 0.91
    assert pricing["total"] == 44.59


def test_preorder_create_rejects_unknown_tier(client):
    c = _create_client(client)
    b = _create_board(client)
    payload = _order_payload(c["id"], b["id"])
    payload["priceTierCode"] = "mayorista"

    resp = client.post("/api/v1/preorders/", json=payload)
    assert resp.status_code == 422
    assert "Nivel de precio" in resp.json()["errors"][0]["message"]


# --- Order: freeze + audit + dedupe -----------------------------------
def test_order_freezes_discount(client, db_session):
    c = _create_client(client)
    b = _create_board(client)
    payload = _order_payload(c["id"], b["id"])
    payload["priceTierCode"] = "carpintero"

    order = OrderService(db_session).create(OrderCreate.model_validate(payload))
    data = client.get(f"/api/v1/orders/{order.id}").json()["data"]

    assert data["priceTierCode"] == "carpintero"
    assert data["discountRate"] == 0.02
    assert data["subtotal"] == 45.5
    assert data["discountAmount"] == 0.91
    assert data["total"] == 44.59  # subtotal != total
    # Lines stay at list price (discount applies only at document level).
    assert data["lines"][0]["unitPriceSnapshot"] == 45.5


def test_order_discount_rate_frozen_against_settings_change(client, db_session):
    c = _create_client(client)
    b = _create_board(client)
    payload = _order_payload(c["id"], b["id"])
    payload["priceTierCode"] = "carpintero"
    order = OrderService(db_session).create(OrderCreate.model_validate(payload))

    # Changing the carpintero rate to 10% must NOT alter the already-created order.
    client.patch(
        "/api/v1/settings/price-tiers",
        json={
            "priceTiers": [
                {
                    "code": "carpintero",
                    "name": "Precio Carpintero",
                    "rate": 0.10,
                    "isActive": True,
                    "sortOrder": 1,
                },
            ]
        },
    )
    db_session.expire_all()
    frozen = db_session.get(OrderModel, order.id)
    assert frozen.discount_rate == 0.02
    assert frozen.total == 44.59


def test_dedupe_distinguishes_price_tiers(client, db_session):
    c = _create_client(client)
    b = _create_board(client)
    svc = OrderService(db_session)

    base = _order_payload(c["id"], b["id"])
    consumidor = svc.create(
        OrderCreate.model_validate({**base, "priceTierCode": "consumidor"})
    )
    # Same geometry, same tier => idempotent (same order).
    again = svc.create(
        OrderCreate.model_validate({**base, "priceTierCode": "consumidor"})
    )
    assert again.id == consumidor.id
    # Same geometry, different tier => different order (tier isn't part of the hash).
    carpintero = svc.create(
        OrderCreate.model_validate({**base, "priceTierCode": "carpintero"})
    )
    assert carpintero.id != consumidor.id
    assert carpintero.optimization_hash == consumidor.optimization_hash


# --- Public review: the client sees the discount ----------------------------
def test_public_review_reflects_discount(client, db_session):
    c = _create_client(client)
    b = _create_board(client)
    payload = _order_payload(c["id"], b["id"])
    payload["priceTierCode"] = "carpintero"
    pre = client.post("/api/v1/preorders/", json=payload).json()["data"]

    link = client.post(f"/api/v1/preorders/{pre['id']}/review-link").json()["data"]
    review = client.get(f"/api/v1/public/review/{link['token']}").json()["data"]

    assert review["subtotal"] == 45.5
    assert review["discountRate"] == 0.02
    assert review["discountAmount"] == 0.91
    assert review["total"] == 44.59
    assert review["priceTierName"] == "Precio Carpintero"
