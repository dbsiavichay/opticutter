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
    layouts: List[dict] = field(default_factory=list)
    layout_groups: List[dict] = field(default_factory=list)
    total_boards_used: int = 0
    total_boards_cost: float = 0.0

    @classmethod
    def from_payload(cls, payload: dict, client, reference: str) -> "ProformaCarrier":
        """Construye el portador desde un payload de optimización + el cliente."""
        return cls(
            reference=reference,
            client=client,
            requirements=payload.get("requirements") or [],
            materials_summary=payload.get("materials_summary") or [],
            layouts=payload.get("layouts") or [],
            layout_groups=payload.get("layout_groups") or [],
            total_boards_used=payload.get("total_boards_used", 0),
            total_boards_cost=payload.get("total_boards_cost", 0.0),
        )

    @classmethod
    def from_order(cls, order) -> "ProformaCarrier":
        """Construye el portador desde una orden (snapshot + precios congelados)."""
        snapshot = order.optimization_snapshot or {}
        reference = order.code or f"ORD-{order.id:06d}"
        carrier = cls.from_payload(snapshot, order.client, reference=reference)
        # La orden congela totales al confirmar: prevalecen sobre el snapshot.
        carrier.total_boards_used = order.total_boards_used
        carrier.total_boards_cost = order.total
        return carrier
