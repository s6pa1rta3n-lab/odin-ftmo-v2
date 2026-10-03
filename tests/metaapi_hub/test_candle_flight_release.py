"""The candle single-flight slot is released even when the SDK task never finishes.

Live evidence (hub PID 2849217, Python 3.9): ``_load_candles`` logged attempts
1/4 and 2/4 at the 20 s SDK timeout, then attempt 3 never logged and
``candle_retries`` froze at 2. ``asyncio.wait_for`` only returns once the
cancelled inner task finishes, so a stuck SDK call wedged the one shared
flight, and every later BTC candle request joined it.

The SDK double below reproduces that: it swallows cancellation until the test
releases it. Every test runs against ``InMemoryBroker``; nothing imports the
SDK or places an order.
"""

from __future__ import annotations

import asyncio

import pytest

from metaapi_hub.adapter import HubBackedWrapper
from metaapi_hub.broker import InMemoryBroker
from metaapi_hub.errors import HubError
from metaapi_hub.harness import start_hub
from metaapi_hub.owner import SyncOwner


async def _no_sleep(_seconds: float) -> None:
    return None


class _StuckSdk:
    """Candle call that does not finish when cancelled, like the live SDK task.

    ``healthy`` flips it back to a normal call. ``release()`` lets the
    orphaned tasks finish so the event loop can shut down cleanly.
    """

    def __init__(self, broker: InMemoryBroker) -> None:
        self.broker = broker
        self.original = broker.get_historical_candles
        self.release_event = asyncio.Event()
        self.healthy = False
        self.calls = 0
        self.swallowed_cancels = 0
        self.stuck_started = asyncio.Event()

    async def __call__(self, symbol: str, timeframe: str, limit: int | None = None) -> list:
        self.calls += 1
        if self.healthy:
            return await self.original(symbol, timeframe, limit)
        self.stuck_started.set()
        while not self.release_event.is_set():
            try:
                await self.release_event.wait()
            except asyncio.CancelledError:
                self.swallowed_cancels += 1
        return await self.original(symbol, timeframe, limit)

    def release(self) -> None:
        self.release_event.set()


async def _settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


def test_cancelled_caller_releases_the_slot_even_if_the_sdk_task_never_finishes() -> None:
    """(1) + (2): the engine's wait_for expires, the slot is free, the next request starts a new call."""

    async def _run() -> None:
        broker = InMemoryBroker()
        sdk = _StuckSdk(broker)
        broker.get_historical_candles = sdk  # type: ignore[method-assign]
        owner = SyncOwner(broker, mode="shadow", backoff_base=0.0, sleep=_no_sleep, candle_call_timeout=60.0)

        # Caller 1 is the engine: CANDLE_FETCH_TIMEOUT_SECONDS expires and its await is cancelled.
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(owner.historical_candles("BTCUSD", "1h", 60), timeout=0.2)
        assert sdk.calls == 1
        await _settle()

        # The SDK task is still running (it swallowed the cancel), yet the slot is free.
        assert sdk.swallowed_cancels == 1
        assert owner._inflight == {}
        assert owner.candle_flights_released == 1
        assert owner.abandoned_calls == 1
        assert owner.snapshot()["abandoned_calls_pending"] == 1

        # Caller 2 must start a new call, not join the stuck one.
        sdk.healthy = True
        candles = await asyncio.wait_for(owner.historical_candles("BTCUSD", "1h", 60), timeout=2.0)
        assert len(candles) >= 15
        assert sdk.calls == 2
        assert owner.single_flight_joins == 0
        assert owner.candle_fetches == 1
        assert broker.synchronize_calls == 1

        # The orphan finishing later is observed and dropped; nothing else changes.
        sdk.release()
        await _settle()
        assert owner.snapshot()["abandoned_calls_pending"] == 0
        assert owner.candle_fetches == 1
        assert broker.order_calls == 0 and broker.mutation_calls == 0

    asyncio.run(_run())


