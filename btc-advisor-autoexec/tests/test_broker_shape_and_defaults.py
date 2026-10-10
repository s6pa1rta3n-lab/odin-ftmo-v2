"""Fixes after Trading Ops' read-only preflight at b54c805 (2026-10-10) and the FTMO symbols-page addendum.

1. Tick values come from the current-price quote on this account (spec tickValue is null).
2. Asset-class map: 'Crypto II CFD', 'Cash CFD', name exceptions (oil, NATGAS, DXY, .c).
3. Env names with dots (AUTOEXEC_..._US100.cash) and a flat 0 counts as set.
4. Confirmed per-asset commission defaults (FTMO updates Jul–Sep 2025 + symbols page 2026-10-08 + measured deals).
5. Preflight on real-shaped fixtures passes for BTCUSD, UNIUSD, US100.cash, XAUUSD, EURUSD.
"""

from __future__ import annotations

import json
import os
import runpy
import sys

import pytest

from autoexec.config import CLASS_COMMISSION_DEFAULTS, Config
from autoexec.symbols import asset_class, asset_class_from_spec, normalize_symbol
from conftest import ACCOUNT, FakeBroker, entry, make_executor, position

# ---- fixtures shaped like the real broker: tick values null in the spec, present in the quote

def real_spec(symbol, path, **kw):
    base = {
        "symbol": symbol,
        "path": path,
        "description": kw.pop("description", symbol),
        "contractSize": 1,
        "tickSize": 0.01,
        "tickValue": None,
        "lossTickValue": None,
        "profitTickValue": None,
        "minVolume": 0.01,
        "volumeStep": 0.01,
        "maxVolume": 50,
        "digits": 2,
        "profitCurrency": "USD",
        "marginCurrency": "USD",
        "initialMargin": 0,
    }
    base.update(kw)
    return base


def real_quote(bid, ask, loss_tick, profit_tick=None):
    return {"bid": bid, "ask": ask, "lossTickValue": loss_tick, "profitTickValue": profit_tick if profit_tick is not None else loss_tick}


def real_broker(**kw) -> FakeBroker:
    b = FakeBroker(account=dict(ACCOUNT, currency="USD"), **kw)
    b.spec = real_spec("BTCUSD", "Crypto\\BTCUSD", description="Bitcoin vs US Dollar")
    b.quote = real_quote(85000.0, 85020.0, 0.01)
    b.set_symbol("BTCUSD", spec=b.spec, quote=b.quote)
    b.set_symbol("UNIUSD", spec=real_spec("UNIUSD", "Crypto II CFD\\UNIUSD", description="Uniswap vs US Dollar", minVolume=1, volumeStep=1, maxVolume=5000), quote=real_quote(7.50, 7.53, 0.01))
    b.set_symbol("US100.cash", spec=real_spec("US100.cash", "Cash CFD\\US100.cash", description="US Tech 100", minVolume=0.1, volumeStep=0.1), quote=real_quote(24000.0, 24001.5, 0.01))
    b.set_symbol("USOIL.cash", spec=real_spec("USOIL.cash", "Cash CFD\\USOIL.cash", description="WTI Crude Oil", minVolume=0.1, volumeStep=0.1), quote=real_quote(60.00, 60.04, 0.01))
    b.set_symbol("NATGAS.cash", spec=real_spec("NATGAS.cash", "Cash CFD\\NATGAS.cash", description="Natural Gas", tickSize=0.001, minVolume=0.1, volumeStep=0.1), quote=real_quote(3.000, 3.006, 0.001))
    b.set_symbol("XAUUSD", spec=real_spec("XAUUSD", "Metals CFD\\XAUUSD", description="Gold vs US Dollar", contractSize=100), quote=real_quote(4400.0, 4400.3, 1.0))
    b.set_symbol("EURUSD", spec=real_spec("EURUSD", "Forex\\Majors\\EURUSD", description="Euro vs US Dollar", contractSize=100000, tickSize=0.00001, digits=5), quote=real_quote(1.08000, 1.08010, 1.0))
    b.set_symbol("AAPL", spec=real_spec("AAPL", "Equities CFD\\US\\AAPL", description="Apple Inc", minVolume=1, volumeStep=1, maxVolume=10000), quote=real_quote(230.00, 230.05, 0.01))
    b.set_symbol("COCOA.c", spec=real_spec("COCOA.c", "Agricultural\\COCOA.c", description="Cocoa", minVolume=0.1, volumeStep=0.1), quote=real_quote(7000.0, 7003.0, 0.01))
    b.set_symbol("XYZ", spec=real_spec("XYZ", "Weird Group\\XYZ"), quote=real_quote(10.0, 10.01, 0.01))
    b.margin_leverage.update({"BTCUSD": 2, "UNIUSD": 2, "US100.cash": 50, "USOIL.cash": 50, "NATGAS.cash": 20, "XAUUSD": 20, "EURUSD": 100, "AAPL": 5, "COCOA.c": 20, "XYZ": 10})
    return b


