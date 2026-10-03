"""Flaky-upstream resilience: big frames, head-of-line blocking, reattach, retries, stale candles.

Every test runs against ``InMemoryBroker``. Nothing here imports the SDK,
reads a token, or sends an order.
"""

from __future__ import annotations

import asyncio

import pytest

from metaapi_hub.adapter import HubBackedWrapper
from metaapi_hub.broker import InMemoryBroker, _sample_candles
from metaapi_hub.errors import GatewayTimeoutError, HubError, HubRequestError, TooManyRequestsError
from metaapi_hub.harness import start_hub
from metaapi_hub.owner import SyncOwner
from metaapi_hub.protocol import MAX_MESSAGE_BYTES, dumps


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


async def _no_sleep(_seconds: float) -> None:
    return None


def _big_candles(count: int = 1000) -> list[dict]:
    """Approximate a real MetaAPI history page: ~1000 bars with broker fields."""

    bars = _sample_candles("BTCUSD", "1h", count)
    for bar in bars:
        bar.update({"brokerTime": "2026-10-02 00:00:00.000", "tickVolume": 1234, "spread": 12, "volume": 0})
    return bars


def _wrapper(handle, name: str = "btc") -> HubBackedWrapper:
    return HubBackedWrapper(None, "shadow-account", engine_name=name, socket_path=handle.socket_path, shadow=True)


def test_candle_frames_larger_than_64kib_do_not_kill_the_client() -> None:
    """The asyncio default readline limit is 64 KiB. A history page is bigger."""

    async def _run() -> None:
        handle = await start_hub()
        big = _big_candles()
        assert len(dumps({"id": "x", "ok": True, "result": big})) > 65536

        async def fake(symbol: str, timeframe: str, limit: int | None = None) -> list:
            return list(big)

        handle.broker.get_historical_candles = fake  # type: ignore[method-assign]
        wrapper = _wrapper(handle)
        await wrapper.connect()
        try:
            candles = await asyncio.wait_for(wrapper.connection.get_historical_candles("BTCUSD", "1h"), timeout=5)  # type: ignore[union-attr]
            assert len(candles) == 1000
            info = await asyncio.wait_for(wrapper.get_account_information(), timeout=5)
            assert info["server"] == "FTMO-Demo"
            assert wrapper.client.attached is True
            assert wrapper.client.connection_losses == 0
            assert handle.broker.synchronize_calls == 1
        finally:
            await wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_slow_candle_fetch_does_not_block_other_requests_on_the_same_connection() -> None:
    """An engine that gave up on candles must still get account info from the hub."""

    async def _run() -> None:
        handle = await start_hub(owner_kwargs={"sleep": _no_sleep, "backoff_base": 0.0})
        release = asyncio.Event()
        original = handle.broker.get_historical_candles

        async def slow(symbol: str, timeframe: str, limit: int | None = None) -> list:
            await release.wait()
            return await original(symbol, timeframe, limit)

        handle.broker.get_historical_candles = slow  # type: ignore[method-assign]
        wrapper = _wrapper(handle)
        await wrapper.connect()
        try:
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(wrapper.connection.get_historical_candles("BTCUSD", "1h"), timeout=0.2)  # type: ignore[union-attr]
            # Before: this waited behind the stale candle request and timed out too.
            info = await asyncio.wait_for(wrapper.get_account_information(), timeout=2.0)
            assert info["equity"] == 100000.0
            positions = await asyncio.wait_for(wrapper.get_positions(), timeout=2.0)
            assert positions == []
            release.set()
            candles = await asyncio.wait_for(wrapper.connection.get_historical_candles("BTCUSD", "1h"), timeout=2.0)  # type: ignore[union-attr]
            assert len(candles) >= 15
            assert handle.server.max_inflight_per_connection >= 2
            assert handle.broker.synchronize_calls == 1
        finally:
            await wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_client_reattaches_after_the_hub_restarts_and_never_syncs() -> None:
    async def _run() -> None:
        handle = await start_hub()
        socket_path = handle.socket_path
        wrapper = _wrapper(handle)
        await wrapper.connect()
        assert (await wrapper.get_account_information())["server"] == "FTMO-Demo"

        # Hub goes away (restart). The engine keeps its wrapper object.
        await handle.server.close()
        with pytest.raises(HubRequestError) as caught:
            await wrapper.get_account_information()
        assert caught.value.code in {"NOT_CONNECTED", "CLOSED"}
        assert wrapper.client.attached is False

        # Hub comes back on the same socket path.
        restarted = await start_hub(socket_path=socket_path)
        try:
            info = await wrapper.get_account_information()
            assert info["server"] == "FTMO-Demo"
            assert wrapper.client.reattaches >= 1
            assert wrapper.client.local_synchronize_calls == 0
            assert restarted.owner.snapshot()["clients"] == ["btc"]
            assert restarted.broker.synchronize_calls == 1
        finally:
            await wrapper.detach()
            await restarted.close()
        # detach() is the engine's own close: no further reattach happens.
        with pytest.raises(HubRequestError) as closed:
            await wrapper.client.request("positions", {})
        assert closed.value.code == "NOT_CONNECTED"

    asyncio.run(_run())


