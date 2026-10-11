"""Multi-symbol extension (Odin, 2026-10-10 17:07 ET): BTCUSD + ETHUSD + SOLUSD on one account.

Per-symbol spec/quote/commission; shared daily cap; 2 positions total across symbols
incl. manual; cross-symbol breakeven requirement; BTC behaviour unchanged when no
symbol is given.
"""

from __future__ import annotations

import json
import threading
import urllib.request

import pytest

from autoexec.config import Config, env_suffix
from autoexec.server import make_server
from conftest import ACCOUNT, MAGIC, SPEC, FakeBroker, deal, entry, make_executor, position

# ETH: $1 per price unit per lot, lot step 0.1 ; SOL: $1 per unit, lot step 1 (min 1)
ETH_SPEC = dict(SPEC, volumeStep=0.1, minVolume=0.1, maxVolume=100, description="Ethereum vs US Dollar")
ETH_QUOTE = {"bid": 3000.0, "ask": 3001.5}
SOL_SPEC = dict(SPEC, volumeStep=1, minVolume=1, maxVolume=1000, description="Solana vs US Dollar")
SOL_QUOTE = {"bid": 150.0, "ask": 150.2}

ETH_COMM = {"AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_ETHUSD": "2.2"}
SOL_COMM = {"AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_SOLUSD": "0.5"}
LEV = {"AUTOEXEC_SYMBOL_LEVERAGE": "2", "AUTOEXEC_SYMBOL_LEVERAGE_ETHUSD": "2", "AUTOEXEC_SYMBOL_LEVERAGE_SOLUSD": "2"}


def multi_broker(**kw) -> FakeBroker:
    b = FakeBroker(**kw)
    b.set_symbol("ETHUSD", spec=ETH_SPEC, quote=ETH_QUOTE)
    b.set_symbol("SOLUSD", spec=SOL_SPEC, quote=SOL_QUOTE)
    return b


def eth_entry(side="BUY", stop=2900.0, target=3300.0, **extra):
    return entry(side, stop=stop, target=target, **{"symbol": "ETHUSD", **extra})


def sol_entry(side="BUY", stop=140.0, target=175.0, **extra):
    return entry(side, stop=stop, target=target, **{"symbol": "SOLUSD", **extra})


def _ex(tmp_path, broker=None, *, enabled=True, env=None):
    e = {"AUTOEXEC_ORDERS_ENABLED": "1" if enabled else "0"}
    e.update(ETH_COMM)
    e.update(SOL_COMM)
    e.update(LEV)
    e.update(env or {})
    return make_executor(tmp_path, broker or multi_broker(), env=e)


# ---------------------------------------------------------------- symbol field: default, allowed set, rejection

def test_default_symbol_is_btcusd_and_order_carries_it(tmp_path):
    ex = _ex(tmp_path)
    d = ex.decide_entry(entry("BUY"))  # no symbol field
    assert d["symbol"] == "BTCUSD" and d["order"]["symbol"] == "BTCUSD" and d["code"] == "PLACED"
    assert ex.broker.trade_calls[0]["symbol"] == "BTCUSD"


def test_explicit_symbol_case_insensitive(tmp_path):
    ex = _ex(tmp_path)
    d = ex.decide_entry(eth_entry(symbol="ethusd"))
    assert d["symbol"] == "ETHUSD" and d["order"]["symbol"] == "ETHUSD" and d["code"] == "PLACED"


@pytest.mark.parametrize("sym", ["XAUUSD", "US100.cash", "DOGEUSD", "BTC", 123])
def test_symbol_not_listed_by_broker_rejected(tmp_path, sym):
    # 19:07 ET #1: validation is against the broker's live list; the fake broker lists only BTC/ETH/SOL here
    ex = _ex(tmp_path)
    d = ex.decide_entry(entry("BUY", symbol=sym))
    assert d["accepted"] is False and d["code"] == "SYMBOL_NOT_LISTED"
    assert d["symbol"] == str(sym)
    assert ex.broker.trade_calls == [] and "symbol_specification" not in ex.broker.read_calls


