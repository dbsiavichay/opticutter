from dataclasses import dataclass, field
from typing import List


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
    requirements: List[dict] = field(default_factory=list)
    materials_summary: List[dict] = field(default_factory=list)
    edge_bandings_summary: List[dict] = field(default_factory=list)
    layouts: List[dict] = field(default_factory=list)
    layout_groups: List[dict] = field(default_factory=list)
    total_boards_used: int = 0
    total_boards_cost: float = 0.0
    total_edge_banding_cost: float = 0.0

    @property
    def total_cost(self) -> float:
        """Costo total: tableros + tapacantos."""
        return round(self.total_boards_cost + self.total_edge_banding_cost, 2)

    @classmethod
    def from_payload(cls, payload: dict, client, reference: str) -> "ProformaCarrier":
        """Construye el portador desde un payload de optimización + el cliente."""
        return cls(
            reference=reference,
            client=client,
            requirements=payload.get("requirements") or [],
            materials_summary=payload.get("materials_summary") or [],
            edge_bandings_summary=payload.get("edge_bandings_summary") or [],
            layouts=payload.get("layouts") or [],
            layout_groups=payload.get("layout_groups") or [],
            total_boards_used=payload.get("total_boards_used", 0),
            total_boards_cost=payload.get("total_boards_cost", 0.0),
            total_edge_banding_cost=payload.get("total_edge_banding_cost", 0.0),
        )

    @classmethod
    def from_order(cls, order) -> "ProformaCarrier":
        """Construye el portador desde una orden (snapshot + precios congelados).

        El desglose (tableros vs tapacantos) se toma del snapshot inmutable; el
        gran total congelado vive en ``order.total`` (= tableros + tapacantos).
        """
        snapshot = order.optimization_snapshot or {}
        reference = order.code or f"ORD-{order.id:06d}"
        carrier = cls.from_payload(snapshot, order.client, reference=reference)
        # La orden congela el conteo de tableros al confirmar.
        carrier.total_boards_used = order.total_boards_used
        return carrier