def test_reads_retry_retryable_errors_with_backoff_and_mutations_do_not() -> None:
    sleeps: list[float] = []

    async def _record(seconds: float) -> None:
        sleeps.append(seconds)

    async def _run() -> None:
        import os

        broker = InMemoryBroker()
        owner = SyncOwner(
            broker,
            mode="live",
            orders_mode="live",
            read_attempts=3,
            backoff_base=0.1,
            backoff_jitter=0.0,
            sleep=_record,
            rand=lambda: 0.0,
        )
        failures = {"left": 2}
        original = broker.get_account_information

        async def flaky() -> dict:
            if failures["left"] > 0:
                failures["left"] -= 1
                raise HubError("TIMEOUT", "MetaAPI call timed out", retryable=True)
            return await original()

        broker.get_account_information = flaky  # type: ignore[method-assign]
        info = await owner.read("get_account_information")
        assert info["server"] == "FTMO-Demo"
        assert owner.read_retries == 2
        assert sleeps == [0.1, 0.2]
        assert owner.snapshot()["last_upstream_error"].startswith("get_account_information: TIMEOUT")
        assert broker.synchronize_calls == 1  # a timeout never opens a second sync

        # Exhausting the attempts raises the upstream error, not a stall.
        failures["left"] = 10
        with pytest.raises(HubError) as caught:
            await owner.read("get_account_information")
        assert caught.value.code == "TIMEOUT"
        assert owner.read_retries == 4
        failures["left"] = 0

        # TooManyRequests on a read is retried the same way.
        tmr = {"left": 1}
        original_positions = broker.get_positions

        async def rate_limited() -> list:
            if tmr["left"] > 0:
                tmr["left"] -= 1
                raise TooManyRequestsError("TooManyRequests: rpc")
            return await original_positions()

        broker.get_positions = rate_limited  # type: ignore[method-assign]
        assert await owner.read("get_positions") == []
        assert owner.read_retries == 5

        # Mutations: one attempt, no retry, no backoff sleep.
        os.environ["ODIN_METAAPI_HUB_ORDERS"] = "live"
        try:
            sleeps.clear()
            orig_market = broker.create_market_order

            async def timed_out_order(payload: dict) -> dict:
                raise HubError("TIMEOUT", "MetaAPI call timed out", retryable=True)

            broker.create_market_order = timed_out_order  # type: ignore[method-assign]
            with pytest.raises(HubError) as order_err:
                await owner.mutate(
                    "create_market_order",
                    {"symbol": "BTCUSD", "side": "BUY", "volume": 0.01, "comment": "GRIFF_BTC"},
                    engine="btc",
                )
            assert order_err.value.code == "TIMEOUT"
            assert sleeps == []
            broker.create_market_order = orig_market  # type: ignore[method-assign]
            assert broker.order_calls == 0
        finally:
            os.environ.pop("ODIN_METAAPI_HUB_ORDERS", None)

    asyncio.run(_run())


