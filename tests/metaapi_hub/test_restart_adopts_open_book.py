"""Restart / hub-reconnect adoption of an open broker position (US100 and Gold).

The 2026-10-02 restart gap: ``griff_engine_us100`` was restarted at ~11:45 ET
while the broker held BUY ticket 172676142 (US100.cash 8.88 @ 30807.38 with
SL/TP). The process started ``SEARCHING`` and never read positions because
the only position read on that path was the pre-entry check inside the
09:45-11:30 window. The 16:00 hard close is gated on ``IN_TRADE`` and would
not have fired.

These tests drive the real ``US100Engine`` and ``GoldEngine`` against the
in-process hub with live orders enabled, clocks pinned *outside* their entry
windows, and assert that the first loop iteration adopts the open ticket with
the broker's size/SL/TP, that a flat restart stays ``SEARCHING``, that the
existing hard close now fires after a restart, and that no order is ever
placed while a position is already open. Nothing here closes or modifies a
position except the engines' pre-existing 16:00 hard-close path.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

import pytest
import pytz

from griff_engine_gold import GoldEngine
from griff_engine_us100 import US100Engine
from metaapi_hub.harness import start_hub
from modules.book_sync import (
    BookResyncTracker,
    BrokerBookSync,
    adopted_position_record,
    choose_position_to_adopt,
    hub_reattach_count,
)

US100 = "US100.cash"
GOLD = "XAUUSD"
EASTERN = pytz.timezone("US/Eastern")

# Ticket the broker still held when the engine was restarted on 2026-10-02.
OPEN_US100_TICKET = {
    "id": "172676142",
    "symbol": US100,
    "type": "POSITION_TYPE_BUY",
    "volume": 8.88,
    "openPrice": 30807.38,
    "stopLoss": 30715.73,
    "takeProfit": 31011.37,
    "comment": "GRIFF_US100_NY",
}
SECOND_US100_TICKET = {
    "id": "172673462",
    "symbol": US100,
    "type": "POSITION_TYPE_BUY",
    "volume": 9.46,
    "openPrice": 30826.23,
    "stopLoss": 30734.58,
    "takeProfit": 31030.22,
    "comment": "GRIFF_US100_NY",
}
OPEN_GOLD_TICKET = {
    "id": "172690001",
    "symbol": GOLD,
    "type": "POSITION_TYPE_SELL",
    "volume": 0.83,
    "openPrice": 3851.20,
    "stopLoss": 3863.95,
    "takeProfit": 3825.70,
    "comment": "GRIFF_GOLD_BREAKOUT",
}
BTC_BOOK = {
    "id": "172311001",
    "symbol": "BTCUSD",
    "type": "POSITION_TYPE_BUY",
    "volume": 1.12,
    "openPrice": 86404.90,
    "stopLoss": 85724.30,
    "comment": "GRIFF_1H_BREAKOUT",
}


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_adopted_position_record_takes_ticket_size_sl_tp_from_the_broker() -> None:
    record = adopted_position_record(OPEN_US100_TICKET)
    assert record == {
        "id": "172676142",
        "symbol": US100,
        "type": "POSITION_TYPE_BUY",
        "direction": "BUY",
        "volume": 8.88,
        "openPrice": 30807.38,
        "stopLoss": 30715.73,
        "takeProfit": 31011.37,
        "comment": "GRIFF_US100_NY",
    }

    sell = adopted_position_record(OPEN_GOLD_TICKET)
    assert sell["direction"] == "SELL"
    assert sell["stopLoss"] == 3863.95
    assert sell["takeProfit"] == 3825.70

    # Missing fields fall back without inventing broker values.
    sparse = adopted_position_record({"id": 7, "type": "POSITION_TYPE_SELL"}, symbol=US100, comment="GRIFF_US100_NY")
    assert sparse["id"] == "7"
    assert sparse["symbol"] == US100
    assert sparse["direction"] == "SELL"
    assert sparse["volume"] is None
    assert sparse["stopLoss"] is None
    assert sparse["takeProfit"] is None
    assert sparse["comment"] == "GRIFF_US100_NY"

    # brokerComment is honoured when comment is empty.
    rewritten = adopted_position_record({"id": "8", "symbol": US100, "brokerComment": "[sl 30715.73]"})
    assert rewritten["comment"] == "[sl 30715.73]"


def test_choose_position_to_adopt_manages_the_first_and_reports_the_rest() -> None:
    assert choose_position_to_adopt(None) == (None, [])
    assert choose_position_to_adopt([]) == (None, [])
    assert choose_position_to_adopt([OPEN_US100_TICKET]) == (OPEN_US100_TICKET, [])
    first, extras = choose_position_to_adopt([OPEN_US100_TICKET, SECOND_US100_TICKET])
    assert first is OPEN_US100_TICKET
    assert extras == [SECOND_US100_TICKET]


class _FakeClient:
    def __init__(self, reattaches: int) -> None:
        self.reattaches = reattaches


class _FakeWrapper:
    def __init__(self, reattaches: int | None) -> None:
        if reattaches is not None:
            self.client = _FakeClient(reattaches)


def test_resync_tracker_is_due_on_startup_reconnect_and_hub_reattach() -> None:
    hub_wrapper = _FakeWrapper(0)
    tracker = BookResyncTracker()

    assert tracker.pending is True
    assert tracker.resync_reason(hub_wrapper) == "engine startup"
    # A failed read never marks the sync done: still due.
    assert tracker.resync_reason(hub_wrapper) == "engine startup"

    tracker.mark_synced(hub_wrapper)
    assert tracker.pending is False
    assert tracker.resync_reason(hub_wrapper) is None

    # The hub client reattached since the last successful sync.
    hub_wrapper.client.reattaches = 1
    assert tracker.resync_reason(hub_wrapper) == "hub reconnect (reattaches 0 -> 1)"
    tracker.mark_synced(hub_wrapper)
    assert tracker.resync_reason(hub_wrapper) is None

    # The engine re-ran its own connect().
    tracker.note_reconnect("engine reconnected to the execution wrapper")
    assert tracker.pending is True
    assert tracker.resync_reason(hub_wrapper) == "engine reconnected to the execution wrapper"
    tracker.mark_synced(hub_wrapper)
    assert tracker.resync_reason(hub_wrapper) is None
    assert tracker.syncs_completed == 3

    # Direct SDK wrapper: no hub client, only startup and connect() trigger.
    direct = _FakeWrapper(None)
    assert hub_reattach_count(direct) is None
    direct_tracker = BookResyncTracker()
    assert direct_tracker.resync_reason(direct) == "engine startup"
    direct_tracker.mark_synced(direct)
    assert direct_tracker.resync_reason(direct) is None


def test_broker_book_sync_treats_a_failed_read_as_unknown_and_keeps_the_resync_due() -> None:
    class _Wrapper:
        def __init__(self) -> None:
            self.client = _FakeClient(0)
            self.fail = True
            self.positions: list[dict] = []

        async def get_positions_rest(self) -> list:
            if self.fail:
                raise RuntimeError("TooManyRequests: simulated")
            return list(self.positions)

    async def _run() -> None:
        wrapper = _Wrapper()
        sync = BrokerBookSync(book_name="US100", symbol=US100, comment_prefix="GRIFF_US100")

        failed = await sync.sync(wrapper, reason="engine startup", current_state="SEARCHING")
        assert failed == {"ok": False, "matched": None, "adopt": None, "extras": []}
        assert sync.read_failures == 1
        assert sync.pending is True
        assert sync.resync_reason(wrapper) == "engine startup"

        wrapper.fail = False
        wrapper.positions = [dict(BTC_BOOK)]
        flat = await sync.sync(wrapper, reason="engine startup", current_state="SEARCHING")
        assert flat["ok"] is True and flat["matched"] == [] and flat["adopt"] is None
        assert sync.read_failures == 0
        assert sync.pending is False
        assert sync.adoptions == 0

        wrapper.positions = [dict(BTC_BOOK), dict(OPEN_US100_TICKET), dict(SECOND_US100_TICKET)]
        wrapper.client.reattaches = 2
        assert sync.resync_reason(wrapper) == "hub reconnect (reattaches 0 -> 2)"
        adopted = await sync.sync(wrapper, reason="hub reconnect", current_state="SEARCHING")
        assert adopted["ok"] is True
        assert adopted["adopt"]["id"] == OPEN_US100_TICKET["id"]
        assert [p["id"] for p in adopted["extras"]] == [SECOND_US100_TICKET["id"]]
        assert sync.adoptions == 1
        assert sync.resync_reason(wrapper) is None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Engines against the in-process hub
# ---------------------------------------------------------------------------


async def _no_sleep(_seconds: float) -> None:
    return None


def _owner_kwargs() -> dict:
    return {"sleep": _no_sleep, "backoff_base": 0.0, "candle_stale_ttl": 0.0}


def _at(hour: int, minute: int):
    def _clock() -> datetime:
        return EASTERN.localize(datetime(2026, 10, 2, hour, minute, 0))

    return _clock


async def _live_hub(socket_path: str | None = None):
    return await start_hub(
        mode="live",
        orders_mode="live",
        account_id="live-account",
        socket_path=socket_path,
        owner_kwargs=_owner_kwargs(),
    )


def _hub_env(handle, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ODIN_METAAPI_HUB", "on")
    monkeypatch.setenv("ODIN_METAAPI_HUB_ORDERS", "live")
    monkeypatch.setenv("ODIN_METAAPI_HUB_SOCKET", handle.socket_path)


async def _us100(handle, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clock) -> US100Engine:
    _hub_env(handle, monkeypatch)
    config_path = tmp_path / "config_us100.json"
    config_path.write_text(json.dumps({"symbol": US100, "risk_pct": 0.01}), encoding="utf-8")
    engine = US100Engine(token="unused", account_id="live-account", config_path=str(config_path))
    engine.post_place_error_sync_delay = 0.0
    monkeypatch.setattr(engine, "get_est_time", clock)
    assert await engine.connect() is True
    return engine


async def _gold(handle, monkeypatch: pytest.MonkeyPatch, clock) -> GoldEngine:
    _hub_env(handle, monkeypatch)
    engine = GoldEngine(token="unused", account_id="live-account")
    monkeypatch.setattr(engine, "get_est_time", clock)
    assert await engine.connect() is True
    return engine


def _assert_no_mutations(handle) -> None:
    assert handle.broker.order_calls == 0
    assert handle.broker.mutation_calls == 0
    assert handle.broker.orders == []


def _assert_adopted(engine, ticket: dict) -> None:
    assert engine.state == "IN_TRADE"
    position = engine.active_position
    assert position["id"] == ticket["id"]
    assert position["volume"] == ticket["volume"]
    assert position["openPrice"] == ticket["openPrice"]
    assert position["stopLoss"] == ticket["stopLoss"]
    assert position["takeProfit"] == ticket["takeProfit"]
    assert position["comment"] == ticket["comment"]
    assert position["direction"] == ("SELL" if "SELL" in ticket["type"] else "BUY")


# --- US100 -----------------------------------------------------------------


def test_us100_restart_outside_the_window_adopts_the_open_ticket(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The incident: restart at 11:45 ET with 172676142 open. First iteration must be IN_TRADE."""

    async def _run() -> None:
        handle = await _live_hub()
        handle.broker.positions = [dict(BTC_BOOK), dict(OPEN_US100_TICKET)]
        engine = await _us100(handle, monkeypatch, tmp_path, _at(11, 45))
        try:
            assert engine.state == "SEARCHING"
            await engine.step()
            _assert_adopted(engine, OPEN_US100_TICKET)
            _assert_no_mutations(handle)
            assert handle.broker.candle_calls == 0, "no setup may be evaluated while a position is open"
            assert engine.book_sync.pending is False
            assert engine.book_sync.adoptions == 1

            for _ in range(5):
                await engine.step()
            _assert_adopted(engine, OPEN_US100_TICKET)
            _assert_no_mutations(handle)
            assert engine.book_sync.adoptions == 1, "startup sync runs once; IN_TRADE polling takes over"

            # Broker closes the ticket (SL/TP). One confirmed empty read returns to SEARCHING.
            handle.broker.positions = [dict(BTC_BOOK)]
            await engine.step()
            assert engine.state == "SEARCHING"
            assert engine.active_position is None
            _assert_no_mutations(handle)
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_us100_restart_flat_outside_the_window_stays_searching(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async def _run() -> None:
        handle = await _live_hub()
        handle.broker.positions = [dict(BTC_BOOK)]
        engine = await _us100(handle, monkeypatch, tmp_path, _at(11, 45))
        try:
            for _ in range(4):
                await engine.step()
                assert engine.state == "SEARCHING"
                assert engine.active_position is None
            _assert_no_mutations(handle)
            assert engine.book_sync.pending is False
            assert engine.book_sync.adoptions == 0
            # Outside the window a flat engine makes exactly one read: the startup sync.
            assert handle.broker.read_calls == 1
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_us100_restart_after_sixteen_hundred_adopts_then_the_existing_hard_close_fires(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Before the fix a restarted engine was SEARCHING at 16:00 and the hard close was skipped."""

    async def _run() -> None:
        handle = await _live_hub()
        handle.broker.positions = [dict(BTC_BOOK), dict(OPEN_US100_TICKET)]
        engine = await _us100(handle, monkeypatch, tmp_path, _at(16, 5))
        try:
            await engine.step()
            closes = [order for order in handle.broker.orders if order["kind"] == "close"]
            assert [order["position_id"] for order in closes] == [OPEN_US100_TICKET["id"]]
            assert handle.broker.order_calls == 0, "hard close must not place anything"
            assert handle.broker.mutation_calls == 1
            assert engine.state == "SEARCHING"
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_us100_restart_inside_the_window_with_an_open_ticket_never_places(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Default hub prices trigger the BUY pullback on every SEARCHING step; adoption must win."""

    async def _run() -> None:
        handle = await _live_hub()
        handle.broker.positions = [dict(OPEN_US100_TICKET)]
        engine = await _us100(handle, monkeypatch, tmp_path, _at(10, 30))
        try:
            for _ in range(6):
                await engine.step()
            _assert_adopted(engine, OPEN_US100_TICKET)
            _assert_no_mutations(handle)
            assert handle.broker.candle_calls == 0

            # Sanity: the same clock and prices do place when the book is flat.
            handle.broker.positions = []
            await engine.step()
            assert engine.state == "SEARCHING"
            await engine.step()
            assert handle.broker.order_calls == 1
            assert engine.state == "IN_TRADE"
            assert engine.active_position["stopLoss"] is not None
            assert engine.active_position["takeProfit"] is not None
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_us100_restart_with_two_open_tickets_manages_the_first_and_never_adds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def _run() -> None:
        handle = await _live_hub()
        handle.broker.positions = [dict(SECOND_US100_TICKET), dict(OPEN_US100_TICKET)]
        engine = await _us100(handle, monkeypatch, tmp_path, _at(10, 30))
        try:
            for _ in range(4):
                await engine.step()
            _assert_adopted(engine, SECOND_US100_TICKET)
            _assert_no_mutations(handle)
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_us100_startup_read_failure_blocks_every_entry_until_a_read_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Unknown is not flat: with reads failing from boot, no setup is evaluated and nothing is placed."""

    async def _run() -> None:
        handle = await _live_hub()
        handle.broker.positions = [dict(OPEN_US100_TICKET)]
        engine = await _us100(handle, monkeypatch, tmp_path, _at(10, 30))
        try:
            real_get_positions_rest = engine.wrapper.get_positions_rest

            async def failing() -> list:
                raise RuntimeError("TooManyRequests: simulated")

            engine.wrapper.get_positions_rest = failing  # type: ignore[method-assign]
            for expected_failures in range(1, 5):
                await engine.step()
                assert engine.state == "SEARCHING"
                assert engine.book_sync.pending is True
                assert engine.position_sync_failures == expected_failures
            _assert_no_mutations(handle)
            assert handle.broker.candle_calls == 0

            engine.wrapper.get_positions_rest = real_get_positions_rest  # type: ignore[method-assign]
            await engine.step()
            _assert_adopted(engine, OPEN_US100_TICKET)
            assert engine.position_sync_failures == 0
            _assert_no_mutations(handle)
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_us100_hub_reconnect_resyncs_the_book_and_adopts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Hub restarts while the engine is SEARCHING; after the client reattaches the book is re-read."""

    async def _run() -> None:
        handle = await _live_hub()
        socket_path = handle.socket_path
        # Price far above the EMA so the BUY pullback does not trigger: the
        # engine polls candles and price each step without placing.
        handle.broker.prices[US100] = {"symbol": US100, "bid": 10_000.0, "ask": 10_000.2}
        engine = await _us100(handle, monkeypatch, tmp_path, _at(10, 30))
        restarted = None
        try:
            await engine.step()
            assert engine.state == "SEARCHING"
            assert engine.book_sync.pending is False
            assert engine.wrapper.client.reattaches == 0

            # Hub goes away and comes back on the same socket. The broker now
            # reports an open US100 ticket (e.g. a fill acknowledged while the
            # engine's socket was down).
            await handle.server.close()
            restarted = await _live_hub(socket_path=socket_path)
            restarted.broker.prices[US100] = {"symbol": US100, "bid": 10_000.0, "ask": 10_000.2}
            restarted.broker.positions = [dict(OPEN_US100_TICKET)]

            # This step's candle read reattaches the client. The next step sees
            # the moved reattach counter and re-syncs the book.
            await engine.step()
            assert engine.wrapper.client.reattaches >= 1
            await engine.step()
            _assert_adopted(engine, OPEN_US100_TICKET)
            _assert_no_mutations(restarted)
            assert engine.wrapper.client.local_synchronize_calls == 0
            assert restarted.broker.synchronize_calls == 1

            for _ in range(3):
                await engine.step()
            _assert_adopted(engine, OPEN_US100_TICKET)
            _assert_no_mutations(restarted)
        finally:
            await engine.wrapper.detach()
            if restarted is not None:
                await restarted.close()
            await handle.close()

    asyncio.run(_run())


# --- Gold ------------------------------------------------------------------


def test_gold_restart_outside_the_window_adopts_the_open_ticket(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        handle = await _live_hub()
        handle.broker.positions = [dict(BTC_BOOK), dict(OPEN_GOLD_TICKET)]
        engine = await _gold(handle, monkeypatch, _at(11, 45))
        try:
            assert engine.state == "SEARCHING"
            await engine.step()
            _assert_adopted(engine, OPEN_GOLD_TICKET)
            _assert_no_mutations(handle)
            assert engine.book_sync.adoptions == 1

            for _ in range(5):
                await engine.step()
            _assert_adopted(engine, OPEN_GOLD_TICKET)
            _assert_no_mutations(handle)

            handle.broker.positions = [dict(BTC_BOOK)]
            await engine.step()
            assert engine.state == "SEARCHING"
            assert engine.active_position is None
            _assert_no_mutations(handle)
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_gold_restart_flat_stays_searching(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        handle = await _live_hub()
        handle.broker.positions = [dict(BTC_BOOK), dict(OPEN_US100_TICKET)]  # other books are not Gold's
        engine = await _gold(handle, monkeypatch, _at(11, 45))
        try:
            for _ in range(4):
                await engine.step()
                assert engine.state == "SEARCHING"
                assert engine.active_position is None
            _assert_no_mutations(handle)
            assert engine.book_sync.pending is False
            assert handle.broker.read_calls == 1
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_gold_restart_after_sixteen_hundred_adopts_then_the_existing_hard_close_fires(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        handle = await _live_hub()
        handle.broker.positions = [dict(OPEN_GOLD_TICKET)]
        engine = await _gold(handle, monkeypatch, _at(16, 5))
        try:
            await engine.step()
            closes = [order for order in handle.broker.orders if order["kind"] == "close"]
            assert [order["position_id"] for order in closes] == [OPEN_GOLD_TICKET["id"]]
            assert handle.broker.order_calls == 0
            assert handle.broker.mutation_calls == 1
            assert engine.state == "SEARCHING"
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_gold_restart_inside_the_window_with_a_breakout_armed_never_places(monkeypatch: pytest.MonkeyPatch) -> None:
    """A breakout that would fire on the default hub price must not be sent while a Gold ticket is open."""

    async def _run() -> None:
        handle = await _live_hub()
        handle.broker.positions = [dict(OPEN_GOLD_TICKET)]
        engine = await _gold(handle, monkeypatch, _at(5, 0))
        # Pretend the Asian range was captured below the default ask (100.2).
        engine.asian_high = 50.0
        engine.asian_low = 10.0
        try:
            for _ in range(6):
                await engine.step()
            _assert_adopted(engine, OPEN_GOLD_TICKET)
            _assert_no_mutations(handle)
            assert handle.broker.candle_calls == 0

            # Sanity: flat, the same armed breakout does place exactly once.
            handle.broker.positions = []
            await engine.step()
            assert engine.state == "SEARCHING"
            await engine.step()
            assert handle.broker.order_calls == 1
            assert engine.state == "IN_TRADE"
            assert engine.day_triggered is True
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_gold_failed_position_read_never_flips_in_trade_to_searching(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        handle = await _live_hub()
        handle.broker.positions = [dict(OPEN_GOLD_TICKET)]
        engine = await _gold(handle, monkeypatch, _at(11, 45))
        try:
            await engine.step()
            _assert_adopted(engine, OPEN_GOLD_TICKET)

            real_get_positions_rest = engine.wrapper.get_positions_rest

            async def failing() -> list:
                raise RuntimeError("TooManyRequests: simulated")

            engine.wrapper.get_positions_rest = failing  # type: ignore[method-assign]
            for _ in range(3):
                await engine.step()
            _assert_adopted(engine, OPEN_GOLD_TICKET)
            assert engine.position_sync_failures == 3

            engine.wrapper.get_positions_rest = real_get_positions_rest  # type: ignore[method-assign]
            handle.broker.positions = []
            await engine.step()
            assert engine.state == "SEARCHING"
            assert engine.position_sync_failures == 0
            _assert_no_mutations(handle)
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())
