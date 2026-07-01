"""Unit: edge-banding track of ``OrderService.transition_banding`` (no DB).

A track parallel to and independent from cutting: advances ``pending ->
in_progress -> done``, forward-only and idempotent. Same pattern as the cutting
state machine: transient ``OrderModel`` + ``get_scoped_or_404`` replaced; paths
that reject must not call ``commit``.
"""

import pytest

from src.modules.orders.model import BandingStatus, OrderModel, OrderStatus
from src.modules.orders.service import OrderService
from src.modules.users.enums import UserRole
from src.shared.audit import Actor, system_actor
from src.shared.exceptions import AuthorizationError, BusinessRuleError


def _order(
    banding_status: BandingStatus, *, status: OrderStatus = OrderStatus.cutting
) -> OrderModel:
    order = OrderModel(status=status.value, banding_status=banding_status.value)
    order.id = 1
    order.code = "ORD-2026-0001"
    return order


def _service(mock_session, order: OrderModel) -> OrderService:
    svc = OrderService(mock_session)
    svc.get_scoped_or_404 = lambda *a, **k: order
    return svc


def test_advance_pending_to_in_progress_commits(mock_session):
    order = _order(BandingStatus.pending)
    svc = _service(mock_session, order)
    resp = svc.transition_banding(1, BandingStatus.in_progress, actor=system_actor())
    assert order.banding_status == BandingStatus.in_progress.value
    assert resp.banding_status == BandingStatus.in_progress
    mock_session.commit.assert_called_once()


def test_reapplying_same_status_is_noop(mock_session):
    order = _order(BandingStatus.pending)
    svc = _service(mock_session, order)
    resp = svc.transition_banding(1, BandingStatus.pending, actor=system_actor())
    assert resp.banding_status == BandingStatus.pending
    mock_session.commit.assert_not_called()


def test_skipping_in_progress_is_invalid(mock_session):
    order = _order(BandingStatus.pending)
    svc = _service(mock_session, order)
    with pytest.raises(BusinessRuleError):
        svc.transition_banding(1, BandingStatus.done, actor=system_actor())
    mock_session.commit.assert_not_called()


def test_order_without_banding_rejects(mock_session):
    order = _order(BandingStatus.not_applicable)
    svc = _service(mock_session, order)
    with pytest.raises(BusinessRuleError):
        svc.transition_banding(1, BandingStatus.in_progress, actor=system_actor())
    mock_session.commit.assert_not_called()


def test_banding_requires_order_in_cutting_or_cut(mock_session):
    order = _order(BandingStatus.pending, status=OrderStatus.confirmed)
    svc = _service(mock_session, order)
    with pytest.raises(BusinessRuleError):
        svc.transition_banding(1, BandingStatus.in_progress, actor=system_actor())
    mock_session.commit.assert_not_called()


def test_unauthorized_role_cannot_band(mock_session):
    order = _order(BandingStatus.pending)
    svc = _service(mock_session, order)
    seller = Actor("staff", user_id=2, label="Vendedor", role=UserRole.SELLER.value)
    with pytest.raises(AuthorizationError):
        svc.transition_banding(1, BandingStatus.in_progress, actor=seller)
    mock_session.commit.assert_not_called()