def _ex(tmp_path, broker=None, *, enabled=False, env=None):
    e = {"AUTOEXEC_ORDERS_ENABLED": "1" if enabled else "0"}
    e.update(env or {})
    return make_executor(tmp_path, broker or real_broker(), env=e)


# ---------------------------------------------------------------- 1. tick value from the quote

def test_btcusd_passes_with_real_shape_spec_null_quote_loss_tick_value(tmp_path):
    ex = _ex(tmp_path, enabled=True)
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "PLACED", d
    assert d["value_source"] == "quote.lossTickValue/tickSize"
    assert d["sizing"]["value_per_unit_per_lot"] == 1.0
    # crypto pct 0.0325 %/side: 2 x 0.000325 x 85020 = 55.263 -> per-lot loss 595.263 -> 0.41 lots
    assert d["per_lot_loss"] == pytest.approx(595.263) and d["lots"] == 0.41


def test_loss_tick_value_preferred_over_profit_tick_value(tmp_path):
    b = real_broker()
    b.set_symbol("BTCUSD", spec=b.spec, quote=real_quote(85000.0, 85020.0, loss_tick=0.02, profit_tick=0.01))
    ex = _ex(tmp_path, b)
    d = ex.decide_entry(entry("BUY"))
    assert d["sizing"]["value_per_unit_per_lot"] == 2.0 and d["value_source"] == "quote.lossTickValue/tickSize"


def test_spec_tick_value_used_when_quote_has_none(tmp_path):
    b = real_broker()
    b.set_symbol("BTCUSD", spec=dict(b.spec, tickValue=0.03), quote={"bid": 85000.0, "ask": 85020.0})
    ex = _ex(tmp_path, b)
    d = ex.decide_entry(entry("BUY"))
    assert d["value_source"] == "spec.tickValue/tickSize" and d["sizing"]["value_per_unit_per_lot"] == 3.0


def test_contract_size_fallback_only_for_account_currency(tmp_path):
    b = real_broker()
    b.set_symbol("BTCUSD", spec=b.spec, quote={"bid": 85000.0, "ask": 85020.0})  # no tick value anywhere; USD-quoted
    ex = _ex(tmp_path, b)
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "DRY_RUN_WOULD_PLACE" and d["value_source"].startswith("contractSize x tickSize") and d["lots"] == 0.41
    b.set_symbol("EURJPY", spec=real_spec("EURJPY", "Forex\\Minors\\EURJPY", contractSize=100000, tickSize=0.001, profitCurrency="JPY"), quote={"bid": 162.0, "ask": 162.015})
    ex.invalidate_caches()
    d2 = ex.decide_entry(entry("BUY", symbol="EURJPY", stop=161.0, target=165.0))
    assert d2["code"] == "TICK_VALUE_UNAVAILABLE" and "JPY" in d2["reason"]
    assert ex.broker.trade_calls == []


def test_spec_completeness_no_longer_requires_tick_value(tmp_path):
    ex = _ex(tmp_path)
    s = ex.symbol_info("BTCUSD")
    assert s["ok"] and s["spec_missing"] == [] and s["spec"]["value_source"] == "quote.lossTickValue/tickSize"


def test_foreign_position_valued_with_quote_tick_value(tmp_path):
    # XAUUSD position from the gold engine at breakeven: valued with XAUUSD's quote lossTickValue (1.0 / 0.01 = $100/unit)
    pos = [position("G", symbol="XAUUSD", magic=4242, comment="GRIFF_GOLD", open_price=4300.0, stop_loss=4300.0, profit=20.0)]
    ex = _ex(tmp_path, real_broker(positions=pos), enabled=True)
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "PLACED" and d["second_position"]["existing"][0]["risk_at_sl_usd"] == 0.0
    assert "current_price" in ex.broker.read_calls


