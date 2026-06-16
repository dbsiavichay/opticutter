"""Agregaciones read-only para el dashboard.

Único módulo que usa agregación SQL (``func.sum``/``func.count``/``group_by``); el
bucketing temporal y la ponderación de eficiencia se hacen en Python para ser portables
y explícitos. La única historia durable es la orden (las optimizaciones son efímeras en
Redis), así que todo se construye sobre ``orders`` + ``order_lines`` + ``order_status_history``.
"""

from collections import defaultdict

from fastapi import Depends
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from src.modules.analytics.constants import (
    PENDING_STATUSES,
    REALIZED_STATUSES,
    STATUS_LABELS,
    Granularity,
    safe_div,
    status_values,
)
from src.modules.analytics.dates import DateRange, bucket_key, iter_buckets
from src.modules.analytics.schemas import (
    AnalyticsSummary,
    Breakdown,
    BreakdownItem,
    DwellTime,
    OperationsReport,
    RangeInfo,
    TimeSeries,
    TimeSeriesData,
)
from src.modules.orders.model import OrderLineModel, OrderModel, OrderStatus
from src.shared.database import get_db


class AnalyticsService:
    """Calcula métricas agregadas sobre el agregado de órdenes."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ summary
    def summary(self, dr: DateRange) -> AnalyticsSummary:
        order_count = self._count(dr)
        completed_count = self._count(dr, REALIZED_STATUSES)
        cancelled = self._count(dr, {OrderStatus.cancelled})

        realized_revenue = self._revenue(dr, REALIZED_STATUSES)
        boards = self._boards_consumed(dr)
        avg_eff, area = self._efficiency_and_area(dr)
        waste = round(area * (1 - avg_eff / 100), 4)

        active_clients = (
            self.db.query(func.count(distinct(OrderModel.client_id)))
            .filter(*self._range(dr))
            .scalar()
        ) or 0

        return AnalyticsSummary(
            range=RangeInfo(date_from=dr.date_from, date_to=dr.date_to),
            total_boards_consumed=boards,
            average_efficiency=avg_eff,
            total_area_cut_m2=area,
            waste_estimate_m2=waste,
            pending_orders_count=self._count(dr, PENDING_STATUSES),
            cancellation_rate=round(safe_div(cancelled, order_count), 4),
            order_count=order_count,
            realized_revenue=realized_revenue,
            average_ticket=round(safe_div(realized_revenue, completed_count), 2),
            active_clients_count=active_clients,
        )

    # --------------------------------------------------------------- timeseries
    def timeseries(self, dr: DateRange, granularity: Granularity) -> TimeSeries:
        buckets = iter_buckets(dr.date_from, dr.date_to, granularity)
        labels = [b.isoformat() for b in buckets]
        index = {b: i for i, b in enumerate(buckets)}
        n = len(buckets)
        revenue = [0.0] * n
        order_count = [0] * n
        boards = [0] * n
        new_clients = [0] * n

        completed = OrderStatus.completed.value
        rows = (
            self.db.query(
                OrderModel.created_at,
                OrderModel.total,
                OrderModel.status,
                OrderModel.total_boards_used,
            )
            .filter(*self._range(dr))
            .all()
        )
        for created_at, total, status, tboards in rows:
            i = index.get(bucket_key(created_at.date(), granularity))
            if i is None:
                continue
            order_count[i] += 1
            if status == completed:  # ingreso/tableros realizados
                revenue[i] += total or 0.0
                boards[i] += tboards or 0

        # Clientes nuevos: primer pedido (MIN created_at) por cliente sobre TODA la
        # historia; se cuenta en el bucket de ese primer pedido si cae en el rango.
        first_orders = (
            self.db.query(OrderModel.client_id, func.min(OrderModel.created_at))
            .group_by(OrderModel.client_id)
            .all()
        )
        for _, first_dt in first_orders:
            if dr.start <= first_dt < dr.end:
                i = index.get(bucket_key(first_dt.date(), granularity))
                if i is not None:
                    new_clients[i] += 1

        return TimeSeries(
            granularity=granularity,
            buckets=labels,
            series=TimeSeriesData(
                revenue=[round(r, 2) for r in revenue],
                order_count=order_count,
                boards_consumed=boards,
                new_clients=new_clients,
            ),
        )

    # ----------------------------------------------------------- breakdown/status
    def breakdown_status(self, dr: DateRange) -> Breakdown:
        rows = (
            self.db.query(
                OrderModel.status,
                func.count(OrderModel.id),
                func.coalesce(func.sum(OrderModel.total), 0.0),
            )
            .filter(*self._range(dr))
            .group_by(OrderModel.status)
            .all()
        )
        by_status = {status: (count, rev) for status, count, rev in rows}
        items = [
            BreakdownItem(
                key=st.value,
                label=STATUS_LABELS[st],
                revenue=round(by_status.get(st.value, (0, 0.0))[1], 2),
                order_count=by_status.get(st.value, (0, 0.0))[0],
            )
            for st in OrderStatus  # densifica: todos los estados, incluso en cero
        ]
        return Breakdown(dimension="status", items=items)

    # ------------------------------------------------------------------ operations
    def operations(self, dr: DateRange) -> OperationsReport:
        avg_eff, area = self._efficiency_and_area(dr)
        waste = round(area * (1 - avg_eff / 100), 4)

        orders = self.db.query(OrderModel).filter(*self._range(dr)).all()
        return OperationsReport(
            average_efficiency=avg_eff,
            total_area_cut_m2=area,
            waste_estimate_m2=waste,
            lifecycle=self._lifecycle(orders),
        )

    # --------------------------------------------------------------------- helpers
    def _range(self, dr: DateRange) -> list:
        """Filtro medio-abierto ``[start, end)`` sobre ``created_at``."""
        return [OrderModel.created_at >= dr.start, OrderModel.created_at < dr.end]

    def _count(self, dr: DateRange, statuses=None) -> int:
        query = self.db.query(func.count(OrderModel.id)).filter(*self._range(dr))
        if statuses is not None:
            query = query.filter(OrderModel.status.in_(status_values(statuses)))
        return query.scalar() or 0

    def _revenue(self, dr: DateRange, statuses) -> float:
        val = (
            self.db.query(func.coalesce(func.sum(OrderModel.total), 0.0))
            .filter(*self._range(dr))
            .filter(OrderModel.status.in_(status_values(statuses)))
            .scalar()
        )
        return round(val or 0.0, 2)

    def _boards_consumed(self, dr: DateRange) -> int:
        """Tableros de órdenes completadas (producción realizada)."""
        val = (
            self.db.query(func.coalesce(func.sum(OrderModel.total_boards_used), 0))
            .filter(*self._range(dr))
            .filter(OrderModel.status.in_(status_values(REALIZED_STATUSES)))
            .scalar()
        )
        return int(val or 0)

    def _efficiency_and_area(self, dr: DateRange) -> tuple[float, float]:
        """Eficiencia ponderada por área (0..100) y área total (m²) de líneas de tablero.

        Excluye líneas de tapacanto (``total_area_m2``/``avg_efficiency`` nulos). El
        promedio se pondera por área: una orden de 1 tablero no pesa igual que una de 50.
        """
        rows = (
            self.db.query(OrderLineModel.avg_efficiency, OrderLineModel.total_area_m2)
            .join(OrderModel, OrderLineModel.order_id == OrderModel.id)
            .filter(*self._range(dr))
            .filter(OrderModel.status.in_(status_values(REALIZED_STATUSES)))
            .filter(OrderLineModel.total_area_m2.isnot(None))
            .filter(OrderLineModel.avg_efficiency.isnot(None))
            .all()
        )
        total_area = sum(area for _, area in rows)
        if not total_area:
            return 0.0, 0.0
        weighted = sum(eff * area for eff, area in rows) / total_area
        return round(weighted, 2), round(total_area, 4)

    def _lifecycle(self, orders: list[OrderModel]) -> list[DwellTime]:
        """Horas medias en cada estado, por par ``(from_status, to_status)``.

        El tiempo en un estado = intervalo entre el evento que entró a él y el que lo
        dejó; ``sample_count`` transparenta el tamaño de la muestra.
        """
        acc: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0])
        for o in orders:
            hist = sorted(o.history, key=lambda h: (h.created_at, h.id))
            for prev, cur in zip(hist, hist[1:]):
                if prev.to_status != cur.from_status:
                    continue
                hours = (cur.created_at - prev.created_at).total_seconds() / 3600.0
                bucket = acc[(cur.from_status, cur.to_status)]
                bucket[0] += hours
                bucket[1] += 1
        return [
            DwellTime(
                from_status=frm,
                to_status=to,
                avg_hours=round(safe_div(total_hours, count), 2),
                sample_count=count,
            )
            for (frm, to), (total_hours, count) in sorted(acc.items())
        ]


def analytics_service(db: Session = Depends(get_db)) -> AnalyticsService:
    """Provider de ``AnalyticsService`` para inyección en rutas."""
    return AnalyticsService(db)
