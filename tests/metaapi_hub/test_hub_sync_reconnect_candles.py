"""Single sync owner: concurrency, reconnect, and historical 504s."""

from __future__ import annotations

import asyncio

import pytest

from metaapi_hub.adapter import HubBackedWrapper
from metaapi_hub.broker import InMemoryBroker
from metaapi_hub.errors import HubError, NotConnectedError
from metaapi_hub.harness import start_hub
from metaapi_hub.owner import SyncOwner
from metaapi_hub.protocol import dumps, loads


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


async def _no_sleep(_seconds: float) -> None:
    return None


def test_three_clients_synchronize_once_and_share_504_retries() -> None:
    async def _run() -> None:
        handle = await start_hub(owner_kwargs={"backoff_base": 0.0, "sleep": _no_sleep})
        handle.broker.fail_candles_remaining = 2
        wrappers = []
        try:
            for name in ("btc", "us100", "gold"):
                wrapper = HubBackedWrapper(
                    "not-a-real-token",
                    "shadow-account",
                    engine_name=name,
                    socket_path=handle.socket_path,
                    shadow=True,
                )
                await wrapper.connect()
                wrappers.append(wrapper)

            async def _fetch(wrapper: HubBackedWrapper) -> list:
                return await wrapper.connection.get_historical_candles("BTCUSD", "1h")  # type: ignore[union-attr]

            batches = await asyncio.gather(*[_fetch(wrapper) for wrapper in wrappers])
            assert all(len(batch) >= 15 for batch in batches)
            assert batches[0] == batches[1] == batches[2]
            assert handle.broker.synchronize_calls == 1
            assert handle.owner.synchronize_calls == 1
            assert handle.broker.candle_calls == 3
            assert handle.owner.single_flight_joins == 2
            assert handle.owner.candle_timeouts == 2
            assert handle.broker.order_calls == 0
        finally:
            for wrapper in wrappers:
                await wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_cached_candles_do_not_hit_the_broker_again() -> None:
    async def _run() -> None:
        clock = _Clock()
        broker = InMemoryBroker()
        owner = SyncOwner(
            broker,
            mode="shadow",
            orders_mode="deny",
            cache_ttl=5.0,
            clock=clock,
            sleep=_no_sleep,
            backoff_base=0.0,
        )
        first = await owner.historical_candles("XAUUSD", "15m", 10)
        second = await owner.historical_candles("XAUUSD", "15m", 10)
        assert first == second
        assert broker.candle_calls == 1
        assert owner.cache_hits == 1
        clock.now = 10.0
        await owner.historical_candles("XAUUSD", "15m", 10)
        assert broker.candle_calls == 2

    asyncio.run(_run())


def test_reconnect_is_shared_by_concurrent_readers() -> None:
    async def _run() -> None:
        handle = await start_hub(owner_kwargs={"backoff_base": 0.0, "sleep": _no_sleep})
        wrappers = []
        try:
            for name in ("btc", "us100", "gold"):
                wrapper = HubBackedWrapper(
                    None,
                    "shadow-account",
                    engine_name=name,
                    socket_path=handle.socket_path,
                    shadow=True,
                )
                await wrapper.connect()
                wrappers.append(wrapper)
            await wrappers[0].get_account_information()
            assert handle.broker.synchronize_calls == 1
            handle.broker.fail_reads_remaining = 1
            infos = await asyncio.gather(*[item.get_account_information() for item in wrappers])
            assert all(info["server"] == "FTMO-Demo" for info in infos)
            assert handle.owner.reconnects == 1
            assert handle.broker.synchronize_calls == 2
            assert handle.broker.connected is True
        finally:
            for wrapper in wrappers:
                await wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_mutation_disconnect_is_not_retried_and_read_resyncs_once() -> None:
    async def _run() -> None:
        broker = InMemoryBroker()
        owner = SyncOwner(broker, mode="live", orders_mode="live", sleep=_no_sleep, backoff_base=0.0)
        import os

        os.environ["ODIN_METAAPI_HUB_ORDERS"] = "live"
        try:
            await owner.mutate(
                "create_market_order",
                {"symbol": "BTCUSD", "side": "BUY", "volume": 0.01, "comment": "GRIFF_BTC"},
                engine="btc",
            )
            broker.fail_mutations_remaining = 1
            with pytest.raises(NotConnectedError):
                await owner.mutate(
                    "create_market_order",
                    {"symbol": "BTCUSD", "side": "SELL", "volume": 0.01, "comment": "GRIFF_BTC_2"},
                    engine="btc",
                )
            assert broker.order_calls == 2
            assert owner.connected is False
            info = await owner.read("get_account_information")
            assert info["equity"] == 100000.0
            assert broker.synchronize_calls == 2
            assert owner.reconnects == 0
        finally:
            os.environ.pop("ODIN_METAAPI_HUB_ORDERS", None)

    asyncio.run(_run())


