"""GriffLiveEngine while IN_TRADE under flaky history and position reads.

Runs the real engine against the shadow hub. Asserts that incomplete or
failed history never strands the engine, never flips an open book to flat,
and never results in a close, cancel, or modify issued for recovery.
"""

from __future__ import annotations

import asyncio

import pytest

import griff_engine_live as engine_mod
from griff_engine_live import GriffLiveEngine
from metaapi_hub.broker import _sample_candles
from metaapi_hub.harness import start_hub

OPEN_BTC_POSITION = {
    "id": "172311001",
    "symbol": "BTCUSD",
    "type": "POSITION_TYPE_BUY",
    "volume": 1.12,
    "openPrice": 86404.90,
    "stopLoss": 85724.30,
    "comment": "GRIFF_1H_BREAKOUT",
}


async def _no_sleep(_seconds: float) -> None:
    return None


def _owner_kwargs() -> dict:
    return {"sleep": _no_sleep, "backoff_base": 0.0, "candle_stale_ttl": 0.0}


async def _engine(handle, monkeypatch: pytest.MonkeyPatch) -> GriffLiveEngine:
    monkeypatch.setenv("ODIN_METAAPI_HUB", "shadow")
    monkeypatch.setenv("ODIN_METAAPI_HUB_SOCKET", handle.socket_path)
    engine = GriffLiveEngine(token="unused", account_id="shadow-account", symbol="BTCUSD")
    assert await engine.connect_account() is True
    return engine


def _assert_untouched(handle, engine: GriffLiveEngine) -> None:
    assert handle.broker.mutation_calls == 0
    assert handle.broker.order_calls == 0
    assert handle.broker.orders == []
    assert engine.state == "IN_TRADE"
    assert engine.active_position is not None
    assert engine.active_position["id"] == OPEN_BTC_POSITION["id"]
    assert engine.active_position["sl"] == OPEN_BTC_POSITION["stopLoss"]
    assert engine.active_position["volume"] == OPEN_BTC_POSITION["volume"]