def test_allowed_set_configurable(tmp_path):
    ex = _ex(tmp_path, env={"AUTOEXEC_SYMBOLS": "BTCUSD,ETHUSD"})
    assert ex.cfg.symbols == ("BTCUSD", "ETHUSD")
    assert ex.decide_entry(sol_entry())["code"] == "SYMBOL_NOT_ALLOWED"
    assert ex.decide_entry(eth_entry())["code"] == "PLACED"
    with pytest.raises(ValueError):
        Config.from_env({"AUTOEXEC_SYMBOLS": "ETHUSD"})  # default symbol BTCUSD not in the allowlist
    assert Config.from_env({"AUTOEXEC_SYMBOLS": "ETHUSD", "AUTOEXEC_SYMBOL": "ETHUSD"}).symbol == "ETHUSD"


def test_config_defaults_for_multi_symbol():
    c = Config.from_env({})
    assert c.symbols == () and c.symbol == "BTCUSD"  # empty allowlist = everything the broker lists (19:07 ET)
    assert c.commission_env_for("BTCUSD") == 27.0
    assert c.commission_env_for("ETHUSD") is None and c.commission_env_for("SOLUSD") is None  # never guessed
    assert c.second_position_scope == "all"
    assert env_suffix("US100.cash") == "US100_CASH"
    c2 = Config.from_env({"AUTOEXEC_SYMBOLS": "BTCUSD,US100.cash", "AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_US100_CASH": "4"})
    assert c2.commission_env_for("US100.cash") == 4.0


# ---------------------------------------------------------------- per-symbol sizing with different specs

def test_eth_sized_from_its_own_spec_quote_and_commission(tmp_path):
    ex = _ex(tmp_path)
    # BUY fills at ask 3001.5; stop 2900 -> 101.5; spread 1.5; commission 2.2 -> 105.2 per lot
    d = ex.decide_entry(eth_entry("BUY", stop=2900, target=3300))
    assert d["code"] == "PLACED", d
    assert d["stop_distance"] == 101.5 and d["spread"] == 1.5 and d["commission_per_lot_roundtrip"] == 2.2
    assert d["per_lot_loss"] == 105.2
    # floor(250 / 105.2 = 2.376, step 0.1) = 2.3
    assert d["lots"] == 2.3 and d["risk_usd"] == pytest.approx(2.3 * 105.2) and d["risk_usd"] <= 250
    assert ex.broker.trade_calls[0] == {
        "actionType": "ORDER_TYPE_BUY", "symbol": "ETHUSD", "volume": 2.3, "stopLoss": 2900.0, "takeProfit": 3300.0,
        "comment": "BTC_ADVISOR_AUTO", "magic": MAGIC,
    }


def test_sol_rounds_down_to_whole_lots(tmp_path):
    ex = _ex(tmp_path)
    # SELL fills at bid 150; stop 160 -> 10; spread 0.2; commission 0.5 -> 10.7 per lot; 250/10.7 = 23.36 -> 23 lots
    d = ex.decide_entry(sol_entry("SELL", stop=160, target=120))
    assert d["code"] == "PLACED" and d["lots"] == 23.0 and d["risk_usd"] == pytest.approx(23 * 10.7)


def test_sol_skipped_when_min_lot_exceeds_250(tmp_path):
    ex = _ex(tmp_path)
    # stop 400 units away: per-lot loss 400.7 > 250 with min lot 1 -> skip
    d = ex.decide_entry(sol_entry("SELL", stop=550, target=100))
    assert d["code"] == "SKIP_MIN_VOLUME" and d["lots"] == 0.0 and ex.broker.trade_calls == []


def test_each_symbol_uses_its_own_tick_value(tmp_path):
    b = multi_broker()
    b.set_symbol("ETHUSD", spec=dict(ETH_SPEC, tickSize=0.01, tickValue=0.1), quote=ETH_QUOTE)  # $10 per unit per lot
    ex = _ex(tmp_path, b, enabled=False)
    d = ex.decide_entry(eth_entry("BUY", stop=2900, target=3300))
    # (101.5 + 1.5) * 10 + 2.2 = 1032.2 per lot -> 0.2 lots
    assert d["per_lot_loss"] == pytest.approx(1032.2) and d["lots"] == 0.2
    b2 = ex.decide_entry(entry("BUY"))
    assert b2["per_lot_loss"] == 567.0 and b2["lots"] == 0.44  # BTC unaffected


def test_non_market_and_missing_sl_tp_rejected_on_every_symbol(tmp_path):
    ex = _ex(tmp_path)
    for body in (eth_entry(entry_type="LIMIT"), sol_entry(entry_type="STOP")):
        assert ex.decide_entry(body)["code"] == "ENTRY_TYPE_NOT_MARKET"
    e = eth_entry()
    e.pop("target")
    assert ex.decide_entry(e)["code"] == "MISSING_TP"
    assert ex.broker.trade_calls == []


