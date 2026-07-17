"""Price-tier discount applied on top of an already-optimized payload.

Pure layer (no DB or framework): cut geometry is cached by hash and is
price-agnostic; the discount is applied **after** ``compute()`` as a
deterministic transform, keeping the optimization cache shared across tiers.

Business rules (decided with the user):
- **Document-level**: line items stay at list price; the discount is a single
  ``subtotal → discount_amount → total`` adjustment.
- **Catalog boards only**: the discount base is the catalog boards
  (``materials_summary`` entries with a non-null ``product_id``). Edge banding,
  offcuts and manual measurements are charged at list price.
"""


def build_pricing(
    payload: dict, tier: dict, additional_services: list | None = None
) -> dict:
    """Computes the pricing block (document-level discount) for a given ``tier``.

    ``tier`` is a resolved price tier ``{code, name, rate, ...}`` (see
    ``SettingsService.resolve_price_tier``). ``additional_services`` is the list of
    billed services (``{unit_price, quantity, ...}``); they are **not** cut geometry
    and are added on top of the total, **after** the discount (the tier discount
    applies only to catalog boards). Returns a serializable dict that is exposed in
    the response and frozen into the order's snapshot/columns.
    """
    rate = float(tier.get("rate", 0.0))
    # Base = catalog boards (non-null product_id). Excludes offcuts/manual
    # (product_id None) and edge banding (a separate collection).
    discount_base = round(
        sum(
            m.get("total_cost", 0.0)
            for m in payload.get("materials_summary") or []
            if m.get("product_id") is not None
        ),
        2,
    )
    boards = payload.get("total_boards_cost", 0.0)
    edge = payload.get("total_edge_banding_cost", 0.0)
    subtotal = round(boards + edge, 2)
    discount_amount = round(discount_base * rate, 2)
    # Additional services: qty × unit price, not discounted (added at the end).
    services_total = round(
        sum(
            s.get("unit_price", 0.0) * s.get("quantity", 0)
            for s in additional_services or []
        ),
        2,
    )
    total = round(subtotal - discount_amount + services_total, 2)
    return {
        "price_tier_code": tier.get("code"),
        "price_tier_name": tier.get("name"),
        "discount_rate": rate,
        "discount_base": discount_base,
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "services_total": services_total,
        "total": total,
    }
