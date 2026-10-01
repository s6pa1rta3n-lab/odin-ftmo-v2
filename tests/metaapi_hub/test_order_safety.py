"""Order path: deny, dry-run, dual live interlock, duplicate suppression, serialization."""

from __future__ import annotations

import asyncio

import pytest

from metaapi_hub.adapter import HubBackedWrapper
from metaapi_hub.broker import InMemoryBroker
from metaapi_hub.errors import DryRunOrderError, HubError, HubRequestError, OrdersDisabledError
from metaapi_hub.harness import start_hub
from metaapi_hub.owner import SyncOwner


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


async def _no_sleep(_seconds: float) -> None:
    return None


_ENTRY = {
    "symbol": "US100.cash",
    "side": "BUY",
    "volume": 0.01,
    "stop_loss": 100.0,
    "take_profit": 120.0,
    "comment": "GRIFF_1H_BREAKOUT",
}


def test_deny_and_dry_run_never_call_the_broker() -> None:
    async def _run() -> None:
        methods = [
            "create_market_order",
            "create_stop_order",
            "create_limit_order",
            "cancel_order",
            "close_position",
            "close_position_partially",
            "modify_position",
        ]
        for orders_mode, expected in (("deny", OrdersDisabledError), ("dry_run", DryRunOrderError)):
            broker = InMemoryBroker()
            owner = SyncOwner(broker, mode="shadow", orders_mode=orders_mode, sleep=_no_sleep)
            for method in methods:
                params = dict(_ENTRY)
                if method in {"create_stop_order", "create_limit_order"}:
                    params["price"] = 110.0
                if method == "cancel_order":
                    params = {"order_id": "1"}
                if method in {"close_position", "modify_position"}:
                    params = {"position_id": "9", "stop_loss": 1.0}
                if method == "close_position_partially":
                    params = {"position_id": "9", "volume": 0.01}
                with pytest.raises(expected) as caught:
                    await owner.mutate(method, params, engine="us100")
                if orders_mode == "dry_run" and method == "create_market_order":
                    assert caught.value.receipt["sent"] is False
                    assert caught.value.receipt["dryRun"] is True
                    assert caught.value.receipt["numericCode"] is None
            assert broker.order_calls == 0
            assert broker.mutation_calls == 0
            assert broker.synchronize_calls == 0

    asyncio.run(_run())


def test_shadow_downgrades_live_orders_and_live_mode_needs_the_env_interlock(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        downgraded = SyncOwner(InMemoryBroker(), mode="shadow", orders_mode="live")
        assert downgraded.orders_mode == "dry_run"
        assert downgraded.orders_are_live() is False

        broker = InMemoryBroker()
        owner = SyncOwner(broker, mode="live", orders_mode="live", account_id="acct-1", sleep=_no_sleep)
        with pytest.raises(OrdersDisabledError):
            await owner.mutate("create_market_order", dict(_ENTRY), engine="btc")
        assert broker.order_calls == 0

        monkeypatch.setenv("ODIN_METAAPI_HUB_ORDERS", "live")
        result = await owner.mutate("create_market_order", dict(_ENTRY), engine="btc")
        assert result["numericCode"] == 10009
        assert result["dryRun"] is False
        assert broker.order_calls == 1
        assert broker.max_rpc_depth == 1

    asyncio.run(_run())


def test_duplicate_order_window_and_parallel_orders_stay_serialized(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        monkeypatch.setenv("ODIN_METAAPI_HUB_ORDERS", "live")
        clock = _Clock()
        broker = InMemoryBroker(rpc_delay=0.05)
        owner = SyncOwner(
            broker,
            mode="live",
            orders_mode="live",
            duplicate_window=10.0,
            clock=clock,
            sleep=_no_sleep,
        )
        first = await owner.mutate("create_market_order", dict(_ENTRY), engine="us100")
        second = await owner.mutate("create_market_order", dict(_ENTRY), engine="us100")
        assert first["orderId"] == second["orderId"]
        assert broker.order_calls == 1
        assert owner.duplicate_suppressions == 1

        other = dict(_ENTRY)
        other["comment"] = "GRIFF_US100_NY"
        await asyncio.gather(
            owner.mutate("create_market_order", other, engine="us100"),
            owner.mutate("create_stop_order", {**_ENTRY, "price": 50.0, "comment": "GRIFF_GOLD_BREAKOUT"}, engine="gold"),
        )
        assert broker.order_calls == 3
        assert broker.max_rpc_depth == 1

        clock.now = 11.0
        await owner.mutate("create_market_order", dict(_ENTRY), engine="us100")
        assert broker.order_calls == 4

    asyncio.run(_run())


def test_entry_validation_rejects_missing_comment_and_bad_volume() -> None:
    async def _run() -> None:
        owner = SyncOwner(InMemoryBroker(), mode="shadow", orders_mode="dry_run", sleep=_no_sleep)
        with pytest.raises(HubError) as missing:
            await owner.mutate(
                "create_market_order",
                {"symbol": "BTCUSD", "side": "BUY", "volume": 0.01},
                engine="btc",
            )
        assert missing.value.code == "COMMENT_REQUIRED"
        with pytest.raises(HubError) as bad_volume:
            await owner.mutate(
                "create_market_order",
                {"symbol": "BTCUSD", "side": "BUY", "volume": float("nan"), "comment": "X"},
                engine="btc",
            )
        assert bad_volume.value.code == "BAD_REQUEST"
        assert owner.broker.order_calls == 0

    asyncio.run(_run())


def test_socket_dry_run_order_does_not_advance_a_filled_code() -> None:
    async def _run() -> None:
        handle = await start_hub(mode="shadow", orders_mode="dry_run")
        wrapper = HubBackedWrapper(
            "token-is-not-forwarded",
            "shadow-account",
            engine_name="gold",
            socket_path=handle.socket_path,
            shadow=True,
        )
        try:
            await wrapper.connect()
            with pytest.raises(HubRequestError) as caught:
                await wrapper.connection.create_market_buy_order(  # type: ignore[union-attr]
                    "XAUUSD",
                    0.01,
                    stop_loss=4400.0,
                    take_profit=4500.0,
                    options={"comment": "GRIFF_GOLD_BREAKOUT"},
                )
            assert caught.value.code == "DRY_RUN"
            assert caught.value.receipt["sent"] is False
            assert caught.value.receipt["numericCode"] is None
            assert handle.broker.order_calls == 0
            assert handle.broker.mutation_calls == 0
            assert not hasattr(wrapper, "token")
        finally:
            await wrapper.detach()
            await handle.close()

    asyncio.run(_run())


def test_live_owner_rejects_shadow_engines_and_foreign_accounts() -> None:
    broker = InMemoryBroker()
    owner = SyncOwner(broker, mode="live", orders_mode="deny", account_id="acct-real")
    with pytest.raises(HubError) as mismatch:
        owner.register("btc", 11, "acct-real", "shadow")
    assert mismatch.value.code == "MODE_MISMATCH"
    with pytest.raises(HubError) as account:
        owner.register("btc", 11, "other-account", "on")
    assert account.value.code == "ACCOUNT_MISMATCH"
    assert broker.synchronize_calls == 0
    assert broker.connected is False