def test_candles_retry_timeouts_then_serve_last_good_within_stale_ttl() -> None:
    async def _run() -> None:
        clock = _Clock()
        broker = InMemoryBroker()
        owner = SyncOwner(
            broker,
            mode="shadow",
            cache_ttl=5.0,
            candle_attempts=3,
            candle_stale_ttl=300.0,
            backoff_base=0.0,
            sleep=_no_sleep,
            clock=clock,
        )
        good = await owner.historical_candles("BTCUSD", "1h", 60)
        assert len(good) >= 15
        assert broker.candle_calls == 1

        # Fresh fetch fails on every attempt with a non-504 timeout.
        original = broker.get_historical_candles

        async def timing_out(symbol: str, timeframe: str, limit: int | None = None) -> list:
            broker.candle_calls += 1
            raise HubError("TIMEOUT", "MetaAPI call timed out", retryable=True)

        broker.get_historical_candles = timing_out  # type: ignore[method-assign]
        clock.now = 60.0  # cache expired, last-good still fresh enough
        served = await owner.historical_candles("BTCUSD", "1h", 60)
        assert served == good
        assert broker.candle_calls == 4  # 1 good + 3 failed attempts
        assert owner.candle_retries == 2
        assert owner.candle_stale_serves == 1
        assert broker.synchronize_calls == 1

        # 504s count as candle_timeouts and are retried the same way.
        async def gateway(symbol: str, timeframe: str, limit: int | None = None) -> list:
            broker.candle_calls += 1
            raise GatewayTimeoutError()

        broker.get_historical_candles = gateway  # type: ignore[method-assign]
        clock.now = 120.0
        assert await owner.historical_candles("BTCUSD", "1h", 60) == good
        assert owner.candle_timeouts == 3
        assert owner.candle_stale_serves == 2

        # Past the stale TTL the failure is surfaced instead of stale data.
        clock.now = 60.0 + 301.0
        with pytest.raises(HubError) as caught:
            await owner.historical_candles("BTCUSD", "1h", 60)
        assert caught.value.code == "GATEWAY_TIMEOUT"

        # A different key has no last-good set and fails immediately after the attempts.
        with pytest.raises(HubError):
            await owner.historical_candles("XAUUSD", "15m", 30)

        broker.get_historical_candles = original  # type: ignore[method-assign]
        clock.now = 1000.0
        fresh = await owner.historical_candles("BTCUSD", "1h", 60)
        assert len(fresh) >= 15

    asyncio.run(_run())


def test_stale_ttl_zero_disables_the_fallback() -> None:
    async def _run() -> None:
        clock = _Clock()
        broker = InMemoryBroker()
        owner = SyncOwner(
            broker, mode="shadow", candle_attempts=2, candle_stale_ttl=0.0, backoff_base=0.0, sleep=_no_sleep, clock=clock
        )
        await owner.historical_candles("BTCUSD", "1h", 60)
        broker.fail_candles_remaining = 2
        clock.now = 10.0
        with pytest.raises(GatewayTimeoutError):
            await owner.historical_candles("BTCUSD", "1h", 60)
        assert owner.candle_stale_serves == 0

    asyncio.run(_run())


def test_one_engine_cancelling_does_not_cancel_the_shared_candle_flight() -> None:
    async def _run() -> None:
        broker = InMemoryBroker()
        owner = SyncOwner(broker, mode="shadow", backoff_base=0.0, sleep=_no_sleep)
        gate = asyncio.Event()
        original = broker.get_historical_candles

        async def gated(symbol: str, timeframe: str, limit: int | None = None) -> list:
            await gate.wait()
            return await original(symbol, timeframe, limit)

        broker.get_historical_candles = gated  # type: ignore[method-assign]
        first = asyncio.ensure_future(owner.historical_candles("BTCUSD", "1h", 60))
        await asyncio.sleep(0)
        second = asyncio.ensure_future(owner.historical_candles("BTCUSD", "1h", 60))
        await asyncio.sleep(0)
        assert owner.single_flight_joins == 1
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        gate.set()
        result = await asyncio.wait_for(second, timeout=2.0)
        assert len(result) >= 15
        assert broker.candle_calls == 1

    asyncio.run(_run())


def test_server_health_reports_transport_limits() -> None:
    async def _run() -> None:
        handle = await start_hub()
        wrapper = _wrapper(handle)
        await wrapper.connect()
        try:
            health = await wrapper.client.request("health", {})
            assert health["max_message_bytes"] == MAX_MESSAGE_BYTES
            assert health["server_oversized_frames"] == 0
            assert health["read_concurrency"] == 4
            assert health["candle_stale_serves"] == 0
            assert health["read_retries"] == 0
            assert health["you_do_not_sync"] is True
        finally:
            await wrapper.detach()
            await handle.close()

    asyncio.run(_run())