def test_candle_call_timeout_frees_the_flight_and_the_read_gate_without_waiting_for_the_sdk() -> None:
    """(1) + (2) on the hub side: a waiter that never cancels (a server handler) still gets an answer in bounded time."""

    async def _run() -> None:
        broker = InMemoryBroker()
        sdk = _StuckSdk(broker)
        broker.get_historical_candles = sdk  # type: ignore[method-assign]
        owner = SyncOwner(
            broker,
            mode="shadow",
            backoff_base=0.0,
            sleep=_no_sleep,
            candle_attempts=2,
            candle_stale_ttl=0.0,
            candle_call_timeout=0.1,
            read_concurrency=1,
        )

        # Before this change the flight never finished: wait_for sat in _cancel_and_wait.
        with pytest.raises(HubError) as caught:
            await asyncio.wait_for(owner.historical_candles("BTCUSD", "1h", 60), timeout=2.0)
        assert caught.value.code == "TIMEOUT"
        assert caught.value.retryable is True
        assert "abandoned" in caught.value.message
        assert sdk.calls == 2  # both attempts ran and were abandoned at the budget
        assert owner.abandoned_calls == 2
        assert owner.candle_retries == 1
        assert owner.snapshot()["abandoned_calls_pending"] == 2
        assert owner._inflight == {}

        # read_concurrency=1: if an abandoned call still held the read gate this would hang.
        info = await asyncio.wait_for(owner.read("get_account_information"), timeout=1.0)
        assert info["server"] == "FTMO-Demo"

        # The next candle request starts a new call and succeeds once the SDK answers.
        sdk.healthy = True
        candles = await asyncio.wait_for(owner.historical_candles("BTCUSD", "1h", 60), timeout=2.0)
        assert len(candles) >= 15
        assert sdk.calls == 3
        assert owner.single_flight_joins == 0
        assert broker.synchronize_calls == 1

        sdk.release()
        await _settle()
        assert owner.snapshot()["abandoned_calls_pending"] == 0

    asyncio.run(_run())


def test_stale_fallback_still_applies_after_abandoned_calls() -> None:
    """A stuck SDK after a good fetch serves the last good set instead of an error."""

    async def _run() -> None:
        broker = InMemoryBroker()
        owner = SyncOwner(
            broker,
            mode="shadow",
            backoff_base=0.0,
            sleep=_no_sleep,
            cache_ttl=0.0,
            candle_attempts=2,
            candle_stale_ttl=300.0,
            candle_call_timeout=0.1,
        )
        good = await owner.historical_candles("BTCUSD", "1h", 60)
        sdk = _StuckSdk(broker)
        broker.get_historical_candles = sdk  # type: ignore[method-assign]
        served = await asyncio.wait_for(owner.historical_candles("BTCUSD", "1h", 60), timeout=2.0)
        assert served == good
        assert owner.candle_stale_serves == 1
        assert owner.abandoned_calls == 2
        sdk.release()
        await _settle()

    asyncio.run(_run())


def test_a_remaining_waiter_keeps_the_shared_flight_and_nothing_is_abandoned() -> None:
    """One engine giving up must not cancel the fetch another engine is still waiting on."""

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
        assert owner.candle_flights_released == 0
        assert len(owner._inflight) == 1
        gate.set()
        result = await asyncio.wait_for(second, timeout=2.0)
        assert len(result) >= 15
        assert broker.candle_calls == 1
        assert owner.abandoned_calls == 0
        assert owner._inflight == {}

    asyncio.run(_run())