# ---------------------------------------------------------------- commission per symbol

def test_missing_commission_skips_with_clear_code(tmp_path):
    ex = _ex(tmp_path, env={"AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_SOLUSD": ""})
    d = ex.decide_entry(sol_entry())
    assert d["accepted"] is False and d["code"] == "COMMISSION_UNAVAILABLE"
    assert "SOLUSD" in d["reason"] and "AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_SOLUSD" in d["reason"]
    assert d["commission"]["source"] == "none" and d["commission"]["env_value"] is None and d["commission"]["model"] is None
    assert ex.broker.trade_calls == []


def test_btc_fallback_does_not_leak_to_other_symbols(tmp_path):
    ex = make_executor(tmp_path, multi_broker(), env={"AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP": "27"})
    assert ex.decide_entry(entry("BUY"))["commission_per_lot_roundtrip"] == 27.0
    assert ex.decide_entry(eth_entry())["code"] == "COMMISSION_UNAVAILABLE"


def test_deals_derived_commission_is_per_symbol(tmp_path):
    deals = [
        deal("i", time="2026-10-01T10:00:00Z", profit=0, commission=-1.0, entry_type="DEAL_ENTRY_IN", volume=1.0, position_id="E", symbol="ETHUSD", dtype="DEAL_TYPE_BUY"),
        deal("o", time="2026-10-01T12:00:00Z", profit=5, commission=-1.0, entry_type="DEAL_ENTRY_OUT", volume=1.0, position_id="E", symbol="ETHUSD"),
    ]
    ex = _ex(tmp_path, multi_broker(deals=deals), enabled=False, env={"AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_SOLUSD": ""})
    d_eth = ex.decide_entry(eth_entry())
    assert d_eth["commission_source"] == "deals" and d_eth["commission_per_lot_roundtrip"] == 2.0
    d_btc = ex.decide_entry(entry("BUY"))
    assert d_btc["commission_source"] == "env" and d_btc["commission_per_lot_roundtrip"] == 27.0  # ETH deals do not count for BTC
    assert ex.decide_entry(sol_entry())["code"] == "COMMISSION_UNAVAILABLE"


# ---------------------------------------------------------------- shared daily cap

def test_daily_cap_shared_across_symbols_closed_and_floating(tmp_path):
    deals = [deal("e1", time="2026-10-10T08:00:00Z", profit=-300.0, symbol="ETHUSD"), deal("s1", time="2026-10-10T08:30:00Z", profit=-120.0, commission=-5.0, symbol="SOLUSD")]
    positions = [position("E1", symbol="ETHUSD", open_price=3000.0, stop_loss=3000.0, take_profit=3300.0, profit=-70.0, commission=-5.0)]
    ex = _ex(tmp_path, multi_broker(deals=deals, positions=positions))
    d = ex.decide_entry(entry("BUY"))  # BTC entry blocked by ETH/SOL losses
    assert d["code"] == "DAILY_CAP_HIT", d
    assert d["detail"]["pnl"] == {"closed": -425.0, "floating": -75.0, "total": -500.0, "deals_counted": 2, "positions_counted": 1}
    assert ex.decide_entry(sol_entry())["code"] == "DAILY_CAP_LATCHED"
    assert ex.broker.trade_calls == []


def test_manual_losses_on_other_symbols_do_not_count(tmp_path):
    deals = [deal("m", time="2026-10-10T08:00:00Z", profit=-900.0, symbol="ETHUSD", magic=0, comment="")]
    ex = _ex(tmp_path, multi_broker(deals=deals))
    assert ex.decide_entry(entry("BUY"))["code"] == "PLACED"


# ---------------------------------------------------------------- 2 positions total across symbols incl. manual

