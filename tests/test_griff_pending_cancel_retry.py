"""Failed-cancel resilience for GRIFF pending breakout orders in griff_engine_live.py.

Reproduces the 2026-10-02 17:00:22 ET incident: a PENDING_PLACED setup expired,
the broker rejected the cancel of SELL STOP ticket 172734108 with
``BROKER_ERROR Market is closed``, and the engine forgot the ticket anyway.

These tests prove:
  (1) a broker cancel error does not clear the tracked pending id or move the
      state machine on as if the order were gone;
  (2) a later successful cancel, or broker confirmation that the order is
      already gone, clears tracking;
  (3) restart/reconcile retries an unconfirmed cancel instead of adopting or
      ignoring a leftover GRIFF_ pending whose setup window expired.

No network, no MetaAPI: the broker is a small in-memory order book.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from griff_engine_live import GRIFF_ORDER_COMMENT, GriffLiveEngine

SYMBOL = "BTCUSD"
TICKET = "172734108"
MARKET_CLOSED = {"status": "REJECTED", "msg": "BROKER_ERROR Market is closed"}


class FakeBroker:
    """In-memory broker: cancel results are scripted, the order book is authoritative."""

    def __init__(self, orders: Optional[List[Dict[str, Any]]] = None) -> None:
        self.orders: Dict[str, Dict[str, Any]] = {str(o["id"]): o for o in (orders or [])}
        self.cancel_results: Dict[str, List[Any]] = {}
        self.cancel_calls: List[str] = []
        self.book_available = True

    def script_cancel(self, order_id: str, *results: Any) -> None:
        self.cancel_results[str(order_id)] = list(results)

    async def cancel_order(self, order_id: str) -> Any:
        oid = str(order_id)
        self.cancel_calls.append(oid)
        scripted = self.cancel_results.get(oid)
        if scripted:
            result = scripted.pop(0)
        else:
            result = {"status": "CANCELED"}
        if isinstance(result, Exception):
            raise result
        if isinstance(result, dict) and result.get("status") == "CANCELED":
            self.orders.pop(oid, None)
        return result

    async def get_orders_rest(self) -> Optional[List[Dict[str, Any]]]:
        if not self.book_available:
            return None
        return list(self.orders.values())


def pending_order(
    order_id: str = TICKET,
    order_type: str = "ORDER_TYPE_SELL_STOP",
    placed_at: Optional[datetime] = None,
    comment: str = GRIFF_ORDER_COMMENT,
    symbol: str = SYMBOL,
) -> Dict[str, Any]:
    return {
        "id": order_id,
        "type": order_type,
        "state": "ORDER_STATE_PLACED",
        "symbol": symbol,
        "comment": comment,
        "expirationType": "ORDER_TIME_GTC",
        "time": placed_at or datetime.now(timezone.utc),
        "openPrice": 110000.0,
        "volume": 0.5,
    }


def build_candles(latest_bar_time: datetime, count: int = 60) -> List[Dict[str, Any]]:
    """Trending 1H candles ending at latest_bar_time; the last bar is never an inside bar."""
    candles: List[Dict[str, Any]] = []
    first_time = latest_bar_time - timedelta(hours=count - 1)
    for i in range(count):
        base = 100000.0 + i * 40.0
        candles.append(
            {
                "time": first_time + timedelta(hours=i),
                "open": base,
                "high": base + 120.0,
                "low": base - 80.0,
                "close": base + 60.0,
            }
        )
    return candles


def make_engine(broker: FakeBroker, candles: List[Dict[str, Any]]) -> GriffLiveEngine:
    engine = GriffLiveEngine(token="test-token", symbol=SYMBOL)
    wrapper = MagicMock()
    wrapper._to_mt5 = lambda sym: sym
    wrapper.cancel_order = AsyncMock(side_effect=broker.cancel_order)
    wrapper.get_orders_rest = AsyncMock(side_effect=broker.get_orders_rest)
    engine.wrapper = wrapper
    engine.fetch_account_information_safe = AsyncMock(return_value={"equity": 100000.0})
    engine.fetch_positions_safe = AsyncMock(return_value=[])
    engine.fetch_completed_1h_candles = AsyncMock(return_value=candles)
    engine.place_pending_breakout_orders = AsyncMock(return_value=True)
    return engine


def arm_expired_setup(engine: GriffLiveEngine, latest_bar_time: datetime) -> None:
    """Put the engine in PENDING_PLACED for a setup bar older than the latest completed bar."""
    engine.state = "PENDING_PLACED"
    engine.pending_sell_order_id = TICKET
    engine.pending_setup_bar_time = latest_bar_time - timedelta(hours=1)


LATEST_BAR = datetime(2026, 10, 2, 20, 0, tzinfo=timezone.utc)  # 16:00 ET bar, completed 17:00 ET


# ---------------------------------------------------------------------------
# (1) A broker cancel error must not forget the order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rejected_cancel_keeps_ticket_tracked_and_blocks_searching() -> None:
    broker = FakeBroker([pending_order()])
    broker.script_cancel(TICKET, MARKET_CLOSED, MARKET_CLOSED)
    engine = make_engine(broker, build_candles(LATEST_BAR))
    arm_expired_setup(engine, LATEST_BAR)

    result = await engine.step()

    assert result["status"] == "CANCEL_PENDING"
    assert engine.state == "CANCEL_PENDING"
    assert engine.pending_sell_order_id == TICKET, "a rejected cancel must not clear the tracked id"
    assert TICKET in engine.unconfirmed_cancel_order_ids
    assert broker.cancel_calls == [TICKET], "the engine must have asked the broker to cancel"
    assert TICKET in broker.orders, "fixture sanity: the broker still has the order working"
    engine.place_pending_breakout_orders.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_exception_keeps_ticket_tracked() -> None:
    broker = FakeBroker([pending_order()])
    broker.script_cancel(TICKET, RuntimeError("TRADE_RETCODE_MARKET_CLOSED"))
    engine = make_engine(broker, build_candles(LATEST_BAR))
    arm_expired_setup(engine, LATEST_BAR)

    await engine.step()

    assert engine.state == "CANCEL_PENDING"
    assert engine.pending_sell_order_id == TICKET
    assert engine.unconfirmed_cancel_order_ids == {TICKET: 1}


@pytest.mark.asyncio
async def test_accepted_cancel_but_order_still_on_book_is_not_confirmed() -> None:
    """The order book, not the cancel response, decides whether the order is gone."""
    broker = FakeBroker([pending_order()])
    broker.script_cancel(TICKET, {"status": "CANCELED_BUT_LYING"})  # not CANCELED: book keeps the order
    engine = make_engine(broker, build_candles(LATEST_BAR))
    arm_expired_setup(engine, LATEST_BAR)

    await engine.step()

    assert engine.state == "CANCEL_PENDING"
    assert engine.pending_sell_order_id == TICKET
    assert TICKET in engine.unconfirmed_cancel_order_ids


@pytest.mark.asyncio
async def test_unreadable_order_book_keeps_ticket_tracked() -> None:
    broker = FakeBroker([pending_order()])
    broker.book_available = False
    engine = make_engine(broker, build_candles(LATEST_BAR))
    arm_expired_setup(engine, LATEST_BAR)

    await engine.step()

    assert engine.state == "CANCEL_PENDING"
    assert engine.pending_sell_order_id == TICKET
    assert TICKET in engine.unconfirmed_cancel_order_ids


@pytest.mark.asyncio
async def test_rejected_cancel_is_retried_on_every_cycle() -> None:
    broker = FakeBroker([pending_order()])
    broker.script_cancel(TICKET, MARKET_CLOSED, MARKET_CLOSED, MARKET_CLOSED)
    engine = make_engine(broker, build_candles(LATEST_BAR))
    arm_expired_setup(engine, LATEST_BAR)

    for _ in range(3):
        await engine.step()

    assert broker.cancel_calls == [TICKET, TICKET, TICKET]
    assert engine.unconfirmed_cancel_order_ids == {TICKET: 3}
    assert engine.pending_sell_order_id == TICKET
    assert engine.state == "CANCEL_PENDING"
    engine.place_pending_breakout_orders.assert_not_called()


# ---------------------------------------------------------------------------
# (2) Broker confirmation that the order is gone clears tracking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_later_successful_cancel_clears_tracking_and_resumes_searching() -> None:
    broker = FakeBroker([pending_order()])
    broker.script_cancel(TICKET, MARKET_CLOSED, MARKET_CLOSED)  # third attempt succeeds
    engine = make_engine(broker, build_candles(LATEST_BAR))
    arm_expired_setup(engine, LATEST_BAR)

    await engine.step()
    await engine.step()
    assert engine.state == "CANCEL_PENDING"

    result = await engine.step()

    assert TICKET not in broker.orders
    assert result["status"] == "SEARCHING"
    assert engine.state == "SEARCHING"
    assert engine.pending_sell_order_id is None
    assert engine.pending_buy_order_id is None
    assert engine.unconfirmed_cancel_order_ids == {}
    assert broker.cancel_calls == [TICKET, TICKET, TICKET]


@pytest.mark.asyncio
async def test_order_deleted_manually_counts_as_confirmed_gone() -> None:
    """Cancel errors on an order the book no longer lists (deleted by hand) clear tracking."""
    broker = FakeBroker([pending_order()])
    broker.script_cancel(TICKET, MARKET_CLOSED, {"status": "REJECTED", "msg": "Invalid order ticket"})
    engine = make_engine(broker, build_candles(LATEST_BAR))
    arm_expired_setup(engine, LATEST_BAR)

    await engine.step()
    assert engine.state == "CANCEL_PENDING"

    del broker.orders[TICKET]  # operator deleted the ticket in the terminal
    await engine.step()

    assert engine.state == "SEARCHING"
    assert engine.pending_sell_order_id is None
    assert engine.unconfirmed_cancel_order_ids == {}


@pytest.mark.asyncio
async def test_successful_expiry_cancel_path_unchanged() -> None:
    """Regression: a cancel confirmed on the first attempt goes straight back to SEARCHING."""
    broker = FakeBroker([pending_order()])
    engine = make_engine(broker, build_candles(LATEST_BAR))
    arm_expired_setup(engine, LATEST_BAR)

    result = await engine.step()

    assert broker.cancel_calls == [TICKET]
    assert result["status"] == "SEARCHING"
    assert engine.state == "SEARCHING"
    assert engine.pending_sell_order_id is None
    assert engine.unconfirmed_cancel_order_ids == {}


@pytest.mark.asyncio
async def test_opposite_leg_cancel_failure_on_position_adoption_is_retried_in_trade() -> None:
    """IN_TRADE adoption cancels the unfilled leg; a rejected cancel is retried without leaving IN_TRADE."""
    buy_leg = pending_order(order_id="900001", order_type="ORDER_TYPE_BUY_STOP")
    broker = FakeBroker([buy_leg])
    broker.script_cancel("900001", MARKET_CLOSED)
    engine = make_engine(broker, build_candles(LATEST_BAR))
    engine.state = "PENDING_PLACED"
    engine.pending_buy_order_id = "900001"
    engine.pending_sell_order_id = "900002"  # filled -> position
    engine.pending_setup_bar_time = LATEST_BAR
    engine.fetch_positions_safe = AsyncMock(
        return_value=[
            {
                "id": "900002",
                "symbol": SYMBOL,
                "comment": GRIFF_ORDER_COMMENT,
                "type": "POSITION_TYPE_SELL",
                "openPrice": 109000.0,
                "volume": 0.5,
                "stopLoss": 110500.0,
            }
        ]
    )
    engine.ratchet_trailing_stop = AsyncMock()

    await engine.step()
    assert engine.state == "IN_TRADE"
    assert engine.pending_buy_order_id == "900001"
    assert "900001" in engine.unconfirmed_cancel_order_ids
    assert engine.pending_sell_order_id is None, "the filled leg is no longer on the book"

    # Adoption attempted both tracked legs once; the filled leg is confirmed gone by the book.
    assert broker.cancel_calls == ["900001", "900002"]

    await engine.step()  # market reopened: default cancel result is CANCELED
    assert engine.state == "IN_TRADE"
    assert engine.pending_buy_order_id is None
    assert engine.unconfirmed_cancel_order_ids == {}
    assert broker.cancel_calls == ["900001", "900002", "900001"]


# ---------------------------------------------------------------------------
# (3) Restart / reconcile re-attempts the cancel of an expired orphan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restart_cancels_expired_orphan_and_retries_until_confirmed() -> None:
    """Fresh process, no tracked ids, GTC GRIFF_ SELL STOP placed two hours ago still on the book."""
    now = datetime.now(timezone.utc)
    orphan = pending_order(placed_at=now - timedelta(hours=2))
    broker = FakeBroker([orphan])
    broker.script_cancel(TICKET, MARKET_CLOSED)
    latest_bar = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    engine = make_engine(broker, build_candles(latest_bar))
    assert engine.state == "SEARCHING" and engine.pending_sell_order_id is None

    result = await engine.step()

    assert broker.cancel_calls == [TICKET], "restart must attempt the cancel, not ignore the orphan"
    assert engine.state == "CANCEL_PENDING", "an expired orphan must not be adopted as a live setup"
    assert engine.pending_sell_order_id is None
    assert TICKET in engine.unconfirmed_cancel_order_ids
    assert result["status"] == "CANCEL_PENDING"
    engine.place_pending_breakout_orders.assert_not_called()

    await engine.step()  # broker now accepts the cancel

    assert TICKET not in broker.orders
    assert engine.state == "SEARCHING"
    assert engine.unconfirmed_cancel_order_ids == {}
    assert broker.cancel_calls == [TICKET, TICKET]


@pytest.mark.asyncio
async def test_restart_reconcile_deferred_when_order_book_unreadable() -> None:
    now = datetime.now(timezone.utc)
    broker = FakeBroker([pending_order(placed_at=now - timedelta(hours=2))])
    broker.book_available = False
    latest_bar = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    engine = make_engine(broker, build_candles(latest_bar))

    await engine.step()
    assert engine.pending_orders_reconciled is False
    assert broker.cancel_calls == []

    broker.book_available = True
    await engine.step()
    assert engine.pending_orders_reconciled is True
    assert broker.cancel_calls == [TICKET]
    assert engine.state == "SEARCHING"
    assert engine.unconfirmed_cancel_order_ids == {}


@pytest.mark.asyncio
async def test_restart_readopts_pending_whose_window_is_still_live() -> None:
    """A GRIFF_ pending placed in the current hour is still inside its window: track it, do not cancel it."""
    now = datetime.now(timezone.utc)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    live = pending_order(placed_at=current_hour + timedelta(seconds=22))
    broker = FakeBroker([live])
    engine = make_engine(broker, build_candles(current_hour - timedelta(hours=1)))

    result = await engine.step()

    assert broker.cancel_calls == []
    assert engine.state == "PENDING_PLACED"
    assert engine.pending_sell_order_id == TICKET
    assert engine.pending_setup_bar_time == current_hour - timedelta(hours=1)
    assert result["status"] == "PENDING_PLACED"
    engine.place_pending_breakout_orders.assert_not_called()


@pytest.mark.asyncio
async def test_readopted_pending_is_cancelled_when_its_window_expires() -> None:
    """After re-adoption the normal expiry rule applies, with the same retry-until-confirmed behavior."""
    now = datetime.now(timezone.utc)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    broker = FakeBroker([pending_order(placed_at=current_hour + timedelta(seconds=5))])
    broker.script_cancel(TICKET, MARKET_CLOSED)
    engine = make_engine(broker, build_candles(current_hour - timedelta(hours=1)))

    await engine.step()
    assert engine.state == "PENDING_PLACED"

    engine.fetch_completed_1h_candles = AsyncMock(return_value=build_candles(current_hour))  # next bar completed
    await engine.step()
    assert engine.state == "CANCEL_PENDING"
    assert engine.pending_sell_order_id == TICKET
    assert broker.cancel_calls == [TICKET]

    await engine.step()
    assert engine.state == "SEARCHING"
    assert engine.pending_sell_order_id is None
    assert engine.unconfirmed_cancel_order_ids == {}


@pytest.mark.asyncio
async def test_reconcile_ignores_other_symbols_and_non_griff_orders() -> None:
    now = datetime.now(timezone.utc)
    broker = FakeBroker(
        [
            pending_order(order_id="1", symbol="US100.cash", comment="GRIFF_US100_NY", placed_at=now - timedelta(hours=3)),
            pending_order(order_id="2", comment="MANUAL_LIMIT", placed_at=now - timedelta(hours=3)),
        ]
    )
    latest_bar = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    engine = make_engine(broker, build_candles(latest_bar))

    await engine.step()

    assert broker.cancel_calls == []
    assert engine.state == "SEARCHING"
    assert engine.unconfirmed_cancel_order_ids == {}


@pytest.mark.asyncio
async def test_duplicate_griff_pendings_of_same_type_are_not_both_adopted() -> None:
    now = datetime.now(timezone.utc)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    broker = FakeBroker(
        [
            pending_order(order_id="A", placed_at=current_hour + timedelta(seconds=5)),
            pending_order(order_id="B", placed_at=current_hour + timedelta(seconds=9)),
        ]
    )
    engine = make_engine(broker, build_candles(current_hour - timedelta(hours=1)))

    await engine.step()

    assert engine.state == "PENDING_PLACED"
    assert engine.pending_sell_order_id == "A"
    assert broker.cancel_calls == ["B"]
    assert "B" not in broker.orders
    assert engine.unconfirmed_cancel_order_ids == {}


# ---------------------------------------------------------------------------
# Unit-level checks on the cancel primitive
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_pending_breakout_orders_returns_true_when_nothing_tracked() -> None:
    broker = FakeBroker()
    engine = make_engine(broker, build_candles(LATEST_BAR))
    assert await engine.cancel_pending_breakout_orders() is True
    assert broker.cancel_calls == []


@pytest.mark.asyncio
async def test_cancel_pending_breakout_orders_also_cancels_stray_griff_orders() -> None:
    broker = FakeBroker([pending_order(order_id="tracked"), pending_order(order_id="stray", order_type="ORDER_TYPE_BUY_STOP")])
    engine = make_engine(broker, build_candles(LATEST_BAR))
    engine.pending_sell_order_id = "tracked"

    assert await engine.cancel_pending_breakout_orders() is True
    assert sorted(broker.cancel_calls) == ["stray", "tracked"]
    assert broker.orders == {}
    assert engine.pending_sell_order_id is None


@pytest.mark.asyncio
async def test_missing_wrapper_cancel_keeps_order_tracked() -> None:
    engine = GriffLiveEngine(token="test-token", symbol=SYMBOL)
    engine.wrapper = None
    engine.pending_sell_order_id = TICKET

    assert await engine.cancel_pending_breakout_orders() is False
    assert engine.pending_sell_order_id == TICKET
    assert TICKET in engine.unconfirmed_cancel_order_ids
