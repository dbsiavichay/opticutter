"""Tests del módulo analytics: summary, timeseries, breakdown de estados y operaciones.

Se siembra directo por ``db_session`` para fijar estados, ``created_at`` e historial con
precisión (la máquina de estados no deja alcanzar todos los casos limpio).
"""

from datetime import datetime

from src.modules.clients.model import ClientModel
from src.modules.orders.model import (
    OrderLineModel,
    OrderModel,
    OrderStatusHistoryModel,
)

_BASE = datetime(2026, 6, 15, 12, 0, 0)
_RANGE = {"from": "2026-06-01", "to": "2026-06-30"}


def _board_line(efficiency, area, *, qty=2, price=45.5):
    return OrderLineModel(
        product_id=None,
        quantity=qty,
        unit_price_snapshot=price,
        line_total=qty * price,
        avg_efficiency=efficiency,
        total_area_m2=area,
    )


def _edge_line(linear_m, *, price=1.5):
    """Línea de tapacanto: sin área/eficiencia (no debe contaminar la ponderación)."""
    return OrderLineModel(
        product_id=None,
        quantity=int(linear_m),
        unit_price_snapshot=price,
        line_total=linear_m * price,
        linear_m=linear_m,
    )


def _seed_order(
    db,
    *,
    client_id=1,
    status="completed",
    total=100.0,
    boards=2,
    created_at=_BASE,
    lines=None,
    history=None,
    optimization_hash="h",
    branch_id=1,
):
    order = OrderModel(
        client_id=client_id,
        branch_id=branch_id,
        status=status,
        optimization_snapshot={},
        optimization_hash=optimization_hash,
        currency="USD",
        subtotal=total,
        total=total,
        total_boards_used=boards,
        created_at=created_at,
        confirmed_at=created_at,
    )
    if lines is not None:
        order.lines = lines
    if history is not None:
        order.history = history
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def _seed_clients(db, n=1):
    """Siembra n clientes con identifiers únicos; el primero obtiene id=1, etc."""
    clients = [ClientModel(identifier=f"TEST{i:07d}") for i in range(1, n + 1)]
    for c in clients:
        db.add(c)
    db.commit()
    return clients


def _hist(to_status, created_at, from_status=None):
    return OrderStatusHistoryModel(
        from_status=from_status,
        to_status=to_status,
        actor="system",
        created_at=created_at,
    )


# --------------------------------------------------------------------- summary
def test_summary_empty_range_returns_zeros_not_nulls(client):
    data = client.get("/api/v1/analytics/summary", params=_RANGE).json()["data"]

    for key in (
        "totalBoardsConsumed",
        "averageEfficiency",
        "totalAreaCutM2",
        "wasteEstimateM2",
        "pendingOrdersCount",
        "cancellationRate",
        "orderCount",
        "realizedRevenue",
        "averageTicket",
        "activeClientsCount",
    ):
        assert data[key] == 0, key
        assert data[key] is not None
    assert data["range"]["dateFrom"] == "2026-06-01"
    assert data["range"]["dateTo"] == "2026-06-30"


def test_summary_revenue_and_rates_isolated_by_status(client, db_session):
    _seed_clients(db_session, 2)
    _seed_order(db_session, client_id=1, status="completed", total=100.0)
    _seed_order(db_session, client_id=2, status="confirmed", total=200.0)
    _seed_order(db_session, client_id=1, status="cancelled", total=50.0)

    data = client.get("/api/v1/analytics/summary", params=_RANGE).json()["data"]

    assert data["orderCount"] == 3
    assert data["realizedRevenue"] == 100.0  # solo completed
    assert data["averageTicket"] == 100.0  # 100 / 1 completada
    assert data["pendingOrdersCount"] == 1  # confirmed
    assert data["cancellationRate"] == round(1 / 3, 4)  # 1 / 3
    assert data["activeClientsCount"] == 2  # clientes 1 y 2 distintos