# ---------------------------------------------------------------- 2. asset-class map

@pytest.mark.parametrize(
    "symbol,path,expected,source",
    [
        ("BTCUSD", "Crypto\\BTCUSD", "crypto", "spec.path"),
        ("ETHUSD", "Crypto CFD\\ETHUSD", "crypto", "spec.path"),
        ("UNIUSD", "Crypto II CFD\\UNIUSD", "crypto", "spec.path"),
        ("US100.cash", "Cash CFD\\US100.cash", "index", "spec.path"),
        ("US30.cash", "cash cfd\\US30.cash", "index", "spec.path"),
        ("GER40.cash", "Indices\\GER40.cash", "index", "spec.path"),
        ("USOIL.cash", "Cash CFD\\USOIL.cash", "oil", "name"),
        ("UKOIL.cash", "Cash CFD\\UKOIL.cash", "oil", "name"),
        ("NATGAS.cash", "Cash CFD\\NATGAS.cash", "energy", "name"),
        ("HEATOIL.c", "Energies\\HEATOIL.c", "energy", "name"),
        ("DXY.cash", "Cash CFD\\DXY.cash", "dollar_index", "name"),
        ("COCOA.c", "Agricultural\\COCOA.c", "agri", "name"),
        ("CORN.c", "Whatever\\CORN.c", "agri", "name"),
        ("XAUUSD", "Metals CFD\\XAUUSD", "metals", "spec.path"),
        ("XAU/USD", "Metals CFD\\XAUUSD", "metals", "spec.path"),
        ("EURUSD", "Forex\\Majors\\EURUSD", "forex", "spec.path"),
        ("USDTRY", "Exotics\\USDTRY", "forex", "spec.path"),
        ("AAPL", "Equities CFD\\US\\AAPL", "equity", "spec.path"),
        ("XYZ", "Weird Group\\XYZ", None, "none"),
        ("XYZ", "", None, "none"),
    ],
)
def test_asset_class_map(symbol, path, expected, source):
    cls_name, src = asset_class(symbol, {"path": path}, None)
    assert (cls_name, src) == (expected, source)


def test_asset_class_override_and_slash_normalisation():
    assert asset_class("XYZ", {"path": "Weird\\XYZ"}, "equity") == ("equity", "env")
    assert normalize_symbol("xau/usd") == "XAUUSD" and normalize_symbol(None) == ""
    assert asset_class_from_spec({"path": "Crypto II CFD\\UNIUSD"}) == "crypto"


# ---------------------------------------------------------------- 3. env names with dots; zero flat is set

@pytest.mark.parametrize("key", ["AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_US100.cash", "AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_US100_CASH", "AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_us100.cash"])
def test_env_names_with_dots_and_case_are_normalised(key):
    c = Config.from_env({key: "1.25"})
    assert c.commission_flat_for("US100.cash", "index") == 1.25
    assert c.commission_model_for("US100.cash", "index") == "flat"


def test_flat_zero_counts_as_set_not_unavailable(tmp_path):
    b = real_broker()
    b.set_symbol("XYZ", spec=real_spec("XYZ", "Weird Group\\XYZ"), quote=real_quote(10.0, 10.01, 0.01))  # unknown group
    ex = _ex(tmp_path, b, enabled=True, env={"AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_XYZ": "0"})
    d = ex.decide_entry(entry("BUY", symbol="XYZ", stop=9.0, target=12.0))
    assert d["code"] == "PLACED", d
    assert d["commission"]["model"] == "flat" and d["commission"]["source"] == "env" and d["commission_per_lot_roundtrip"] == 0.0
    ex2 = _ex(tmp_path / "b", real_broker(), enabled=True)  # same symbol without the env -> skip
    assert ex2.decide_entry(entry("BUY", symbol="XYZ", stop=9.0, target=12.0))["code"] == "COMMISSION_UNAVAILABLE"