@pytest.mark.parametrize(
    "positions",
    [
        [position("B", symbol="BTCUSD", magic=0, comment="", stop_loss=84100.0), position("E", symbol="ETHUSD", open_price=3000.0, stop_loss=3000.0)],  # manual BTC + auto ETH
        [position("E", symbol="ETHUSD", open_price=3000.0, stop_loss=3000.0), position("S", symbol="SOLUSD", open_price=150.0, stop_loss=150.0)],  # auto ETH + auto SOL
        [position("E1", symbol="ETHUSD", magic=0, comment="", open_price=3000.0, stop_loss=3000.0), position("E2", symbol="ETHUSD", magic=0, comment="", open_price=3000.0, stop_loss=3000.0)],  # two manual ETH
    ],
)
def test_third_position_rejected_across_symbols(tmp_path, positions):
    ex = _ex(tmp_path, multi_broker(positions=positions))
    for body in (entry("BUY"), eth_entry(), sol_entry()):
        d = ex.decide_entry(body)
        assert d["code"] == "MAX_POSITIONS", d
        assert d["guards"]["total_open"] == 2
    assert ex.broker.trade_calls == []


def test_positions_on_any_symbol_count_by_default(tmp_path):
    # 19:07 ET #5: account-wide; gold/index positions from other engines count
    positions = [position("X", symbol="XAUUSD", magic=0, comment="", stop_loss=None), position("U", symbol="US100.cash", magic=777, comment="GRIFF", stop_loss=None)]
    ex = _ex(tmp_path, multi_broker(positions=positions))
    d = ex.decide_entry(eth_entry())
    assert d["code"] == "MAX_POSITIONS" and d["guards"]["total_open"] == 2


def test_scope_is_account_wide_even_with_an_allowlist(tmp_path):
    positions = [position("X", symbol="XAUUSD", magic=0, comment="", open_price=4400.0, stop_loss=4300.0)]
    ex = _ex(tmp_path, multi_broker(positions=positions), env={"AUTOEXEC_SECOND_POSITION_SCOPE": "all"})
    d = ex.decide_entry(eth_entry())
    assert d["code"] == "SECOND_SL_NOT_BREAKEVEN" and d["guards"]["total_open"] == 1
    # the XAUUSD spec was fetched to value that position (same fake spec here)
    assert ex.broker.read_calls.count("symbol_specification") >= 2
    # an allowlist restricts what can be TRADED, never what is COUNTED (Odin 19:07 ET)
    ex2 = _ex(tmp_path / "b", multi_broker(positions=positions), env={"AUTOEXEC_SECOND_POSITION_SCOPE": "allowed", "AUTOEXEC_SYMBOLS": "BTCUSD,ETHUSD,SOLUSD"})
    d2 = ex2.decide_entry(eth_entry())
    assert d2["code"] == "SECOND_SL_NOT_BREAKEVEN" and d2["guards"]["total_open"] == 1


# ---------------------------------------------------------------- cross-symbol second-position conditions

def test_second_entry_requires_breakeven_on_every_symbol_including_manual(tmp_path):
    # manual ETH long with SL below entry blocks a BTC second entry
    ex = _ex(tmp_path, multi_broker(positions=[position("E", symbol="ETHUSD", magic=0, comment="", open_price=3000.0, stop_loss=2990.0, take_profit=3300.0)]))
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "SECOND_SL_NOT_BREAKEVEN", d
    bad = d["detail"]["second_position"]["existing"][0]
    assert bad["symbol"] == "ETHUSD" and bad["breakeven_or_better"] is False
    # short SOL with SL above entry blocks too
    ex2 = _ex(tmp_path / "b", multi_broker(positions=[position("S", symbol="SOLUSD", side="SELL", open_price=150.0, stop_loss=151.0, take_profit=120.0)]))
    assert ex2.decide_entry(eth_entry())["code"] == "SECOND_SL_NOT_BREAKEVEN"
    # missing SL on any symbol fails
    ex3 = _ex(tmp_path / "c", multi_broker(positions=[position("E", symbol="ETHUSD", stop_loss=None)]))
    assert ex3.decide_entry(entry("BUY"))["code"] == "SECOND_SL_NOT_BREAKEVEN"


def test_second_entry_on_other_symbol_allowed_when_all_conditions_hold(tmp_path):
    # BTC auto long at breakeven+, in profit; ETH second entry with R:R 2.5 after costs
    ex = _ex(tmp_path, multi_broker(positions=[position("B", symbol="BTCUSD", open_price=84000.0, stop_loss=84100.0, profit=300.0)]))
    d = ex.decide_entry(eth_entry("BUY", stop=2900, target=3300))
    assert d["code"] == "PLACED", d
    sp = d["second_position"]
    assert sp["passed"] and sp["symbol"] == "ETHUSD"
    assert sp["existing"][0]["symbol"] == "BTCUSD" and sp["existing"][0]["risk_at_sl_usd"] == 0.0
    assert sp["combined_open_risk_usd"] == pytest.approx(d["risk_usd"]) and sp["combined_open_risk_usd"] <= 250
    # reward (3300-3001.5) - 1.5 - 2.2 = 294.8 ; risk 105.2 -> 2.80
    assert sp["reward_risk"] == pytest.approx(294.8 / 105.2)
    assert sp["margin"]["method"] == "metaapi.calculate-margin"


