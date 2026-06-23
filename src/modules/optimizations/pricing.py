"""Descuento por nivel de precio aplicado sobre un payload ya optimizado.

Capa pura (sin DB ni framework): la geometría del corte se cachea por hash y es
agnóstica al precio; el descuento se aplica **después** de ``compute()`` como un
transform determinista, manteniendo la caché de optimización compartida entre niveles.

Reglas de negocio (decididas con el usuario):
- A **nivel de documento**: las líneas se quedan a precio de lista; el descuento es un
  único ajuste ``subtotal → discount_amount → total``.
- **Solo tableros de catálogo**: la base del descuento son los tableros del catálogo
  (``materials_summary`` con ``product_id`` no nulo). Tapacantos, retazos y medidas
  manuales se cobran a precio de lista.
"""


def build_pricing(payload: dict, tier: dict) -> dict:
    """Calcula el bloque de precios (descuento a nivel documento) para un ``tier``.

    ``tier`` es una tarifa resuelta ``{code, name, rate, ...}`` (ver
    ``SettingsService.resolve_price_tier``). Devuelve un dict serializable que se
    expone en la respuesta y se congela en el snapshot/columnas de la orden.
    """
    rate = float(tier.get("rate", 0.0))
    # Base = tableros de catálogo (product_id no nulo). Excluye retazos/manual
    # (product_id None) y tapacantos (otra colección).
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
    total = round(subtotal - discount_amount, 2)
    return {
        "price_tier_code": tier.get("code"),
        "price_tier_name": tier.get("name"),
        "discount_rate": rate,
        "discount_base": discount_base,
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "total": total,
    }