def test_margin_and_class_env_with_dots():
    c = Config.from_env({"AUTOEXEC_SYMBOL_LEVERAGE_US100.cash": "50", "AUTOEXEC_COMMISSION_PCT_PER_SIDE_Metals": "0.001", "AUTOEXEC_COMMISSION_MODEL_dollar_index": "flat"})
    assert c.symbol_leverage_for("US100.cash") == 50.0
    assert c.commission_pct_for("XAUUSD", "metals") == 0.001
    assert c.commission_model_for("DXY.cash", "dollar_index") == "flat"


# ---------------------------------------------------------------- 4. confirmed per-asset defaults

def test_class_defaults_table():
    assert CLASS_COMMISSION_DEFAULTS == {
        "crypto": ("pct", 0.0325),
        "forex": ("flat", 5.02),
        "metals": ("pct", 0.0007),
        "index": ("flat", 0.0),
        "oil": ("flat", 0.0),
        "equity": ("pct", 0.002),
        "energy": ("pct", 0.0007),
        "dollar_index": ("pct", 0.0007),
        "agri": ("flat", 0.0),
    }


def _decide(ex, symbol, side, stop, target):
    return ex.decide_entry(entry(side, symbol=symbol, stop=stop, target=target))


def test_forex_default_flat_5_02(tmp_path):
    d = _decide(_ex(tmp_path), "EURUSD", "BUY", 1.0750, 1.0900)
    assert d["code"] == "DRY_RUN_WOULD_PLACE", d
    c = d["commission"]
    assert c["asset_class"] == "forex" and c["model"] == "flat" and c["source"] == "env" and d["commission_per_lot_roundtrip"] == 5.02
    # EURUSD quote lossTickValue 1.0 / tickSize 0.00001 = $100,000 per 1.0 price unit per lot
    assert d["sizing"]["value_per_unit_per_lot"] == 100000.0
    # stop 1.0801-1.0750 = 0.0051 -> $510 + spread 0.0001 -> $10 + 5.02 = 525.02 -> 0.47 lots
    assert d["per_lot_loss"] == pytest.approx(525.02) and d["lots"] == 0.47


def test_index_default_flat_zero(tmp_path):
    d = _decide(_ex(tmp_path), "US100.cash", "BUY", 23800, 24500)
    assert d["code"] == "DRY_RUN_WOULD_PLACE"
    assert d["commission"]["asset_class"] == "index" and d["commission"]["model"] == "flat" and d["commission_per_lot_roundtrip"] == 0.0
    assert d["per_lot_loss"] == pytest.approx(201.5 + 1.5) and d["lots"] == 1.2


def test_metals_default_pct_0_0007(tmp_path):
    d = _decide(_ex(tmp_path), "XAUUSD", "BUY", 4350, 4550)
    assert d["code"] == "DRY_RUN_WOULD_PLACE", d
    c = d["commission"]
    assert c["asset_class"] == "metals" and c["model"] == "pct" and c["pct_per_side"] == 0.0007 and c["notional_per_lot"] == pytest.approx(440030.0)
    assert d["commission_per_lot_roundtrip"] == pytest.approx(2 * 0.000007 * 440030)  # 6.16


def test_oil_default_flat_zero(tmp_path):
    d = _decide(_ex(tmp_path), "USOIL.cash", "SELL", 61.0, 57.0)
    assert d["code"] == "DRY_RUN_WOULD_PLACE", d
    assert d["commission"]["asset_class"] == "oil" and d["commission"]["model"] == "flat" and d["commission_per_lot_roundtrip"] == 0.0


def test_natgas_default_pct_0_0007(tmp_path):
    d = _decide(_ex(tmp_path), "NATGAS.cash", "BUY", 2.9, 3.3)
    assert d["code"] == "DRY_RUN_WOULD_PLACE", d
    c = d["commission"]
    assert c["asset_class"] == "energy" and c["model"] == "pct" and c["pct_per_side"] == 0.0007
    assert d["commission_per_lot_roundtrip"] == pytest.approx(2 * 0.000007 * 3.006)


def test_stock_default_pct_0_002(tmp_path):
    d = _decide(_ex(tmp_path), "AAPL", "BUY", 225.0, 245.0)
    assert d["code"] == "DRY_RUN_WOULD_PLACE", d
    c = d["commission"]
    assert c["asset_class"] == "equity" and c["model"] == "pct" and c["pct_per_side"] == 0.002
    assert d["commission_per_lot_roundtrip"] == pytest.approx(2 * 0.00002 * 230.05)


