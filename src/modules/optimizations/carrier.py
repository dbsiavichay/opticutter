from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class ProformaCarrier:
    """Duck-typed carrier that the proforma and production sheet know how to render.

    Unifies the two sources of the same computation — an ephemeral optimization
    (cached by hash) or an order's immutable snapshot — exposing the same
    attributes that ``ProformaService`` reads, without coupling the render to a
    concrete ORM model. The render only depends on this shape, not its origin.
    """

    reference: str
    client: object
    company: dict = field(default_factory=dict)
    # Validity (days) shown on the proforma; ``None`` omits it (e.g. an already
    # confirmed order isn't a current quote). Set by the quoting carriers.
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
    # Document-level discount (price tier). 0 = no discount (walk-in customer).
    price_tier_name: Optional[str] = None
    discount_rate: float = 0.0
    discount_amount: float = 0.0
    # Billed additional services (qty × unit price); added on top of the total
    # after the discount. Empty for documents without services.
    additional_services: List[dict] = field(default_factory=list)
    # Dispatch data (only the dispatch sheet uses it; ``None`` omits it). Set by
    # ``from_order`` from the order; the ephemeral-optimization path doesn't.
    dispatch_date: Optional[datetime] = None
    dispatched_by_label: Optional[str] = None
    # Frozen payment method (informational). Only ``from_order`` sets it; ephemeral
    # quotes leave it as ``None`` and the block is omitted from the PDF.
    payment_cash_amount: Optional[float] = None
    payment_credit_amount: Optional[float] = None

    @property
    def subtotal(self) -> float:
        """List-price subtotal: boards + edge banding (before the discount)."""
        return round(self.total_boards_cost + self.total_edge_banding_cost, 2)

    @property
    def services_total(self) -> float:
        """Sum of the billed additional services (qty × unit price)."""
        return round(
            sum(
                s.get("unit_price", 0.0) * s.get("quantity", 0)
                for s in self.additional_services
            ),
            2,
        )

    @property
    def total_cost(self) -> float:
        """Total cost: list-price subtotal − tier discount + additional services."""
        return round(self.subtotal - self.discount_amount + self.services_total, 2)

    @classmethod
    def from_payload(
        cls,
        payload: dict,
        client,
        reference: str,
        company: dict | None = None,
        validity_days: Optional[int] = None,
    ) -> "ProformaCarrier":
        """Builds the carrier from an optimization payload + the client.

        ``company`` is the current letterhead (company data) rendered live,
        including the full configured branch list; it's not part of the priced
        snapshot. ``validity_days`` is the quote's validity period shown on the
        proforma (``None`` omits it).
        """
        company = company or {}
        # Discount block (attached by build_pricing before assembling the carrier;
        # a payload without it = no discount, e.g. snapshots predating the feature).
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
            additional_services=payload.get("additional_services") or [],
        )

    @classmethod
    def from_order(cls, order, company: dict | None = None) -> "ProformaCarrier":
        """Builds the carrier from an order (snapshot + frozen prices).

        The breakdown (boards vs edge banding) is taken from the immutable
        snapshot; the frozen grand total lives in ``order.total`` (= boards +
        edge banding). The letterhead (``company``) is rendered live, not frozen
        into the snapshot, and always lists every configured branch (not scoped
        to the order's own branch).
        """
        snapshot = order.optimization_snapshot or {}
        reference = order.code or f"ORD-{order.id:06d}"
        carrier = cls.from_payload(
            snapshot, order.client, reference=reference, company=company
        )
        # The order freezes the board count when confirmed.
        carrier.total_boards_used = order.total_boards_used
        # The frozen discount lives in the order's columns (source of truth); the
        # tier name comes from the snapshot (already read by from_payload).
        carrier.discount_rate = order.discount_rate
        carrier.discount_amount = order.discount_amount
        # Frozen dispatch data (shown by the dispatch sheet; ``None`` before dispatch).
        carrier.dispatch_date = order.dispatched_at
        carrier.dispatched_by_label = order.dispatched_by_label
        # Frozen payment method (``None`` before moving to the queue).
        carrier.payment_cash_amount = order.payment_cash_amount
        carrier.payment_credit_amount = order.payment_credit_amount
        return carrier