def test_summary_efficiency_is_area_weighted_and_ignores_edge_banding(
    client, db_session
):
    _seed_clients(db_session)
    _seed_order(
        db_session,
        status="completed",
        boards=2,
        lines=[_board_line(90.0, 10.0), _edge_line(5.0)],
    )
    _seed_order(
        db_session, status="completed", boards=5, lines=[_board_line(70.0, 30.0)]
    )

    data = client.get("/api/v1/analytics/summary", params=_RANGE).json()["data"]

    # Ponderada: (90*10 + 70*30) / (10+30) = 3000/40 = 75.0
    assert data["averageEfficiency"] == 75.0
    assert data["totalAreaCutM2"] == 40.0
    assert data["wasteEstimateM2"] == 10.0  # 40 * (1 - 0.75)
    assert data["totalBoardsConsumed"] == 7  # 2 + 5


def test_summary_uses_default_range_when_omitted(client):
    data = client.get("/api/v1/analytics/summary").json()["data"]
    assert data["range"]["dateFrom"] < data["range"]["dateTo"]


def test_invalid_range_returns_422_with_envelope(client):
    resp = client.get(
        "/api/v1/analytics/summary", params={"from": "2026-06-30", "to": "2026-06-01"}
    )
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["field"] == "from"


# ------------------------------------------------------------- date filtering
def test_date_filter_is_half_open(client, db_session):
    _seed_clients(db_session)
    _seed_order(db_session, total=100.0, created_at=datetime(2026, 6, 1, 0, 0, 0))
    _seed_order(db_session, total=50.0, created_at=datetime(2026, 6, 10, 23, 0, 0))
    _seed_order(db_session, total=999.0, created_at=datetime(2026, 5, 31, 23, 0, 0))
    _seed_order(db_session, total=999.0, created_at=datetime(2026, 6, 11, 0, 0, 0))

    data = client.get(
        "/api/v1/analytics/summary", params={"from": "2026-06-01", "to": "2026-06-10"}
    ).json()["data"]
    assert data["orderCount"] == 2
    assert data["realizedRevenue"] == 150.0


# ------------------------------------------------------------------ timeseries
def test_timeseries_daily_dense_axis_with_zero_gaps(client, db_session):
    _seed_clients(db_session)
    _seed_order(
        db_session, total=100.0, boards=2, created_at=datetime(2026, 6, 1, 9, 0)
    )
    _seed_order(db_session, total=50.0, boards=1, created_at=datetime(2026, 6, 3, 9, 0))

    data = client.get(
        "/api/v1/analytics/timeseries",
        params={"from": "2026-06-01", "to": "2026-06-03", "granularity": "day"},
    ).json()["data"]

    assert data["granularity"] == "day"
    assert data["buckets"] == ["2026-06-01", "2026-06-02", "2026-06-03"]
    assert data["series"]["revenue"] == [100.0, 0.0, 50.0]
    assert data["series"]["orderCount"] == [1, 0, 1]
    assert data["series"]["boardsConsumed"] == [2, 0, 1]


def test_timeseries_monthly_buckets(client, db_session):
    _seed_clients(db_session)
    _seed_order(db_session, total=100.0, created_at=datetime(2026, 6, 20, 9, 0))

    data = client.get(
        "/api/v1/analytics/timeseries",
        params={"from": "2026-05-15", "to": "2026-07-10", "granularity": "month"},
    ).json()["data"]

    assert data["buckets"] == ["2026-05-01", "2026-06-01", "2026-07-01"]
    assert data["series"]["revenue"] == [0.0, 100.0, 0.0]


def test_timeseries_monthly_crosses_year_boundary(client, db_session):
    _seed_clients(db_session)
    _seed_order(db_session, total=100.0, created_at=datetime(2026, 1, 10, 9, 0))

    data = client.get(
        "/api/v1/analytics/timeseries",
        params={"from": "2025-12-01", "to": "2026-01-31", "granularity": "month"},
    ).json()["data"]

    assert data["buckets"] == ["2025-12-01", "2026-01-01"]
    assert data["series"]["revenue"] == [0.0, 100.0]


def test_timeseries_weekly_buckets(client, db_session):
    _seed_clients(db_session)
    # 2026-06-01 es lunes; las semanas ISO arrancan en 06-01 y 06-08.
    _seed_order(db_session, total=100.0, created_at=datetime(2026, 6, 3, 9, 0))
    _seed_order(db_session, total=50.0, created_at=datetime(2026, 6, 10, 9, 0))

    data = client.get(
        "/api/v1/analytics/timeseries",
        params={"from": "2026-06-01", "to": "2026-06-14", "granularity": "week"},
    ).json()["data"]

    assert data["buckets"] == ["2026-06-01", "2026-06-08"]
    assert data["series"]["revenue"] == [100.0, 50.0]


