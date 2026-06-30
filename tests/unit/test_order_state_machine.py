"""Unidad: máquina de estados de ``OrderService.transition`` (sin DB).

Construye un ``OrderModel`` transitorio (sin sesión) y reemplaza la carga por id
(``get_scoped_or_404``) por el objeto en mano, de modo que se ejercitan los *gates*
de la transición sin tocar PostgreSQL. Es el patrón de referencia para probar lógica
de servicio con ``mock_session``: cada camino que rechaza la transición **no** debe
llamar a ``commit``.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.modules.orders.model import OrderModel, OrderStatus
from src.modules.orders.schemas import OrderPaymentInput
from src.modules.orders.service import OrderService, _has_payment, _progress
from src.modules.users.enums import UserRole
from src.shared.audit import Actor
from src.shared.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    ValidationError,
)


def _order(
    status: OrderStatus, *, banding_status: str = "not_applicable"
) -> OrderModel:
    """Orden transitoria (sin sesión) en el estado pedido."""
    order = OrderModel(status=status.value, banding_status=banding_status)
    order.id = 1
    return order


def _service(mock_session, order: OrderModel) -> OrderService:
    svc = OrderService(mock_session)
    # La carga por id con scope de sucursal se sustituye por la orden en mano.
    svc.get_scoped_or_404 = lambda *a, **k: order
    return svc


def _actor(role: UserRole | None) -> Actor:
    return Actor("staff", user_id=1, label="Tester", role=role.value if role else None)


# --- Transiciones inválidas / autorización -----------------------------------
def test_invalid_transition_raises_and_does_not_commit(mock_session):
    svc = _service(mock_session, _order(OrderStatus.confirmed))
    with pytest.raises(BusinessRuleError):
        svc.transition(1, OrderStatus.cutting, actor=_actor(UserRole.ADMIN))
    mock_session.commit.assert_not_called()


def test_role_gate_blocks_unauthorized_role(mock_session):
    svc = _service(mock_session, _order(OrderStatus.confirmed))
    # confirmed → queued solo lo pueden hacer admin/vendedor, no el operador.
    with pytest.raises(AuthorizationError):
        svc.transition(1, OrderStatus.queued, actor=_actor(UserRole.OPERATOR))
    mock_session.commit.assert_not_called()


# --- Gate de forma de pago (confirmed → queued) ------------------------------
def test_queued_requires_payment(mock_session):
    svc = _service(mock_session, _order(OrderStatus.confirmed))
    with pytest.raises(ValidationError):
        svc.transition(
            1, OrderStatus.queued, actor=_actor(UserRole.ADMIN), payment=None
        )
    mock_session.commit.assert_not_called()


def test_queued_with_payment_freezes_amount_and_commits(mock_session):
    order = _order(OrderStatus.confirmed)
    svc = _service(mock_session, order)
    svc.transition(
        1,
        OrderStatus.queued,
        actor=_actor(UserRole.ADMIN),
        payment=OrderPaymentInput(cash_amount=50.0),
    )
    assert order.status == OrderStatus.queued.value
    assert order.payment_cash_amount == 50.0
    mock_session.commit.assert_called_once()


# --- Gate de producción (cutting → cut) --------------------------------------
def test_cut_blocked_while_pieces_pending(mock_session):
    order = _order(OrderStatus.cutting)
    svc = _service(mock_session, order)
    svc._ensure_cutting_plan = lambda o: None  # el plan ya está materializado
    mock_session.query.return_value.filter.return_value.count.return_value = 2
    with pytest.raises(BusinessRuleError):
        svc.transition(1, OrderStatus.cut, actor=_actor(UserRole.OPERATOR))
    mock_session.commit.assert_not_called()


# --- Gate de cierre (banding pendiente) --------------------------------------
def test_completed_blocked_when_banding_pending(mock_session):
    order = _order(OrderStatus.cut, banding_status="in_progress")
    svc = _service(mock_session, order)
    with pytest.raises(BusinessRuleError):
        svc.transition(1, OrderStatus.completed, actor=_actor(UserRole.ADMIN))
    mock_session.commit.assert_not_called()


# --- Helpers puros -----------------------------------------------------------
def test_has_payment_true_only_when_some_amount_positive():
    assert _has_payment(None) is False
    assert _has_payment(OrderPaymentInput(cash_amount=0, credit_amount=0)) is False
    assert _has_payment(OrderPaymentInput(cash_amount=10)) is True
    assert _has_payment(OrderPaymentInput(credit_amount=5)) is True


def test_progress_counts_cut_pieces():
    pieces = [
        SimpleNamespace(cut_at=datetime.utcnow()),
        SimpleNamespace(cut_at=None),
        SimpleNamespace(cut_at=None),
    ]
    progress = _progress(pieces)
    assert progress.cut_pieces == 1
    assert progress.total_pieces == 3