def test_agri_default_flat_zero(tmp_path):
    d = _decide(_ex(tmp_path), "COCOA.c", "BUY", 6900.0, 7300.0)
    assert d["code"] == "DRY_RUN_WOULD_PLACE", d
    assert d["commission"]["asset_class"] == "agri" and d["commission_per_lot_roundtrip"] == 0.0


def test_unknown_group_has_no_default(tmp_path):
    d = _decide(_ex(tmp_path), "XYZ", "BUY", 9.0, 12.0)
    assert d["code"] == "COMMISSION_UNAVAILABLE" and d["commission"]["asset_class"] is None and d["commission"]["model"] is None


def test_deals_derived_still_beats_the_class_default(tmp_path):
    from conftest import deal

    deals = [
        deal("i", time="2026-10-01T10:00:00Z", profit=0, commission=-2.508, entry_type="DEAL_ENTRY_IN", volume=1.0, position_id="F", symbol="EURUSD", dtype="DEAL_TYPE_BUY"),
        deal("o", time="2026-10-01T12:00:00Z", profit=3, commission=-2.508, entry_type="DEAL_ENTRY_OUT", volume=1.0, position_id="F", symbol="EURUSD"),
    ]
    d = _decide(_ex(tmp_path, real_broker(deals=deals)), "EURUSD", "BUY", 1.0750, 1.0900)
    assert d["commission_source"] == "deals" and d["commission_per_lot_roundtrip"] == pytest.approx(5.016)


def test_class_env_overrides_the_default(tmp_path):
    d = _decide(_ex(tmp_path, env={"AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_FOREX": "6"}), "EURUSD", "BUY", 1.0750, 1.0900)
    assert d["commission_per_lot_roundtrip"] == 6.0
    d2 = _decide(_ex(tmp_path / "b", env={"AUTOEXEC_COMMISSION_MODEL_INDEX": "pct", "AUTOEXEC_COMMISSION_PCT_PER_SIDE_INDEX": "0.01"}), "US100.cash", "BUY", 23800, 24500)
    assert d2["commission"]["model"] == "pct" and d2["commission_per_lot_roundtrip"] == pytest.approx(2 * 0.0001 * 24001.5)


# ---------------------------------------------------------------- 5. preflight on real-shaped fixtures

def test_preflight_passes_for_the_five_symbols_on_real_shape(tmp_path, monkeypatch, capsys):
    import autoexec.broker as broker_mod

    b = real_broker()
    monkeypatch.setattr(broker_mod, "MetaApiRest", lambda *a, **k: b)
    monkeypatch.setenv("AUTOEXEC_TOKEN", "SECRET-TOKEN-123")
    monkeypatch.setenv("AUTOEXEC_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("AUTOEXEC_ORDERS_ENABLED", raising=False)
    script = os.path.join(os.path.dirname(__file__), "..", "scripts", "preflight.py")
    monkeypatch.setattr(sys, "argv", ["preflight.py", "--symbols", "BTCUSD,UNIUSD,US100.cash,XAUUSD,EURUSD", "--stop-pct", "1", "--json"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(script, run_name="__main__")
    assert exc.value.code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] and out["all_pass"] is True
    by = {v["symbol"]: v for v in out["symbols"]}
    assert set(by) == {"BTCUSD", "UNIUSD", "US100.cash", "XAUUSD", "EURUSD"}
    for v in by.values():
        assert v["ok"] and v["reason"].startswith("pass") and v["spec"]["value_source"] == "quote.lossTickValue/tickSize"
        assert v["margin"]["method"] == "metaapi.calculate-margin" and v["sample"]["lots"] > 0
    assert by["BTCUSD"]["commission"]["model"] == "pct" and by["BTCUSD"]["commission"]["pct_per_side"] == 0.0325
    assert by["UNIUSD"]["asset_class"]["value"] == "crypto"
    assert by["US100.cash"]["commission"]["per_lot_roundtrip"] == 0.0
    assert by["XAUUSD"]["commission"]["pct_per_side"] == 0.0007
    assert by["EURUSD"]["commission"]["per_lot_roundtrip"] == 5.02
    assert "SECRET-TOKEN-123" not in json.dumps(out)
    assert b.trade_calls == []
