"""Flag defaults, real engine adapters, and the shadow probe."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from metaapi_hub import DEFAULT_HUB_MODE
from metaapi_hub.adapter import HubBackedWrapper, to_mt5
from metaapi_hub.factory import build_execution_wrapper, engine_name_for_symbol, hub_mode
from metaapi_hub.harness import assert_shadow_proof, start_hub
from metaapi_hub.shadow_probe import run_shadow_probe


def test_default_flag_is_off_and_unknown_values_stay_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Off mode is the direct wrapper, including when that module is installed.

    Constructing the real ``MetaApiWrapper`` calls ``MetaApi(token)``. This
    test substitutes a stub, and separately blocks the import, so neither
    host opens a client. Shadow mode still returns the hub adapter.
    """

    import sys
    import types

    assert DEFAULT_HUB_MODE == "off"
    assert hub_mode() == "off"
    monkeypatch.setenv("ODIN_METAAPI_HUB", "please")
    assert hub_mode() == "off"
    monkeypatch.setenv("ODIN_METAAPI_HUB", "0")
    assert hub_mode() == "off"

    stub = types.ModuleType("MetaApiWrapper")

    class SentinelWrapper:
        def __init__(self, token: str, account_id: str) -> None:
            self.account_id = account_id
            self.connection = None
            self.api = None
            self.saw_token = token

    stub.MetaApiWrapper = SentinelWrapper
    monkeypatch.setitem(sys.modules, "MetaApiWrapper", stub)
    direct = build_execution_wrapper("not-used-for-network", "acct-1", engine_name="btc")
    assert isinstance(direct, SentinelWrapper)
    assert direct.connection is None
    assert direct.api is None
    assert not isinstance(direct, HubBackedWrapper)

    monkeypatch.setitem(sys.modules, "MetaApiWrapper", None)
    with pytest.raises(RuntimeError, match="MetaApiWrapper module not available"):
        build_execution_wrapper("not-used-for-network", "acct-1", engine_name="btc")

    monkeypatch.setenv("ODIN_METAAPI_HUB", "shadow")
    hub_wrapper = build_execution_wrapper(
        "not-used-for-network",
        "acct-1",
        engine_name="btc",
        socket_path="/tmp/odin-metaapi-hub-test.sock",
    )
    assert isinstance(hub_wrapper, HubBackedWrapper)
    assert hub_wrapper.client.local_synchronize_calls == 0