def test_combined_risk_values_each_symbol_with_its_own_spec(tmp_path):
    from decimal import Decimal

    from autoexec import second_position as second

    # ETH position valued at $10/unit: 0.5 lots, 2 units below entry -> risk 10 (not at breakeven -> would be rejected anyway)
    r = second.existing_position_risk(position("E", symbol="ETHUSD", volume=0.5, open_price=3000.0, stop_loss=2998.0), Decimal("10"))
    assert r.symbol == "ETHUSD" and r.risk_at_sl_usd == Decimal("10.0")


def test_averaging_down_is_same_symbol_same_side_only(tmp_path):
    # BTC long in floating loss but at breakeven stop: blocks a second BTC long, not an ETH long
    pos = [position("B", symbol="BTCUSD", open_price=84000.0, stop_loss=84000.0, profit=-15.0)]
    ex = _ex(tmp_path, multi_broker(positions=pos))
    assert ex.decide_entry(entry("BUY"))["code"] == "SECOND_AVERAGING_DOWN"
    d = ex.decide_entry(eth_entry("BUY"))
    assert d["code"] == "PLACED", d
    # ETH long in loss blocks ETH long
    ex2 = _ex(tmp_path / "b", multi_broker(positions=[position("E", symbol="ETHUSD", open_price=3000.0, stop_loss=3000.0, profit=-3.0)]))
    assert ex2.decide_entry(eth_entry("BUY"))["code"] == "SECOND_AVERAGING_DOWN"
    assert ex2.decide_entry(eth_entry("SELL", stop=3100, target=2700))["code"] == "PLACED"


def test_shared_daily_room_and_equity_buffer_apply_across_symbols(tmp_path):
    deals = [deal("s", time="2026-10-10T08:00:00Z", profit=-350.0, symbol="SOLUSD")]  # room 150 shared
    ex = _ex(tmp_path, multi_broker(deals=deals, positions=[position("B", symbol="BTCUSD", open_price=84000.0, stop_loss=84100.0, profit=0.0, commission=0.0)]))
    d = ex.decide_entry(eth_entry())  # risk ~241.96 > room 150
    assert d["code"] == "SECOND_DAILY_ROOM" and d["detail"]["second_position"]["daily_cap_room_usd"] == 150.0
    b = multi_broker(account=dict(ACCOUNT, equity=90990.0), positions=[position("B", symbol="BTCUSD", open_price=84000.0, stop_loss=84100.0)])
    ex2 = _ex(tmp_path / "b", b)
    assert ex2.decide_entry(eth_entry())["code"] == "SECOND_EQUITY_BUFFER"


def _no_calc(positions):
    b = multi_broker(positions=positions)
    b.calc_margin_supported = False  # exercise the per-symbol calibration fallbacks
    return b


def test_margin_calibration_is_per_symbol(tmp_path):
    pos = [position("B", symbol="BTCUSD", open_price=84000.0, stop_loss=84100.0)]
    # only the BTC (legacy) leverage is set -> ETH entry cannot estimate margin -> skip (margin cap, 19:07 ET #3)
    ex = make_executor(tmp_path, _no_calc(pos), env={"AUTOEXEC_ORDERS_ENABLED": "1", "AUTOEXEC_SYMBOL_LEVERAGE": "2", **ETH_COMM})
    d = ex.decide_entry(eth_entry())
    assert d["code"] == "MARGIN_UNKNOWN", d
    ex2 = make_executor(tmp_path / "b", _no_calc(pos), env={"AUTOEXEC_ORDERS_ENABLED": "1", "AUTOEXEC_SYMBOL_LEVERAGE_ETHUSD": "2", **ETH_COMM})
    d2 = ex2.decide_entry(eth_entry())
    assert d2["code"] == "PLACED" and d2["second_position"]["margin"]["new_margin_usd"] == pytest.approx(2.3 * 3001.5 / 2)
    ex3 = make_executor(tmp_path / "c", _no_calc(pos), env={"AUTOEXEC_ORDERS_ENABLED": "1", "AUTOEXEC_MARGIN_PER_LOT_USD_ETHUSD": "1500", **ETH_COMM})
    assert ex3.decide_entry(eth_entry())["second_position"]["margin"]["method"].startswith("override")


