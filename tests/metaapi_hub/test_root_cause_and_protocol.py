"""Root-cause model and error classification.

The production failure is three processes each calling wait_synchronized() on
one MetaAPI account. InMemoryBroker reproduces the one-slot limit without
contacting MetaAPI.
"""

from __future__ import annotations

import asyncio

import pytest

from metaapi_hub.broker import InMemoryBroker, MetaApiBroker
from metaapi_hub.errors import (
    GatewayTimeoutError,
    HubError,
    NotConnectedError,
    OrdersDisabledError,
    TooManyRequestsError,
    classify_metaapi_error,
)
from metaapi_hub.protocol import normalize_candles


def test_three_overlapping_syncs_raise_too_many_requests() -> None:
    """A second and third synchronize lose while the first slot is held."""

    async def _run() -> None:
        broker = InMemoryBroker(sync_delay=0.05)
        outcomes = await asyncio.gather(
            *[broker.synchronize() for _ in range(3)],
            return_exceptions=True,
        )
        successes = [item for item in outcomes if item is None]
        rejected = [item for item in outcomes if isinstance(item, TooManyRequestsError)]
        assert len(successes) == 1
        assert len(rejected) == 2
        assert broker.synchronize_calls == 1
        assert broker.rejected_syncs == 2
        assert all(item.max_sync == 1 for item in rejected)

    asyncio.run(_run())


def test_held_slot_rejects_a_later_sync_until_close() -> None:
    async def _run() -> None:
        broker = InMemoryBroker()
        await broker.synchronize()
        with pytest.raises(TooManyRequestsError):
            await broker.synchronize()
        await broker.close()
        await broker.synchronize()
        assert broker.synchronize_calls == 2

    asyncio.run(_run())


def test_unserialized_rpc_overlaps_without_the_hub() -> None:
    """The bare broker allows overlapping RPC. The hub tests require depth 1."""

    async def _run() -> None:
        broker = InMemoryBroker(rpc_delay=0.05)
        await broker.synchronize()
        await asyncio.gather(broker.get_account_information(), broker.get_symbol_price("BTCUSD"))
        assert broker.max_rpc_depth >= 2

    asyncio.run(_run())


def test_classify_metaapi_errors() -> None:
    class SdkTooMany(Exception):
        status_code = 429

    class SdkTimeout(Exception):
        pass

    SdkTimeout.__name__ = "TimeoutException"

    too_many = classify_metaapi_error(SdkTooMany("TooManyRequestsError"))
    assert isinstance(too_many, TooManyRequestsError)

    gateway = classify_metaapi_error(Exception("504 Gateway Timeout"))
    assert isinstance(gateway, GatewayTimeoutError)

    offline = classify_metaapi_error(Exception("not connected to broker"))
    assert isinstance(offline, NotConnectedError)

    timed = classify_metaapi_error(SdkTimeout("slow"))
    assert isinstance(timed, HubError)
    assert timed.code == "TIMEOUT"


def test_metaapi_broker_redacts_token_and_refuses_a_masked_sdk_import() -> None:
    """SDK_MISSING must be proven without calling MetaAPI.

    On a host where ``metaapi_cloud_sdk`` is installed, calling the real
    ``synchronize`` would open a client. This test hides that module so the
    refusal path runs everywhere, and the token never appears in errors.
    """

    async def _run() -> None:
        import sys
        from unittest.mock import patch

        secret = "super-secret-token-value"
        broker = MetaApiBroker(secret, "account-id")
        assert secret not in repr(broker)
        assert broker.connected is False
        assert broker.order_calls == 0
        with patch.dict(sys.modules, {"metaapi_cloud_sdk": None}):
            with pytest.raises(HubError) as caught:
                await broker.synchronize()
        assert caught.value.code == "SDK_MISSING"
        assert secret not in str(caught.value)
        assert broker.connected is False
        assert broker.synchronize_calls == 0
        assert broker.order_calls == 0
        assert broker.mutation_calls == 0

    asyncio.run(_run())


def test_owner_built_outside_a_loop_still_syncs_once_and_denies_orders() -> None:
    """Python 3.9 binds asyncio primitives to the loop that exists at construction.

    ``asyncio.run`` clears that loop. Building the broker afterwards must still
    synchronize once and must still refuse orders.
    """

    async def _warm_up() -> None:
        await asyncio.sleep(0)

    asyncio.run(_warm_up())

    from metaapi_hub.owner import SyncOwner

    broker = InMemoryBroker()
    owner = SyncOwner(broker, mode="shadow", orders_mode="deny", backoff_base=0.0)

    async def _use() -> None:
        await owner.ensure_connected()
        info = await owner.read("get_account_information")
        assert info["equity"] == 100000.0
        with pytest.raises(OrdersDisabledError):
            await owner.mutate(
                "create_market_order",
                {
                    "symbol": "BTCUSD",
                    "side": "BUY",
                    "volume": 0.01,
                    "comment": "GRIFF_BTC",
                },
                engine="btc",
            )
        assert broker.synchronize_calls == 1
        assert broker.order_calls == 0
        assert broker.mutation_calls == 0
        assert owner.orders_are_live() is False

    asyncio.run(_use())


def test_normalize_candles_sorts_and_keeps_the_newest_limit() -> None:
    candles = normalize_candles(
        [
            {"time": "2026-09-02T00:00:00+00:00", "close": 2},
            {"time": "2026-09-01T00:00:00+00:00", "close": 1},
            {"time": "2026-09-03T00:00:00+00:00", "close": 3},
        ],
        limit=2,
    )
    assert [item["close"] for item in candles] == [2, 3]
