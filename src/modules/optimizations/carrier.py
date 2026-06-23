from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ProformaCarrier:
    """Portador duck-typed que la proforma y la hoja de producción saben renderizar.

    Unifica las dos fuentes de un mismo cálculo —una optimización efímera
    (cacheada por hash) o el snapshot inmutable de una orden— exponiendo los
    mismos atributos que ``ProformaService`` lee, sin acoplar el render a un
    modelo ORM concreto. El render solo depende de esta forma, no de su origen.
    """

    reference: str
    client: object
    company: dict = field(default_factory=dict)
    # Vigencia (días) que muestra la proforma; ``None`` la omite (p. ej. una orden
    # ya confirmada no es una cotización vigente). La fijan los carriers de cotización.
    validity_days: Optional[int] = None
    requirements: List[dict] = field(default_factory=list)
    materials_summary: List[dict] = field(default_factory=list)
    edge_bandings_summary: List[dict] = field(default_factory=list)
    layouts: List[dict] = field(default_factory=list)
    layout_groups: List[dict] = field(default_factory=list)
    total_boards_used: int = 0
    total_boards_cost: float = 0.0
    total_edge_banding_cost: float = 0.0
    total_cut_linear_m: float = 0.0
    total_edge_banding_linear_m: float = 0.0
    # Descuento a nivel documento (nivel de precio). 0 = sin descuento (consumidor).
    price_tier_name: Optional[str] = None
    discount_rate: float = 0.0
    discount_amount: float = 0.0

    @property
    def subtotal(self) -> float:
        """Subtotal a precio de lista: tableros + tapacantos (antes del descuento)."""
        return round(self.total_boards_cost + self.total_edge_banding_cost, 2)

    @property
    def total_cost(self) -> float:
        """Costo total: subtotal a precio de lista menos el descuento del nivel."""
        return round(self.subtotal - self.discount_amount, 2)

    @classmethod
    def from_payload(
        cls,
        payload: dict,
        client,
        reference: str,
        company: dict | None = None,
        validity_days: Optional[int] = None,
        branch: dict | None = None,
    ) -> "ProformaCarrier":
        """Construye el portador desde un payload de optimización + el cliente.

        ``company`` es el membrete vigente (datos de la empresa) que se renderiza en
        vivo; no forma parte del snapshot con precio. ``validity_days`` es la vigencia
        de la cotización que muestra la proforma (``None`` la omite). ``branch``, si se
        da, es la sucursal dueña del documento: reemplaza el listado de sucursales del
        membrete para mostrar solo esa (``{"name", "address"}``).
        """
        company = company or {}
        if branch is not None:
            company = {**company, "branches": [branch]}
        # Bloque de descuento (lo adjunta build_pricing antes de armar el carrier; un
        # payload sin él = sin descuento, p. ej. snapshots previos a la feature).
        pricing = payload.get("pricing") or {}
        return cls(
            reference=reference,
            client=client,
            company=company,
            validity_days=validity_days,
            requirements=payload.get("requirements") or [],
            materials_summary=payload.get("materials_summary") or [],
            edge_bandings_summary=payload.get("edge_bandings_summary") or [],
            layouts=payload.get("layouts") or [],
            layout_groups=payload.get("layout_groups") or [],
            total_boards_used=payload.get("total_boards_used", 0),
            total_boards_cost=payload.get("total_boards_cost", 0.0),
            total_edge_banding_cost=payload.get("total_edge_banding_cost", 0.0),
            total_cut_linear_m=payload.get("total_cut_linear_m", 0.0),
            total_edge_banding_linear_m=payload.get("total_edge_banding_linear_m", 0.0),
            price_tier_name=pricing.get("price_tier_name"),
            discount_rate=pricing.get("discount_rate", 0.0),
            discount_amount=pricing.get("discount_amount", 0.0),
        )

    @classmethod
    def from_order(
        cls, order, company: dict | None = None, branch: dict | None = None
    ) -> "ProformaCarrier":
        """Construye el portador desde una orden (snapshot + precios congelados).

        El desglose (tableros vs tapacantos) se toma del snapshot inmutable; el
        gran total congelado vive en ``order.total`` (= tableros + tapacantos). El
        membrete (``company``) se renderiza en vivo, no se congela en el snapshot.
        ``branch`` (sucursal de la orden) acota el membrete a esa sucursal.
        """
        snapshot = order.optimization_snapshot or {}
        reference = order.code or f"ORD-{order.id:06d}"
        carrier = cls.from_payload(
            snapshot, order.client, reference=reference, company=company, branch=branch
        )
        # La orden congela el conteo de tableros al confirmar.
        carrier.total_boards_used = order.total_boards_used
        # El descuento congelado vive en columnas de la orden (fuente de verdad); el
        # nombre del nivel viene del snapshot (from_payload ya lo leyó).
        carrier.discount_rate = order.discount_rate
        carrier.discount_amount = order.discount_amount
        return carrier