def test_off_mode_uses_installed_metaapi_wrapper_without_constructing_metaapi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the real wrapper imports, off mode must return it and not connect.

    ``__init__`` is replaced so ``MetaApi(token)`` is not called. Hosts without
    the SDK skip this assertion; the stub test above still covers them.
    """

    import sys

    try:
        import MetaApiWrapper as real_mod
    except ImportError:
        pytest.skip("MetaApiWrapper is not importable in this environment")

    def _safe_init(self, token: str, account_id: str) -> None:
        self.account_id = account_id
        self.connection = None
        self.account = None
        self.api = None
        self._constructed_without_sdk_call = True

    monkeypatch.setattr(real_mod.MetaApiWrapper, "__init__", _safe_init)
    monkeypatch.setitem(sys.modules, "MetaApiWrapper", real_mod)
    monkeypatch.delenv("ODIN_METAAPI_HUB", raising=False)
    wrapper = build_execution_wrapper("not-used-for-network", "acct-1", engine_name="us100")
    assert isinstance(wrapper, real_mod.MetaApiWrapper)
    assert wrapper.connection is None
    assert wrapper.api is None
    assert wrapper._constructed_without_sdk_call is True
    assert not isinstance(wrapper, HubBackedWrapper)


def test_symbol_mapping_matches_the_existing_wrapper() -> None:
    assert to_mt5("BTCUSDT") == "BTCUSD"
    assert to_mt5("US100.cash") == "US100.cash"
    assert to_mt5("XAUUSD") == "XAUUSD"
    assert to_mt5("DOTUSDT") == "DOTUSD"
    assert engine_name_for_symbol("BTCUSD") == "btc"
    assert engine_name_for_symbol("US100.cash") == "us100"
    assert engine_name_for_symbol("XAUUSD") == "gold"


def test_shadow_probe_proves_one_sync_and_no_orders() -> None:
    evidence = asyncio.run(run_shadow_probe())
    assert evidence["ok"] is True
    assert {item["engine"] for item in evidence["engines"]} == {"btc", "us100", "gold"}
    assert all(item["order_sent"] is False for item in evidence["engines"])
    assert all(item["local_synchronize_calls"] == 0 for item in evidence["engines"])
    assert all(item["candles"] >= 15 for item in evidence["engines"])
    assert_shadow_proof(evidence["snapshot"], engines={"btc", "us100", "gold"})
    assert "DO NOT CUT OVER" in evidence["note"]


def test_griff_engines_share_one_sync_and_do_not_fallback_when_the_hub_is_down(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def _run() -> None:
        from griff_engine_gold import GoldEngine
        from griff_engine_live import GriffLiveEngine
        from griff_engine_us100 import US100Engine

        handle = await start_hub(mode="shadow", orders_mode="deny", account_id="shadow-account")
        monkeypatch.setenv("ODIN_METAAPI_HUB", "shadow")
        monkeypatch.setenv("ODIN_METAAPI_HUB_SOCKET", handle.socket_path)
        config_path = tmp_path / "config_us100.json"
        config_path.write_text(json.dumps({"symbol": "US100.cash", "risk_pct": 0.01}), encoding="utf-8")
        engines = []
        try:
            for symbol in ("BTCUSD", "US100.cash", "XAUUSD"):
                engine = GriffLiveEngine(token="do-not-log-this-token", account_id="shadow-account", symbol=symbol)
                assert await engine.connect_account() is True
                candles = await engine.fetch_completed_1h_candles(limit=30)
                assert len(candles) >= 15
                assert engine.wrapper.client.local_synchronize_calls == 0
                assert not hasattr(engine.wrapper, "token")
                engines.append(engine)

            us100 = US100Engine("do-not-log-this-token", "shadow-account", config_path=str(config_path))
            await us100.connect()
            us_candles = await us100.fetch_15m_candles()
            assert len(us_candles) >= 15
            assert us100.wrapper.client.local_synchronize_calls == 0

            gold = GoldEngine("do-not-log-this-token", "shadow-account")
            await gold.connect()
            gold_candles = await gold.fetch_15m_candles(limit=20)
            assert len(gold_candles) == 20
            assert gold.wrapper.client.local_synchronize_calls == 0

            assert handle.broker.synchronize_calls == 1
            assert handle.broker.order_calls == 0
            assert handle.owner.snapshot()["orders_live"] is False
            names = set(handle.owner.snapshot()["clients"])
            assert {"btc", "us100", "gold"}.issubset(names)

            await engines[0].wrapper.streaming_connection.close()
            await engines[1].fetch_account_information_safe()
            assert handle.broker.synchronize_calls == 1
            assert handle.broker.connected is True
        finally:
            await handle.close()

        monkeypatch.setenv("ODIN_METAAPI_HUB", "on")
        monkeypatch.setenv("ODIN_METAAPI_HUB_SOCKET", str(tmp_path / "missing.sock"))
        offline = GriffLiveEngine(token="x", account_id="shadow-account", symbol="BTCUSD")
        assert await offline.connect_account() is False
        assert isinstance(offline.wrapper, HubBackedWrapper)
        assert offline.wrapper.client.local_synchronize_calls == 0

    asyncio.run(_run())


def test_griff_self_test_runs_against_shadow_without_a_second_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        from griff_engine_live import GriffLiveEngine

        handle = await start_hub(mode="shadow", orders_mode="deny", account_id="shadow-account")
        monkeypatch.setenv("ODIN_METAAPI_HUB", "shadow")
        monkeypatch.setenv("ODIN_METAAPI_HUB_SOCKET", handle.socket_path)
        try:
            engine = GriffLiveEngine(token="unused", account_id="shadow-account", symbol="US100.cash")
            assert await engine.run_self_test() is True
            assert handle.broker.synchronize_calls == 1
            assert handle.broker.order_calls == 0
            assert handle.broker.mutation_calls == 0
        finally:
            await handle.close()

    asyncio.run(_run())


def _exec_lines(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip().startswith("ExecStart="))


def test_repo_service_installers_do_not_enable_the_hub() -> None:
    root = Path(__file__).resolve().parents[2]
    watched = [
        root / "setup_gold_service.sh",
        root / "setup_us100_service.sh",
        root / "ftmo_hft_omni.service",
        root / "ftmo_london_reversal.service",
    ]
    for path in watched:
        text = path.read_text(encoding="utf-8")
        assert "metaapi_hub" not in text
        assert "ODIN_METAAPI_HUB" not in text

    example = (root / "deploy" / "examples" / "odin-metaapi-hub.service").read_text(encoding="utf-8")
    readonly = (root / "deploy" / "examples" / "odin-metaapi-hub.live-readonly.service.example").read_text(encoding="utf-8")
    for text in (example, readonly):
        assert "DO NOT" in text
        executed = _exec_lines(text)
        assert "--enable-live-orders" not in executed
        assert "--orders live" not in executed
        assert "ODIN_METAAPI_HUB=on" not in text
        assert "ODIN_METAAPI_HUB=1" not in text
    assert "--mode shadow" in _exec_lines(example)
    assert "--orders deny" in _exec_lines(example)
    assert "--mode live" in _exec_lines(readonly)
    assert "--orders deny" in _exec_lines(readonly)

    live = (root / "deploy" / "examples" / "odin-metaapi-hub.live-orders.service.example").read_text(encoding="utf-8")
    live_exec = _exec_lines(live)
    assert "intentional cutover" in live.lower()
    assert "--mode live" in live_exec
    assert "--orders live" in live_exec
    assert "--enable-live-orders" in live_exec
    assert "ODIN_METAAPI_HUB_ORDERS=live" in live
    assert "Environment=ODIN_METAAPI_HUB=on" not in live
    assert "Environment=ODIN_METAAPI_HUB=1" not in live
    dropin = (root / "deploy" / "examples" / "griff-hub-on.conf.example").read_text(encoding="utf-8")
    assert "ODIN_METAAPI_HUB=on" in dropin
    assert "ODIN_METAAPI_HUB_SOCKET=" in dropin
    assert "PYTHONPATH=" in dropin
    assert "intentional cutover" in dropin.lower()
