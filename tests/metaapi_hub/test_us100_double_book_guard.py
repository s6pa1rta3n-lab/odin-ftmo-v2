"""US100 double-book guard.

Reproduces the 2026-10-02 race on matt-berserker: the broker filled BUY 9.46
(position 172673462) and the hub then answered NOT_CONNECTED for that same
mutation. The engine stayed SEARCHING without re-reading positions and placed
BUY 8.88 (172676142) on top of the live book five minutes later.

These tests drive the real ``US100Engine`` against the in-process hub with
live orders enabled, script the broker to "fill, then lose the ack", and
assert that exactly one position is ever opened. Pure helper behaviour is
covered separately without a hub.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

import pytest
import pytz

import griff_engine_us100 as engine_mod
from griff_engine_us100 import US100Engine
from metaapi_hub.errors import (
    DryRunOrderError,
    HubError,
    HubRequestError,
    NotConnectedError,
    OrdersDisabledError,
)
from metaapi_hub.harness import start_hub
from modules.entry_guard import (
    describe_place_error,
    is_ambiguous_place_error,
    matching_positions,
    should_skip_entry,
)

US100 = "US100.cash"

# The two real tickets from the incident, as the hub reports positions.
FILLED_9_46 = {
    "id": "172673462",
    "symbol": US100,
    "type": "POSITION_TYPE_BUY",
    "volume": 9.46,
    "openPrice": 30826.23,
    "stopLoss": 30734.58,
    "takeProfit": 31030.22,
    "comment": "GRIFF_US100_NY",
}
FILLED_8_88 = {
    "id": "172676142",
    "symbol": US100,
    "type": "POSITION_TYPE_BUY",
    "volume": 8.88,
    "openPrice": 30807.38,
    "comment": "GRIFF_US100_NY",
}
OTHER_BOOK = {
    "id": "900000001",
    "symbol": "BTCUSD",
    "type": "POSITION_TYPE_BUY",
    "volume": 1.0,
    "comment": "GRIFF_1H_BREAKOUT",
}


# ---------------------------------------------------------------------------
# Pure helper
# ---------------------------------------------------------------------------


def test_matching_positions_by_symbol_or_comment_prefix() -> None:
    aliased = {"id": "5", "symbol": "USTEC", "comment": "GRIFF_US100_NY"}
    rewritten_comment = {"id": "6", "symbol": US100, "brokerComment": "[sl 30734.58]"}
    positions = [OTHER_BOOK, FILLED_9_46, aliased, rewritten_comment, "garbage", None]

    matched = matching_positions(positions, symbol=US100, comment_prefix="GRIFF_US100")
    assert [p["id"] for p in matched] == ["172673462", "5", "6"]
    assert matching_positions(None, symbol=US100, comment_prefix="GRIFF_US100") == []
    assert matching_positions([], symbol=US100, comment_prefix="GRIFF_US100") == []
    assert matching_positions([OTHER_BOOK], symbol=US100, comment_prefix="GRIFF_US100") == []


def test_ambiguous_place_errors_cover_lost_acks_and_only_exclude_hub_refusals() -> None:
    ambiguous = [
        NotConnectedError("not connected to broker"),
        HubRequestError("NOT_CONNECTED", "hub unreachable after 3 reattach attempts"),
        HubRequestError("CLOSED", "hub connection closed while sending create_market_order"),
        HubError("TIMEOUT", "MetaAPI call timed out after 20s", retryable=True),
        HubError("BROKER_ERROR", "TradeException: TRADE_RETCODE_REQUOTE"),
        asyncio.TimeoutError(),
        ConnectionResetError("peer reset"),
        OSError("socket gone"),
        RuntimeError("unexpected"),
    ]
    for exc in ambiguous:
        assert is_ambiguous_place_error(exc) is True, exc

    never_sent = [
        OrdersDisabledError(),
        DryRunOrderError("dry run", {"sent": False}),
        HubError("COMMENT_REQUIRED", "entry orders must include a comment"),
        HubError("BAD_REQUEST", "volume must be at least 0.01"),
        HubRequestError("FORBIDDEN_SYNC", "this client is not allowed to synchronize"),
    ]
    for exc in never_sent:
        assert is_ambiguous_place_error(exc) is False, exc
    assert is_ambiguous_place_error(None) is False

    assert describe_place_error(NotConnectedError("x")).startswith("NOT_CONNECTED")
    assert describe_place_error(RuntimeError("boom")) == "boom"


def test_should_skip_entry_decision_table() -> None:
    kwargs = {"symbol": US100, "comment_prefix": "GRIFF_US100"}

    # Position read failed: flatness unknown, never enter.
    assert should_skip_entry(None, None, **kwargs) is True
    # The "failed" order actually filled.
    assert should_skip_entry([FILLED_9_46], None, **kwargs) is True
    # Another process holds the US100 book.
    assert should_skip_entry([{"id": "1", "symbol": US100, "comment": ""}], None, **kwargs) is True
    # Unreconciled ambiguous error with an empty read still blocks.
    assert should_skip_entry([], NotConnectedError(), **kwargs) is True
    assert should_skip_entry([], HubError("TIMEOUT", "t", retryable=True), **kwargs) is True
    # Confirmed flat and no unreconciled error: entry allowed.
    assert should_skip_entry([], None, **kwargs) is False
    assert should_skip_entry([OTHER_BOOK], None, **kwargs) is False
    # A hub refusal never reached the broker, so a flat read is enough.
    assert should_skip_entry([], OrdersDisabledError(), **kwargs) is False


# ---------------------------------------------------------------------------
# Engine against the in-process hub
# ---------------------------------------------------------------------------


async def _no_sleep(_seconds: float) -> None:
    return None


def _owner_kwargs() -> dict:
    return {"sleep": _no_sleep, "backoff_base": 0.0, "candle_stale_ttl": 0.0}


def _ny_window_time() -> datetime:
    eastern = pytz.timezone("US/Eastern")
    return eastern.localize(datetime(2026, 10, 2, 10, 30, 0))


async def _live_hub():
    return await start_hub(mode="live", orders_mode="live", account_id="live-account", owner_kwargs=_owner_kwargs())


async def _engine(handle, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> US100Engine:
    monkeypatch.setenv("ODIN_METAAPI_HUB", "on")
    monkeypatch.setenv("ODIN_METAAPI_HUB_ORDERS", "live")
    monkeypatch.setenv("ODIN_METAAPI_HUB_SOCKET", handle.socket_path)
    config_path = tmp_path / "config_us100.json"
    config_path.write_text(json.dumps({"symbol": US100, "risk_pct": 0.01}), encoding="utf-8")
    engine = US100Engine(token="unused", account_id="live-account", config_path=str(config_path))
    engine.post_place_error_sync_delay = 0.0
    monkeypatch.setattr(engine, "get_est_time", _ny_window_time)
    # Sample 15m candles close 101..140 with EMA(20) well above the default
    # ask of 100.2, so the BUY pullback trigger fires on every SEARCHING step.
    assert await engine.connect() is True
    return engine


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


def test_fill_then_not_connected_adopts_the_fill_instead_of_placing_again(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The exact 2026-10-02 sequence. Only one order may ever reach the broker."""

    async def _run() -> None:
        handle = await _live_hub()
        calls = _fill_then_lose_ack(handle, FILLED_9_46)
        engine = await _engine(handle, monkeypatch, tmp_path)
        try:
            assert engine.state == "SEARCHING"

            # 15:09:48 place -> 15:09:58 broker fill -> 15:10:03 NOT_CONNECTED.
            await engine.step()
            assert calls["count"] == 1
            assert handle.broker.order_calls == 1
            assert engine.state == "IN_TRADE", "post-error sync must adopt the fill"
            assert engine.active_position["id"] == FILLED_9_46["id"]
            assert engine.entry_sync_required is False
            assert engine.last_place_error is None

            # 15:14:14 the next trigger. Before the fix this placed BUY 8.88.
            for _ in range(5):
                await engine.step()
            assert handle.broker.order_calls == 1, "second entry was placed on top of the live book"
            assert len(handle.broker.positions) == 1
            assert engine.state == "IN_TRADE"

            # The book closes (SL hit). One confirmed empty read returns to SEARCHING.
            handle.broker.positions = []
            await engine.step()
            assert engine.state == "SEARCHING"
            assert engine.active_position is None

            # Normal entry still works once flat is confirmed.
            await engine.step()
            assert handle.broker.order_calls == 2
            assert engine.state == "IN_TRADE"
            assert engine.active_position["id"] == "pos-2"
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_not_connected_without_a_fill_stays_searching_and_may_enter_later(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A genuine failure (nothing filled) must not wedge the engine."""

    async def _run() -> None:
        handle = await _live_hub()
        engine = await _engine(handle, monkeypatch, tmp_path)
        try:
            handle.broker.fail_mutations_remaining = 1
            await engine.step()
            assert handle.broker.order_calls == 1
            assert handle.broker.positions == []
            assert engine.state == "SEARCHING"
            # The reconciling read succeeded and found nothing, so entries are open again.
            assert engine.entry_sync_required is False
            assert engine.last_place_error is None

            await engine.step()
            assert handle.broker.order_calls == 2
            assert engine.state == "IN_TRADE"
            assert len(handle.broker.positions) == 0  # InMemoryBroker does not materialise positions on fill
            assert engine.active_position["id"] == "pos-2"
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_entry_is_blocked_until_a_position_read_succeeds_after_an_ambiguous_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """NOT_CONNECTED on place, then position reads also fail: no entry until reads recover."""

    async def _run() -> None:
        handle = await _live_hub()
        calls = _fill_then_lose_ack(handle, FILLED_9_46)
        engine = await _engine(handle, monkeypatch, tmp_path)
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

            # Triggers keep firing, reads keep failing: nothing may be placed.
            for _ in range(4):
                await engine.step()
            assert handle.broker.order_calls == 1
            assert engine.entry_sync_required is True
            assert engine.position_sync_failures == 5

            # Reads recover: the fill is found and adopted. Still no second order.
            engine.wrapper.get_positions_rest = real_get_positions_rest  # type: ignore[method-assign]
            await engine.step()
            assert engine.state == "IN_TRADE"
            assert engine.active_position["id"] == FILLED_9_46["id"]
            assert engine.entry_sync_required is False
            assert engine.position_sync_failures == 0
            await engine.step()
            assert handle.broker.order_calls == 1
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_pre_entry_check_adopts_an_existing_us100_position_on_restart(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Fresh process (SEARCHING) with 172676142 already open must not add to it."""

    async def _run() -> None:
        handle = await _live_hub()
        handle.broker.positions = [dict(OTHER_BOOK), dict(FILLED_8_88)]
        engine = await _engine(handle, monkeypatch, tmp_path)
        try:
            await engine.step()
            assert handle.broker.order_calls == 0
            assert handle.broker.mutation_calls == 0
            assert engine.state == "IN_TRADE"
            assert engine.active_position["id"] == FILLED_8_88["id"]

            await engine.step()
            assert handle.broker.order_calls == 0
            assert engine.state == "IN_TRADE"
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_pre_entry_read_failure_skips_the_entry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async def _run() -> None:
        handle = await _live_hub()
        engine = await _engine(handle, monkeypatch, tmp_path)
        try:
            real_get_positions_rest = engine.wrapper.get_positions_rest

            async def failing() -> list:
                raise RuntimeError("TooManyRequests: simulated")

            engine.wrapper.get_positions_rest = failing  # type: ignore[method-assign]
            await engine.step()
            assert handle.broker.order_calls == 0
            assert engine.state == "SEARCHING"
            assert engine.position_sync_failures == 1

            engine.wrapper.get_positions_rest = real_get_positions_rest  # type: ignore[method-assign]
            await engine.step()
            assert handle.broker.order_calls == 1
            assert engine.state == "IN_TRADE"
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_guard_never_closes_or_modifies_positions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Across fill-then-error, adoption, and recovery, the only mutations are entries."""

    async def _run() -> None:
        handle = await _live_hub()
        calls = _fill_then_lose_ack(handle, FILLED_9_46)
        engine = await _engine(handle, monkeypatch, tmp_path)
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


def test_hub_refusal_does_not_add_the_post_error_delay(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """ORDERS_DISABLED never reached the broker; the engine still re-reads positions but does not wait."""

    async def _run() -> None:
        handle = await start_hub(mode="live", orders_mode="deny", account_id="live-account", owner_kwargs=_owner_kwargs())
        engine = await _engine(handle, monkeypatch, tmp_path)
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
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())