def test_normal_completion_still_shares_one_flight() -> None:
    """(3): concurrent callers share one broker call exactly as before."""

    async def _run() -> None:
        broker = InMemoryBroker()
        owner = SyncOwner(broker, mode="shadow", backoff_base=0.0, sleep=_no_sleep)
        gate = asyncio.Event()
        original = broker.get_historical_candles

        async def gated(symbol: str, timeframe: str, limit: int | None = None) -> list:
            await gate.wait()
            return await original(symbol, timeframe, limit)

        broker.get_historical_candles = gated  # type: ignore[method-assign]
        waiters = [asyncio.ensure_future(owner.historical_candles("BTCUSD", "1h", 60)) for _ in range(3)]
        await _settle()
        assert owner.single_flight_joins == 2
        assert owner._inflight[("BTCUSD", "1h", 60)].waiters == 3
        gate.set()
        results = await asyncio.wait_for(asyncio.gather(*waiters), timeout=2.0)
        assert results[0] == results[1] == results[2]
        assert len(results[0]) >= 15
        assert broker.candle_calls == 1
        assert owner.candle_fetches == 1
        assert owner.candle_flights_released == 0
        assert owner.abandoned_calls == 0
        assert owner._inflight == {}

        # Within the cache TTL nobody even starts a flight.
        again = await owner.historical_candles("BTCUSD", "1h", 60)
        assert again == results[0]
        assert owner.cache_hits == 1
        assert broker.candle_calls == 1

        # Budget 0 opts out of the bounded call; normal fetches are unchanged.
        plain = SyncOwner(InMemoryBroker(), mode="shadow", candle_call_timeout=0.0)
        assert len(await plain.historical_candles("BTCUSD", "1h", 60)) >= 15
        assert plain.abandoned_calls == 0

    asyncio.run(_run())


def test_engine_timeout_over_the_socket_does_not_wedge_later_candle_requests() -> None:
    """The live path: engine wait_for expires client-side, the server handler is not cancelled.

    The hub budget ends the stuck flight; the engine's next poll gets fresh
    candles from a new call, and account reads keep working throughout.
    """

    async def _run() -> None:
        handle = await start_hub(
            owner_kwargs={
                "sleep": _no_sleep,
                "backoff_base": 0.0,
                "candle_attempts": 2,
                "candle_stale_ttl": 0.0,
                "candle_call_timeout": 0.3,
                "read_concurrency": 1,
            }
        )
        sdk = _StuckSdk(handle.broker)
        handle.broker.get_historical_candles = sdk  # type: ignore[method-assign]
        wrapper = HubBackedWrapper(None, "shadow-account", engine_name="btc", socket_path=handle.socket_path, shadow=True)
        await wrapper.connect()
        try:
            # Engine attempt: CANDLE_FETCH_TIMEOUT_SECONDS scaled down.
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(wrapper.connection.get_historical_candles("BTCUSD", "1h"), timeout=0.1)  # type: ignore[union-attr]
            await sdk.stuck_started.wait()
            # The server-side handler is still awaiting the flight (by design it is not cancelled).
            assert len(handle.owner._inflight) == 1
            assert handle.owner._inflight[("BTCUSD", "1h", None)].waiters == 1

            # Other reads are not stuck behind it even with a single read slot.
            info = await asyncio.wait_for(wrapper.get_account_information(), timeout=1.0)
            assert info["equity"] == 100000.0

            # The hub budget (0.3 s x 2 attempts) ends the flight without the SDK task finishing.
            await asyncio.sleep(0.8)
            assert handle.owner._inflight == {}
            assert handle.owner.abandoned_calls == 2
            assert sdk.swallowed_cancels == 2

            # Next engine poll: a new call, fresh candles.
            sdk.healthy = True
            candles = await asyncio.wait_for(wrapper.connection.get_historical_candles("BTCUSD", "1h"), timeout=2.0)  # type: ignore[union-attr]
            assert len(candles) >= 15
            assert sdk.calls == 3
            health = await wrapper.client.request("health", {})
            assert health["abandoned_calls"] == 2
            assert health["candle_call_timeout"] == 0.3
            assert health["single_flight_joins"] == 0
            assert health["synchronize_calls"] == 1
            assert handle.broker.order_calls == 0
        finally:
            sdk.release()
            await _settle()
            await wrapper.detach()
            await handle.close()

    asyncio.run(_run())