def test_external_slot_backs_off_instead_of_storming() -> None:
    sleeps: list[float] = []

    async def _record(seconds: float) -> None:
        sleeps.append(seconds)

    async def _run() -> None:
        broker = InMemoryBroker()
        broker.external_sync_held = True
        owner = SyncOwner(
            broker,
            mode="shadow",
            orders_mode="deny",
            max_sync_attempts=3,
            backoff_base=0.2,
            sleep=_record,
            rand=lambda: 0.0,
        )
        with pytest.raises(HubError) as caught:
            await owner.ensure_connected()
        assert caught.value.code == "SYNC_FAILED"
        assert broker.synchronize_calls == 0
        assert broker.rejected_syncs == 3
        assert sleeps == [0.2, 0.4, 0.8]
        broker.external_sync_held = False
        await owner.ensure_connected()
        assert broker.synchronize_calls == 1

    asyncio.run(_run())


def test_backoff_is_capped_and_jittered() -> None:
    owner = SyncOwner(
        InMemoryBroker(),
        mode="shadow",
        orders_mode="deny",
        backoff_base=1.0,
        backoff_max=4.0,
        backoff_jitter=0.5,
        rand=lambda: 1.0,
    )
    # 1, 2, 4, 4(capped) each plus 50% jitter at rand=1.0
    assert [owner.backoff_delay(n) for n in (1, 2, 3, 4)] == [1.5, 3.0, 6.0, 6.0]
    pinned = SyncOwner(InMemoryBroker(), mode="shadow", backoff_base=1.0, backoff_max=4.0, rand=lambda: 0.0)
    assert [pinned.backoff_delay(n) for n in (1, 2, 3, 4)] == [1.0, 2.0, 4.0, 4.0]


def test_server_rejects_client_synchronize_and_closing_a_client_keeps_the_slot() -> None:
    async def _run() -> None:
        handle = await start_hub()
        wrapper = HubBackedWrapper(
            "token",
            "shadow-account",
            engine_name="btc",
            socket_path=handle.socket_path,
            shadow=True,
        )
        try:
            await wrapper.connect()
            await wrapper.get_account_information()
            with pytest.raises(Exception) as caught:
                await wrapper.client.request("synchronize", {})
            assert getattr(caught.value, "code", "") == "FORBIDDEN_SYNC"
            assert wrapper.client.local_synchronize_calls == 1

            reader, writer = await asyncio.open_unix_connection(handle.socket_path)
            writer.write(dumps({"id": "raw-1", "method": "wait_synchronized", "params": {}}))
            await writer.drain()
            raw = loads(await reader.readline())
            writer.close()
            await writer.wait_closed()
            assert raw["ok"] is False
            assert raw["error"]["code"] == "FORBIDDEN_SYNC"
            assert handle.broker.synchronize_calls == 1

            await wrapper.streaming_connection.close()  # type: ignore[union-attr]
            assert handle.broker.connected is True
            assert handle.broker.close_calls == 1  # only the pre-sync release inside ensure_connected
            assert handle.owner.synchronize_calls == 1
        finally:
            await handle.close()

    asyncio.run(_run())
