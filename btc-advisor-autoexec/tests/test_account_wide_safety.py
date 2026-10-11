"""Safety check on 6c07d0f (Trading Ops, 2026-10-11): the position limit, the breakeven rule and the
daily-cap floating P&L must read EVERY open position on the account (Odin 2026-10-10 19:07 ET),
and /status must list them all. Fixture: XAUUSD manual, ETHUSD auto, US100.cash from another engine.
"""

from __future__ import annotations

import json
import threading
import urllib.request

import pytest

from autoexec.config import Config
from autoexec.server import make_server
from conftest import MAGIC, SPEC, FakeBroker, deal, entry, make_executor, position

XAU_MANUAL = dict(pid="X", symbol="XAUUSD", magic=0, comment="", open_price=4300.0, stop_loss=4290.0, take_profit=4500.0, profit=-40.0, commission=0.0)
ETH_AUTO = dict(pid="E", symbol="ETHUSD", magic=MAGIC, comment="BTC_ADVISOR_AUTO", open_price=3000.0, stop_loss=3000.0, take_profit=3300.0, profit=-25.0, commission=-2.0, swap=-1.0)
NDX_OTHER = dict(pid="N", symbol="US100.cash", magic=777, comment="GRIFF_US100", side="SELL", open_price=24000.0, stop_loss=24000.0, take_profit=23000.0, profit=12.0, commission=0.0)


def broker_with(*specs, **kw) -> FakeBroker:
    b = FakeBroker(positions=[position(**s) for s in specs], **kw)
    for sym, q in (("XAUUSD", {"bid": 4400.0, "ask": 4400.3}), ("ETHUSD", {"bid": 3000.0, "ask": 3001.5}), ("US100.cash", {"bid": 24000.0, "ask": 24001.5})):
        b.set_symbol(sym, spec=dict(SPEC, profitCurrency="USD"), quote=q)
    return b


def _ex(tmp_path, b, **env):
    e = {"AUTOEXEC_ORDERS_ENABLED": "1"}
    e.update(env)
    return make_executor(tmp_path, b, env=e)


# (a) position limit reads every open position on the account

def test_a_position_limit_counts_manual_auto_and_other_engine_on_other_symbols(tmp_path):
    ex = _ex(tmp_path, broker_with(XAU_MANUAL, ETH_AUTO, NDX_OTHER))
    d = ex.decide_entry(entry("BUY"))  # BTCUSD request; zero BTCUSD positions open
    assert d["code"] == "MAX_POSITIONS", d
    assert d["guards"]["total_open"] == 3 and d["guards"]["open_by_symbol"] == {"ETHUSD": 1, "XAUUSD": 1, "US100.cash": 1}
    assert ex.broker.trade_calls == []


@pytest.mark.parametrize("pair", [(XAU_MANUAL, ETH_AUTO), (XAU_MANUAL, NDX_OTHER), (ETH_AUTO, NDX_OTHER)])
def test_a_any_two_positions_anywhere_block_a_third(tmp_path, pair):
    ex = _ex(tmp_path, broker_with(*pair))
    assert ex.decide_entry(entry("BUY"))["code"] == "MAX_POSITIONS"


def test_a_count_is_account_wide_regardless_of_allowlist_or_scope_env(tmp_path):
    ex = _ex(tmp_path, broker_with(XAU_MANUAL, NDX_OTHER), AUTOEXEC_SYMBOLS="BTCUSD,ETHUSD", AUTOEXEC_SECOND_POSITION_SCOPE="allowed")
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "MAX_POSITIONS" and d["guards"]["total_open"] == 2
    assert d["guards"]["second_position_scope"] == "all" and d["guards"]["second_position_scope_requested"] == "allowed"


# (b) breakeven rule for a second entry checks every open position on the account

@pytest.mark.parametrize("existing,label", [(XAU_MANUAL, "XAUUSD manual below BE"), (dict(ETH_AUTO, stop_loss=2990.0), "ETHUSD auto below BE"), (dict(NDX_OTHER, stop_loss=24010.0), "US100.cash other engine, short with SL above entry")])
def test_b_breakeven_checked_on_every_account_position(tmp_path, existing, label):
    ex = _ex(tmp_path, broker_with(existing))
    d = ex.decide_entry(entry("BUY"))  # BTCUSD second entry
    assert d["code"] == "SECOND_SL_NOT_BREAKEVEN", (label, d)
    bad = d["detail"]["second_position"]["existing"][0]
    assert bad["symbol"] == existing["symbol"] and bad["breakeven_or_better"] is False
    assert ex.broker.trade_calls == []