def test_restart_adopts_open_position_and_manages_it_with_partial_history(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fresh process (state SEARCHING) with 20 bars must reattach and manage, not stall."""

    async def _run() -> None:
        handle = await start_hub(owner_kwargs=_owner_kwargs())
        handle.broker.positions = [dict(OPEN_BTC_POSITION)]
        twenty = _sample_candles("BTCUSD", "1h", 20)

        async def partial(symbol: str, timeframe: str, limit: int | None = None) -> list:
            handle.broker.candle_calls += 1
            return list(twenty)

        handle.broker.get_historical_candles = partial  # type: ignore[method-assign]
        engine = await _engine(handle, monkeypatch)
        try:
            assert engine.state == "SEARCHING"
            result = await engine.step()
            assert result["status"] == "IN_TRADE"
            assert result["history_count"] == 20
            assert result["atr_14"] is not None and result["atr_14"] > 0
            assert engine.active_position["direction"] == "BUY"
            assert engine.active_position["entry_price"] == OPEN_BTC_POSITION["openPrice"]
            # The trailing stop was evaluated on the latest bar (no structural
            # swing in the sample data, so no modify was warranted).
            assert engine.last_evaluated_bar_time == twenty[-1]["time"]
            _assert_untouched(handle, engine)
            assert engine.wrapper.client.local_synchronize_calls == 0
            assert handle.broker.synchronize_calls == 1
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_zero_history_while_in_trade_holds_the_position_and_keeps_polling(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reported stall: candle fetch fails, 0/50 bars, position still open."""

    async def _run() -> None:
        handle = await start_hub(owner_kwargs=_owner_kwargs())
        handle.broker.positions = [dict(OPEN_BTC_POSITION)]
        monkeypatch.setattr(engine_mod, "CANDLE_FETCH_ATTEMPTS", 1)
        engine = await _engine(handle, monkeypatch)
        try:
            handle.broker.fail_candles_remaining = 10_000
            first = await engine.step()
            assert first["status"] == "IN_TRADE"
            assert first["history_count"] == 0
            assert first["atr_14"] is None
            assert engine.candle_fetch_failures == 1
            _assert_untouched(handle, engine)

            second = await engine.step()
            assert second["status"] == "IN_TRADE"
            assert engine.candle_fetch_failures == 2
            _assert_untouched(handle, engine)

            # Upstream recovers: the next poll resumes normal management.
            handle.broker.fail_candles_remaining = 0
            third = await engine.step()
            assert third["status"] == "IN_TRADE"
            assert third["history_count"] >= 15
            assert third["atr_14"] > 0
            assert engine.candle_fetch_failures == 0
            _assert_untouched(handle, engine)
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_failed_position_read_never_flips_in_trade_to_searching(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        handle = await start_hub(owner_kwargs=_owner_kwargs())
        handle.broker.positions = [dict(OPEN_BTC_POSITION)]
        engine = await _engine(handle, monkeypatch)
        try:
            await engine.synchronize_active_positions()
            assert engine.state == "IN_TRADE"

            async def failing(*_args, **_kwargs):
                raise RuntimeError("TooManyRequests: simulated")

            real_get_positions = engine.wrapper.get_positions
            real_get_positions_rest = engine.wrapper.get_positions_rest
            engine.wrapper.get_positions = failing  # type: ignore[method-assign]
            engine.wrapper.get_positions_rest = failing  # type: ignore[method-assign]

            assert await engine.fetch_positions_safe() is None
            await engine.synchronize_active_positions()
            assert engine.position_sync_failures == 1
            _assert_untouched(handle, engine)

            # A whole step with failing position reads and no history still holds.
            monkeypatch.setattr(engine_mod, "CANDLE_FETCH_ATTEMPTS", 1)
            handle.broker.fail_candles_remaining = 10_000
            result = await engine.step()
            assert result["status"] == "IN_TRADE"
            assert engine.position_sync_failures == 2
            _assert_untouched(handle, engine)

            # Reads recover and the position is really gone: one confirmed empty read flips state.
            engine.wrapper.get_positions = real_get_positions  # type: ignore[method-assign]
            engine.wrapper.get_positions_rest = real_get_positions_rest  # type: ignore[method-assign]
            await engine.synchronize_active_positions()
            assert engine.state == "IN_TRADE"
            assert engine.position_sync_failures == 0
            handle.broker.positions = []
            await engine.synchronize_active_positions()
            assert engine.state == "SEARCHING"
            assert engine.active_position is None
            assert handle.broker.mutation_calls == 0
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_candle_retry_joins_the_hub_flight_the_first_attempt_abandoned(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        handle = await start_hub(owner_kwargs=_owner_kwargs())
        gate = asyncio.Event()
        original = handle.broker.get_historical_candles

        async def slow(symbol: str, timeframe: str, limit: int | None = None) -> list:
            await gate.wait()
            return await original(symbol, timeframe, limit)

        handle.broker.get_historical_candles = slow  # type: ignore[method-assign]
        monkeypatch.setattr(engine_mod, "CANDLE_FETCH_TIMEOUT_SECONDS", 0.2)
        monkeypatch.setattr(engine_mod.random, "random", lambda: 0.0)  # retry pause = 1.0s exactly
        engine = await _engine(handle, monkeypatch)
        try:
            loop = asyncio.get_running_loop()
            loop.call_later(0.5, gate.set)
            candles = await engine.fetch_completed_1h_candles(limit=60)
            assert len(candles) >= 15
            assert engine.candle_fetch_failures == 0
            assert handle.broker.candle_calls == 1  # second attempt did not start a new fetch
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_setup_scan_still_requires_fifty_bars_when_flat(monkeypatch: pytest.MonkeyPatch) -> None:
    """The IN_TRADE relaxation must not leak into entry logic."""

    async def _run() -> None:
        handle = await start_hub(owner_kwargs=_owner_kwargs())
        forty = _sample_candles("BTCUSD", "1h", 40)

        async def partial(symbol: str, timeframe: str, limit: int | None = None) -> list:
            return list(forty)

        handle.broker.get_historical_candles = partial  # type: ignore[method-assign]
        engine = await _engine(handle, monkeypatch)
        try:
            result = await engine.step()
            assert result == {"status": "ACCUMULATING_HISTORY", "count": 40}
            assert engine.state == "SEARCHING"
            assert handle.broker.order_calls == 0
            assert handle.broker.mutation_calls == 0
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_fourteen_bars_in_trade_defers_ratchet_without_touching_the_book(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        handle = await start_hub(owner_kwargs=_owner_kwargs())
        handle.broker.positions = [dict(OPEN_BTC_POSITION)]
        fourteen = _sample_candles("BTCUSD", "1h", 14)

        async def partial(symbol: str, timeframe: str, limit: int | None = None) -> list:
            return list(fourteen)

        handle.broker.get_historical_candles = partial  # type: ignore[method-assign]
        engine = await _engine(handle, monkeypatch)
        try:
            result = await engine.step()
            assert result["status"] == "IN_TRADE"
            assert result["history_count"] == 14
            assert result["atr_14"] is None
            assert engine.last_evaluated_bar_time is None
            _assert_untouched(handle, engine)
        finally:
            await engine.wrapper.detach()
            await handle.close()

    asyncio.run(_run())