# ---------------------------------------------------------------- tighten on any allowed symbol

def test_tighten_eth_by_symbol_and_by_position_id(tmp_path):
    pos = [position("E", symbol="ETHUSD", open_price=3000.0, stop_loss=2950.0, take_profit=3300.0)]
    ex = _ex(tmp_path, multi_broker(positions=pos))
    assert ex.tighten_stop({"stop": 2960})["code"] == "NO_AUTO_POSITION"  # defaults to BTCUSD
    d = ex.tighten_stop({"symbol": "ETHUSD", "stop": 2960})
    assert d["code"] == "MODIFIED" and d["symbol"] == "ETHUSD" and d["position"]["symbol"] == "ETHUSD"
    assert ex.broker.trade_calls[-1] == {"actionType": "POSITION_MODIFY", "positionId": "E", "stopLoss": 2960.0, "takeProfit": 3300.0}
    d2 = ex.tighten_stop({"position_id": "E", "stop": 2970})  # no symbol, found across allowed symbols
    assert d2["code"] == "MODIFIED" and d2["symbol"] == "ETHUSD"
    assert ex.tighten_stop({"symbol": "ETHUSD", "stop": 2940})["code"] == "SL_NOT_TIGHTER"
    assert ex.tighten_stop({"symbol": "ETHUSD", "stop": 3000.5})["code"] == "SL_WRONG_SIDE"  # above ETH bid 3000
    assert ex.tighten_stop({"symbol": "DOGEUSD", "stop": 1})["code"] == "SYMBOL_NOT_LISTED"


def test_tighten_without_symbol_targets_btc_even_when_eth_auto_exists(tmp_path):
    pos = [position("B", symbol="BTCUSD", stop_loss=83500.0), position("E", symbol="ETHUSD", open_price=3000.0, stop_loss=2950.0, take_profit=3300.0)]
    ex = _ex(tmp_path, multi_broker(positions=pos))
    d = ex.tighten_stop({"stop": 83800})
    assert d["code"] == "MODIFIED" and d["position"]["id"] == "B"


def test_tighten_position_id_on_any_symbol_unless_denied(tmp_path):
    pos = [position("X", symbol="XAUUSD", open_price=4000.0, stop_loss=3950.0, take_profit=4200.0)]
    b = multi_broker(positions=pos)
    b.set_symbol("XAUUSD", spec=SPEC, quote={"bid": 4100.0, "ask": 4100.5})
    ex = _ex(tmp_path, b)
    d = ex.tighten_stop({"position_id": "X", "stop": 3960})
    assert d["code"] == "MODIFIED" and d["symbol"] == "XAUUSD"
    ex2 = _ex(tmp_path / "b", b, env={"AUTOEXEC_SYMBOLS": "BTCUSD,ETHUSD"})
    assert ex2.tighten_stop({"position_id": "X", "stop": 3960})["code"] == "POSITION_NOT_FOUND"


# ---------------------------------------------------------------- dry-run, logging, caches, status

def test_dry_run_eth_and_sol_send_nothing(tmp_path):
    ex = _ex(tmp_path, enabled=False)
    for body in (eth_entry(), sol_entry("SELL", stop=160, target=120)):
        d = ex.decide_entry(body)
        assert d["code"] == "DRY_RUN_WOULD_PLACE" and d["sent"] is False and d["order"]["symbol"] == body["symbol"]
    t = ex.tighten_stop({"symbol": "ETHUSD", "stop": 2960})
    assert t["code"] == "NO_AUTO_POSITION"
    assert ex.broker.trade_calls == []


def test_symbol_logged_on_every_decision(tmp_path):
    ex = _ex(tmp_path)
    ex.decide_entry(eth_entry())
    ex.decide_entry(entry("BUY"))
    ex.decide_entry(entry("BUY", symbol="NOPE"))
    ex.decide_entry(sol_entry(entry_type="LIMIT"))
    ex.tighten_stop({"symbol": "SOLUSD", "stop": 1})
    recs = [r for r in ex.log.records if r["event"] == "decision"]
    assert [r["symbol"] for r in recs] == ["ETHUSD", "BTCUSD", "NOPE", "SOLUSD", "SOLUSD"]
    assert all("symbol" in r for r in recs)