@pytest.mark.parametrize("existing", [dict(XAU_MANUAL, stop_loss=4300.0, profit=5.0), dict(ETH_AUTO, profit=3.0, commission=0.0, swap=0.0), NDX_OTHER])
def test_b_breakeven_position_on_another_symbol_allows_second_entry(tmp_path, existing):
    ex = _ex(tmp_path, broker_with(existing))
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "PLACED", d
    assert d["second_position"]["existing"][0]["symbol"] == existing["symbol"] and d["second_position"]["passed"]


# (c) daily-cap floating P&L includes every auto-magic position on every symbol

def test_c_floating_pnl_counts_eth_auto_not_manual_or_other_engine(tmp_path):
    b = broker_with(XAU_MANUAL, ETH_AUTO, NDX_OTHER)
    ex = _ex(tmp_path, b)
    st = ex.status()["guards"]
    # ETH auto: profit -25 + commission -2 + swap -1 = -28; XAUUSD manual (-40) and US100 other (+12) excluded
    assert st["daily_pnl"] == {"closed": 0.0, "floating": -28.0, "total": -28.0, "deals_counted": 0, "positions_counted": 1}


def test_c_eth_auto_floating_loss_trips_the_shared_cap_for_a_btc_entry(tmp_path):
    b = broker_with(dict(ETH_AUTO, profit=-180.0, commission=-2.0, swap=0.0), deals=[deal("s", time="2026-10-10T08:00:00Z", profit=-318.0, symbol="SOLUSD")])
    ex = _ex(tmp_path, b)
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "DAILY_CAP_HIT" and d["detail"]["pnl"]["floating"] == -182.0 and d["detail"]["pnl"]["total"] == -500.0
    assert ex.broker.trade_calls == []


def test_c_auto_position_on_a_non_allowlisted_symbol_still_counts(tmp_path):
    b = broker_with(dict(ETH_AUTO, symbol="XAUUSD", pid="A", profit=-520.0, commission=0.0, swap=0.0, stop_loss=4300.0, open_price=4300.0))
    ex = _ex(tmp_path, b, AUTOEXEC_SYMBOLS="BTCUSD")
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "DAILY_CAP_HIT" and d["detail"]["pnl"]["floating"] == -520.0


# /status lists ALL account positions

def test_status_lists_every_account_position_with_details(tmp_path):
    b = broker_with(XAU_MANUAL, ETH_AUTO, NDX_OTHER)
    ex = make_executor(tmp_path, b)
    g = ex.status()["guards"]
    rows = {r["id"]: r for r in g["positions"]}
    assert set(rows) == {"X", "E", "N"} and g["total_open"] == 3
    assert rows["X"] == {
        "id": "X", "symbol": "XAUUSD", "side": "BUY", "volume": 0.4, "open_price": 4300.0, "stop_loss": 4290.0, "take_profit": 4500.0,
        "magic": 0, "comment": "", "kind": "manual", "breakeven_or_better": False, "profit": -40.0, "commission": 0.0, "swap": 0.0,
        "floating_pnl": -40.0, "open_time": None,
    }
    assert rows["E"]["kind"] == "auto" and rows["E"]["breakeven_or_better"] is True and rows["E"]["floating_pnl"] == -28.0
    assert rows["N"]["kind"] == "other" and rows["N"]["side"] == "SELL" and rows["N"]["magic"] == 777 and rows["N"]["comment"] == "GRIFF_US100"
    # grouped view still present
    assert [p["symbol"] for p in g["book"]["manual"]] == ["XAUUSD"] and [p["symbol"] for p in g["book"]["other"]] == ["US100.cash"]


def test_status_positions_over_http_and_unaffected_by_allowlist(tmp_path):
    b = broker_with(XAU_MANUAL, ETH_AUTO, NDX_OTHER)
    ex = make_executor(tmp_path, b, env={"AUTOEXEC_SYMBOLS": "BTCUSD", "AUTOEXEC_SECOND_POSITION_SCOPE": "allowed"})
    srv = make_server(ex, host="127.0.0.1", port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/status", timeout=5) as resp:
            body = json.loads(resp.read())
    finally:
        srv.shutdown()
        srv.server_close()
    g = body["guards"]
    assert sorted(p["symbol"] for p in g["positions"]) == ["ETHUSD", "US100.cash", "XAUUSD"]
    assert g["total_open"] == 3 and g["second_position_scope"] == "all"
    assert set(g["per_symbol"]) >= {"BTCUSD", "ETHUSD", "US100.cash", "XAUUSD"}


def test_scope_config_is_always_all():
    assert Config.from_env({}).second_position_scope == "all"
    c = Config.from_env({"AUTOEXEC_SECOND_POSITION_SCOPE": "allowed"})
    assert c.second_position_scope == "all" and c.second_position_scope_requested == "allowed"
