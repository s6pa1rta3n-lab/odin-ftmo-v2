"""Gold double-book guard (port of the US100 place-time guard).

The 2026-10-02 race on matt-berserker (US100): the broker filled BUY 9.46
(position 172673462), the hub then answered NOT_CONNECTED for that same
mutation, the engine stayed SEARCHING without re-reading positions and
placed BUY 8.88 (172676142) on top of the live book five minutes later.

``griff_engine_gold.py`` had the identical place pattern (catch, log, do
nothing). These tests drive the real ``GoldEngine`` against the in-process
hub with live orders enabled, arm an Asian-range breakout so the entry
fires on every SEARCHING step, script the broker to "fill, then lose the
ack", and assert that exactly one Gold position is ever opened. The
startup/reconnect adoption from ``modules/book_sync.py`` is left in place
and exercised alongside.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest
import pytz

import griff_engine_gold as engine_mod
from griff_engine_gold import GoldEngine
from metaapi_hub.errors import NotConnectedError, OrdersDisabledError
from metaapi_hub.harness import start_hub
from modules.entry_guard import matching_positions, should_skip_entry

GOLD = "XAUUSD"
EASTERN = pytz.timezone("US/Eastern")

# A Gold ticket as the hub reports positions: the fill whose ack is lost.
FILLED_GOLD = {
    "id": "172690101",
    "symbol": GOLD,
    "type": "POSITION_TYPE_BUY",
    "volume": 0.83,
    "openPrice": 100.2,
    "stopLoss": 98.7,
    "takeProfit": 103.2,
    "comment": "GRIFF_GOLD_BREAKOUT",
}
# A Gold ticket some other process (or an earlier instance) already holds.
OTHER_GOLD = {
    "id": "172690001",
    "symbol": GOLD,
    "type": "POSITION_TYPE_SELL",
    "volume": 0.50,
    "openPrice": 3851.20,
    "stopLoss": 3863.95,
    "takeProfit": 3825.70,
    "comment": "GRIFF_GOLD_BREAKOUT",
}
US100_BOOK = {
    "id": "172676142",
    "symbol": "US100.cash",
    "type": "POSITION_TYPE_BUY",
    "volume": 8.88,
    "openPrice": 30807.38,
    "comment": "GRIFF_US100_NY",
}
BTC_BOOK = {
    "id": "900000001",
    "symbol": "BTCUSD",
    "type": "POSITION_TYPE_BUY",
    "volume": 1.0,
    "comment": "GRIFF_1H_BREAKOUT",
}


# ---------------------------------------------------------------------------
# Pure helper, Gold identifiers
# ---------------------------------------------------------------------------


def test_gold_book_matches_by_symbol_or_comment_prefix_and_ignores_other_books() -> None:
    aliased = {"id": "5", "symbol": "XAUUSD.m", "comment": "GRIFF_GOLD_BREAKOUT"}
    rewritten_comment = {"id": "6", "symbol": GOLD, "brokerComment": "[sl 3863.95]"}
    positions = [BTC_BOOK, US100_BOOK, FILLED_GOLD, aliased, rewritten_comment]

    matched = matching_positions(positions, symbol=GOLD, comment_prefix="GRIFF_GOLD")
    assert [p["id"] for p in matched] == [FILLED_GOLD["id"], "5", "6"]
    assert matching_positions([BTC_BOOK, US100_BOOK], symbol=GOLD, comment_prefix="GRIFF_GOLD") == []

    kwargs = {"symbol": GOLD, "comment_prefix": "GRIFF_GOLD"}
    assert should_skip_entry(None, None, **kwargs) is True
    assert should_skip_entry([FILLED_GOLD], None, **kwargs) is True
    assert should_skip_entry([], NotConnectedError(), **kwargs) is True
    assert should_skip_entry([BTC_BOOK, US100_BOOK], None, **kwargs) is False
    assert should_skip_entry([], OrdersDisabledError(), **kwargs) is False


# ---------------------------------------------------------------------------
# Engine against the in-process hub
# ---------------------------------------------------------------------------


async def _no_sleep(_seconds: float) -> None:
    return None


def _owner_kwargs() -> dict:
    return {"sleep": _no_sleep, "backoff_base": 0.0, "candle_stale_ttl": 0.0}


def _at(hour: int, minute: int):
    def _clock() -> datetime:
        return EASTERN.localize(datetime(2026, 10, 2, hour, minute, 0))

    return _clock


async def _live_hub(orders_mode: str = "live"):
    return await start_hub(mode="live", orders_mode=orders_mode, account_id="live-account", owner_kwargs=_owner_kwargs())


async def _armed_engine(handle, monkeypatch: pytest.MonkeyPatch) -> GoldEngine:
    """GoldEngine at 05:00 ET with an Asian range below the default hub ask.

    The default hub price (bid 100.0 / ask 100.2) is above ``asian_high``, so
    the BUY breakout fires on every SEARCHING step, like the US100 pullback
    does in its guard tests.
    """

    monkeypatch.setenv("ODIN_METAAPI_HUB", "on")
    monkeypatch.setenv("ODIN_METAAPI_HUB_ORDERS", "live")
    monkeypatch.setenv("ODIN_METAAPI_HUB_SOCKET", handle.socket_path)
    engine = GoldEngine(token="unused", account_id="live-account")
    engine.post_place_error_sync_delay = 0.0
    monkeypatch.setattr(engine, "get_est_time", _at(5, 0))
    engine.asian_high = 50.0
    engine.asian_low = 10.0
    assert await engine.connect() is True
    return engine


def _quiet_price(handle) -> None:
    """Price inside the armed range: the engine polls but no breakout fires."""

    handle.broker.prices[GOLD] = {"symbol": GOLD, "bid": 30.0, "ask": 30.2, "bidPrice": 30.0, "askPrice": 30.2}


def _breakout_price(handle) -> None:
    handle.broker.prices.pop(GOLD, None)


def _fill_then_lose_ack(handle, position: dict):
    """Script the broker: first market order fills and raises NOT_CONNECTED; later ones fill normally."""

    original = handle.broker.create_market_order
    calls = {"count": 0}

    async def scripted(payload: dict) -> dict:
        calls["count"] += 1
        if calls["count"] == 1:
            handle.broker.order_calls += 1
            handle.broker.mutation_calls += 1
            handle.broker.orders.append({**payload, "kind": "market"})
            handle.broker.positions.append(dict(position))
            handle.broker.connected = False
            raise NotConnectedError("not connected to broker")
        return await original(payload)

    handle.broker.create_market_order = scripted  # type: ignore[method-assign]
    return calls


def _assert_adopted(engine: GoldEngine, ticket: dict) -> None:
    assert engine.state == "IN_TRADE"
    position = engine.active_position
    assert position["id"] == ticket["id"]
    assert position["volume"] == ticket["volume"]
    assert position["stopLoss"] == ticket["stopLoss"]
    assert position["takeProfit"] == ticket["takeProfit"]
    assert position["comment"] == ticket["comment"]


def test_gold_fill_then_not_connected_adopts_the_fill_instead_of_placing_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """The US100 sequence replayed on Gold. Only one order may ever reach the broker."""

    async def _run() -> None:
        handle = await _live_hub()
        calls = _fill_then_lose_ack(handle, FILLED_GOLD)
        engine = await _armed_engine(handle, monkeypatch)
        try:
            assert engine.state == "SEARCHING"

            # place -> broker fill -> NOT_CONNECTED for that same mutation.
            await engine.step()
            assert calls["count"] == 1
            assert handle.broker.order_calls == 1
            _assert_adopted(engine, FILLED_GOLD)
            assert engine.entry_sync_required is False
            assert engine.last_place_error is None
            # The adopted fill is today's trade: same bookkeeping as a confirmed success.
            assert engine.day_triggered is True
            assert engine.asian_high == 0

            # The breakout condition is still true on every step. Before the
            # port this placed a second Gold order on top of the live one.
            for _ in range(5):
                await engine.step()
            assert handle.broker.order_calls == 1, "second entry was placed on top of the live book"
            assert len(handle.broker.positions) == 1
            _assert_adopted(engine, FILLED_GOLD)

            # The book closes (SL hit). One confirmed empty read returns to SEARCHING.
            handle.broker.positions = []
            await engine.step()
            assert engine.state == "SEARCHING"
            assert engine.active_position is None

            # One trade per day: nothing more is placed this session.
            for _ in range(3):
                await engine.step()
            assert handle.broker.order_calls == 1
            assert engine.state == "SEARCHING"

            # Next day: the midnight reset and a fresh range. A normal entry
            # still works once flat is confirmed.
            monkeypatch.setattr(engine, "get_est_time", _at(0, 1))
            await engine.step()
            assert engine.day_triggered is False
            monkeypatch.setattr(engine, "get_est_time", _at(5, 0))
            engine.asian_high = 50.0
            engine.asian_low = 10.0
            await engine.step()
            assert handle.broker.order_calls == 2
            assert engine.state == "IN_TRADE"
            assert engine.active_position["id"] == "pos-2"
            assert engine.day_triggered is True
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_gold_not_connected_without_a_fill_stays_searching_and_may_enter_later(monkeypatch: pytest.MonkeyPatch) -> None:
    """A genuine failure (nothing filled) must not wedge the engine or burn the day's one trade."""

    async def _run() -> None:
        handle = await _live_hub()
        engine = await _armed_engine(handle, monkeypatch)
        try:
            handle.broker.fail_mutations_remaining = 1
            await engine.step()
            assert handle.broker.order_calls == 1
            assert handle.broker.positions == []
            assert engine.state == "SEARCHING"
            # The reconciling read succeeded and found nothing, so entries are open again.
            assert engine.entry_sync_required is False
            assert engine.last_place_error is None
            # Pre-existing behaviour: a failed place does not count as the day's trade.
            assert engine.day_triggered is False
            assert engine.asian_high == 50.0

            await engine.step()
            assert handle.broker.order_calls == 2
            assert engine.state == "IN_TRADE"
            assert engine.active_position["id"] == "pos-2"
            assert engine.day_triggered is True
            assert engine.asian_high == 0
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_gold_entry_is_blocked_until_a_position_read_succeeds_after_an_ambiguous_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NOT_CONNECTED on place, then position reads also fail: no entry until reads recover."""

    async def _run() -> None:
        handle = await _live_hub()
        calls = _fill_then_lose_ack(handle, FILLED_GOLD)
        engine = await _armed_engine(handle, monkeypatch)
        try:
            real_get_positions_rest = engine.wrapper.get_positions_rest

            # The startup book sync and the pre-entry read must succeed (flat)
            # so the order is sent; the post-error read must fail so the
            # engine cannot reconcile yet.
            reads = {"count": 0}

            async def flaky_reads() -> list:
                reads["count"] += 1
                if reads["count"] <= 2:
                    return await real_get_positions_rest()
                raise RuntimeError("TooManyRequests: simulated")

            engine.wrapper.get_positions_rest = flaky_reads  # type: ignore[method-assign]

            await engine.step()
            assert calls["count"] == 1
            assert engine.state == "SEARCHING"
            assert engine.entry_sync_required is True
            assert isinstance(engine.last_place_error, Exception)
            assert engine.position_sync_failures == 1
            # Nothing is confirmed yet, so the day's trade is not booked either.
            assert engine.day_triggered is False

            # The breakout keeps firing, reads keep failing: nothing may be placed
            # and no setup is evaluated. The failing position reads never reach
            # the broker, so its read counter must not move at all (no price or
            # account polls while unreconciled).
            broker_reads_before = handle.broker.read_calls
            for _ in range(4):
                await engine.step()
            assert handle.broker.order_calls == 1
            assert engine.entry_sync_required is True
            assert engine.position_sync_failures == 5
            assert handle.broker.read_calls == broker_reads_before, "unreconciled engine must only reconcile"

            # Reads recover: the fill is found and adopted. Still no second order.
            engine.wrapper.get_positions_rest = real_get_positions_rest  # type: ignore[method-assign]
            await engine.step()
            _assert_adopted(engine, FILLED_GOLD)
            assert engine.entry_sync_required is False
            assert engine.position_sync_failures == 0
            assert engine.day_triggered is True
            assert engine.asian_high == 0
            await engine.step()
            assert handle.broker.order_calls == 1
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_gold_pre_entry_check_adopts_a_position_that_appeared_after_the_startup_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Gold ticket opened by someone else between the startup sync and the trigger is adopted, not added to."""

    async def _run() -> None:
        handle = await _live_hub()
        _quiet_price(handle)
        engine = await _armed_engine(handle, monkeypatch)
        try:
            await engine.step()
            assert engine.state == "SEARCHING"
            assert engine.book_sync.pending is False
            assert handle.broker.order_calls == 0

            handle.broker.positions = [dict(BTC_BOOK), dict(OTHER_GOLD)]
            _breakout_price(handle)
            await engine.step()
            assert handle.broker.order_calls == 0
            assert handle.broker.mutation_calls == 0
            _assert_adopted(engine, OTHER_GOLD)
            # This engine did not place anything, so the day's trade is not booked.
            assert engine.day_triggered is False

            for _ in range(3):
                await engine.step()
            assert handle.broker.order_calls == 0
            _assert_adopted(engine, OTHER_GOLD)
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_gold_pre_entry_read_failure_skips_the_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        handle = await _live_hub()
        _quiet_price(handle)
        engine = await _armed_engine(handle, monkeypatch)
        try:
            await engine.step()
            assert engine.book_sync.pending is False

            real_get_positions_rest = engine.wrapper.get_positions_rest

            async def failing() -> list:
                raise RuntimeError("TooManyRequests: simulated")

            engine.wrapper.get_positions_rest = failing  # type: ignore[method-assign]
            _breakout_price(handle)
            await engine.step()
            assert handle.broker.order_calls == 0
            assert engine.state == "SEARCHING"
            assert engine.position_sync_failures == 1
            assert engine.day_triggered is False

            engine.wrapper.get_positions_rest = real_get_positions_rest  # type: ignore[method-assign]
            await engine.step()
            assert handle.broker.order_calls == 1
            assert engine.state == "IN_TRADE"
            assert engine.day_triggered is True
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_gold_flat_path_places_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sanity: with a flat book the armed breakout places once and then stays IN_TRADE."""

    async def _run() -> None:
        handle = await _live_hub()
        handle.broker.positions = [dict(BTC_BOOK), dict(US100_BOOK)]  # other books are not Gold's
        engine = await _armed_engine(handle, monkeypatch)
        try:
            real_get_positions_rest = engine.wrapper.get_positions_rest
            position_reads: list[int] = []

            async def counted() -> list:
                position_reads.append(handle.broker.order_calls)
                return await real_get_positions_rest()

            engine.wrapper.get_positions_rest = counted  # type: ignore[method-assign]

            await engine.step()
            assert handle.broker.order_calls == 1
            assert engine.state == "IN_TRADE"
            assert engine.active_position["id"] == "pos-1"
            assert engine.active_position["stopLoss"] is not None
            assert engine.active_position["takeProfit"] is not None
            assert engine.day_triggered is True

            # Exactly two position reads, both before the order was sent:
            # the startup book sync and the pre-entry flat check.
            assert position_reads == [0, 0]

            for _ in range(4):
                await engine.step()
            assert handle.broker.order_calls == 1
            assert {order["kind"] for order in handle.broker.orders} == {"market"}
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_gold_guard_never_closes_or_modifies_positions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Across fill-then-error, adoption, and recovery, the only mutations are entries."""

    async def _run() -> None:
        handle = await _live_hub()
        calls = _fill_then_lose_ack(handle, FILLED_GOLD)
        engine = await _armed_engine(handle, monkeypatch)
        try:
            for _ in range(6):
                await engine.step()
            assert calls["count"] == 1
            kinds = {order["kind"] for order in handle.broker.orders}
            assert kinds == {"market"}
            assert handle.broker.mutation_calls == handle.broker.order_calls == 1
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_gold_hub_refusal_does_not_add_the_post_error_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """ORDERS_DISABLED never reached the broker; the engine re-reads positions but does not wait."""

    async def _run() -> None:
        handle = await _live_hub(orders_mode="deny")
        engine = await _armed_engine(handle, monkeypatch)
        engine.post_place_error_sync_delay = 60.0
        slept: list[float] = []

        async def record_sleep(seconds: float) -> None:
            slept.append(seconds)

        monkeypatch.setattr(engine_mod.asyncio, "sleep", record_sleep)
        try:
            await engine.step()
            assert handle.broker.order_calls == 0
            assert engine.state == "SEARCHING"
            assert slept == []
            assert engine.entry_sync_required is False
            assert engine.last_place_error is None
            # A refused order is not a trade: the day stays open, as before.
            assert engine.day_triggered is False
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())