def test_spec_cache_is_per_symbol(tmp_path):
    ex = _ex(tmp_path, enabled=False)
    ex.decide_entry(eth_entry())
    ex.decide_entry(eth_entry())
    ex.decide_entry(entry("BUY"))
    ex.decide_entry(sol_entry("SELL", stop=160, target=120))
    assert ex.broker.read_calls.count("symbol_specification") == 3  # one per symbol
    assert ex.broker.read_calls.count("current_price") == 4  # quotes always fresh
    ex.clock["mono"] += 1801
    ex.decide_entry(eth_entry())
    assert ex.broker.read_calls.count("symbol_specification") == 4


def test_status_reports_every_symbol(tmp_path):
    ex = _ex(tmp_path, env={"AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_SOLUSD": "", "AUTOEXEC_STATUS_SYMBOLS": "ETHUSD,SOLUSD"})
    s = ex.status()
    per = s["guards"]["per_symbol"]
    assert list(per) == ["BTCUSD", "ETHUSD", "SOLUSD"]
    assert per["ETHUSD"]["quote"]["spread"] == 1.5 and per["ETHUSD"]["spec"]["volume_step"] == 0.1
    assert per["ETHUSD"]["description"] == "Ethereum vs US Dollar"
    assert per["SOLUSD"]["commission"]["source"] == "none"
    assert per["BTCUSD"]["commission"]["per_lot_roundtrip"] == 27.0
    assert s["guards"]["active_symbols"] == ["BTCUSD", "ETHUSD", "SOLUSD"]


def test_http_and_cli_accept_symbol(tmp_path, monkeypatch, capsys):
    broker = multi_broker()
    ex = _ex(tmp_path, broker, enabled=False)
    server = make_server(ex, host="127.0.0.1", port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/setup"
        req = urllib.request.Request(url, data=json.dumps({"symbol": "ETHUSD", "side": "BUY", "entry_type": "MARKET", "stop": 2900, "target": 3300}).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
        assert body["ok"] and body["symbol"] == "ETHUSD" and body["order"]["symbol"] == "ETHUSD" and body["lots"] == 2.3
    finally:
        server.shutdown()
        server.server_close()
    from autoexec import cli

    monkeypatch.setenv("AUTOEXEC_STATE_DIR", str(tmp_path / "cli"))
    monkeypatch.setenv("AUTOEXEC_TOKEN", "SECRET-TOKEN-123")
    for k, v in {**ETH_COMM, **SOL_COMM}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(cli, "MetaApiRest", lambda *a, **k: broker)
    rc = cli.main(["setup", "--symbol", "solusd", "--side", "sell", "--stop", "160", "--target", "120"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["symbol"] == "SOLUSD" and out["lots"] == 23.0 and out["sent"] is False
    rc = cli.main(["tighten", "--symbol", "ETHUSD", "--stop", "2960"])
    assert rc == 2 and json.loads(capsys.readouterr().out)["code"] == "NO_AUTO_POSITION"
    assert broker.trade_calls == []


# ---------------------------------------------------------------- BTC regression: identical when no symbol is given

def test_btc_regression_decision_identical_without_symbol_field(tmp_path):
    before = make_executor(tmp_path / "a", FakeBroker(), env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    after = _ex(tmp_path / "b", FakeBroker())
    d0 = before.decide_entry(entry("BUY"))
    d1 = after.decide_entry(entry("BUY"))
    for key in ("code", "lots", "risk_usd", "per_lot_loss", "spread", "commission_per_lot_roundtrip", "commission_source", "stop_distance", "order", "sizing", "reward_risk"):
        assert d0[key] == d1[key], key
    assert d1["symbol"] == "BTCUSD"
    assert before.broker.trade_calls == after.broker.trade_calls


def test_btc_regression_second_position_and_tighten(tmp_path):
    pos = [position("B", symbol="BTCUSD", open_price=84000.0, stop_loss=84100.0, profit=300.0)]
    ex = _ex(tmp_path, FakeBroker(positions=pos))
    d = ex.decide_entry(entry("BUY", stop=84500, target=86500))
    assert d["code"] == "PLACED" and d["second_position"]["passed"] and d["lots"] == 0.44
    assert ex.tighten_stop({"stop": 84500})["code"] == "MODIFIED"
    assert ex.tighten_stop({"stop": 84050})["code"] == "SL_NOT_TIGHTER"  # below the position's current 84100