def test_timeseries_new_clients_counts_first_order_only(client, db_session):
    _seed_clients(db_session, 3)
    # Cliente 1: primer pedido el 06-01, segundo el 06-02 (no recuenta).
    _seed_order(db_session, client_id=1, created_at=datetime(2026, 6, 1, 9, 0))
    _seed_order(db_session, client_id=1, created_at=datetime(2026, 6, 2, 9, 0))
    # Cliente 2: nuevo el 06-02.
    _seed_order(db_session, client_id=2, created_at=datetime(2026, 6, 2, 9, 0))
    # Cliente 3: su primer pedido fue antes del rango → no es "nuevo" aquí.
    _seed_order(db_session, client_id=3, created_at=datetime(2026, 5, 1, 9, 0))
    _seed_order(db_session, client_id=3, created_at=datetime(2026, 6, 2, 9, 0))

    data = client.get(
        "/api/v1/analytics/timeseries",
        params={"from": "2026-06-01", "to": "2026-06-03", "granularity": "day"},
    ).json()["data"]

    assert data["series"]["newClients"] == [1, 1, 0]


# ------------------------------------------------------------- breakdown/status
def test_breakdown_status_densifies_all_states(client, db_session):
    _seed_clients(db_session)
    _seed_order(db_session, status="completed", total=100.0)
    _seed_order(db_session, status="completed", total=200.0)
    _seed_order(db_session, status="cancelled", total=50.0)

    data = client.get("/api/v1/analytics/breakdown/status", params=_RANGE).json()[
        "data"
    ]

    assert data["dimension"] == "status"
    assert len(data["items"]) == 7  # todos los OrderStatus
    by_key = {it["key"]: it for it in data["items"]}
    assert by_key["completed"]["orderCount"] == 2
    assert by_key["completed"]["revenue"] == 300.0
    assert by_key["completed"]["label"] == "Completada"
    assert by_key["cancelled"]["orderCount"] == 1
    assert by_key["cancelled"]["revenue"] == 50.0
    assert by_key["confirmed"]["orderCount"] == 0  # densificado en cero


def test_breakdown_status_empty_range(client):
    data = client.get("/api/v1/analytics/breakdown/status", params=_RANGE).json()[
        "data"
    ]
    assert len(data["items"]) == 7
    assert all(it["orderCount"] == 0 and it["revenue"] == 0 for it in data["items"])


# ------------------------------------------------------------------ operations
def test_operations_efficiency_mirrors_summary(client, db_session):
    _seed_clients(db_session)
    _seed_order(db_session, status="completed", lines=[_board_line(90.0, 10.0)])
    _seed_order(db_session, status="completed", lines=[_board_line(70.0, 30.0)])

    data = client.get("/api/v1/analytics/operations", params=_RANGE).json()["data"]
    assert data["averageEfficiency"] == 75.0
    assert data["totalAreaCutM2"] == 40.0
    assert data["wasteEstimateM2"] == 10.0


def test_operations_lifecycle_dwell_times(client, db_session):
    _seed_clients(db_session)
    history = [
        _hist("confirmed", datetime(2026, 6, 15, 0, 0)),
        _hist("queued", datetime(2026, 6, 15, 2, 0), from_status="confirmed"),
        _hist("cutting", datetime(2026, 6, 15, 5, 0), from_status="queued"),
    ]
    _seed_order(db_session, status="cutting", history=history)

    data = client.get("/api/v1/analytics/operations", params=_RANGE).json()["data"]
    cycle = {(d["fromStatus"], d["toStatus"]): d for d in data["lifecycle"]}
    assert cycle[("confirmed", "queued")]["avgHours"] == 2.0
    assert cycle[("confirmed", "queued")]["sampleCount"] == 1
    assert cycle[("queued", "cutting")]["avgHours"] == 3.0


def test_operations_empty_range(client):
    data = client.get("/api/v1/analytics/operations", params=_RANGE).json()["data"]
    assert data["averageEfficiency"] == 0
    assert data["totalAreaCutM2"] == 0
    assert data["wasteEstimateM2"] == 0
    assert data["lifecycle"] == []
