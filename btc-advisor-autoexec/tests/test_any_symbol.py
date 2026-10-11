"""Any-FTMO-symbol extension (Odin, 2026-10-10 19:07 ET).

Broker-validated symbols, strict specs, the margin cap on every entry, the percentage
commission model per asset class, account-wide position count / breakeven, /symbol.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from decimal import Decimal

import pytest

from autoexec.broker import BrokerError
from autoexec.config import Config
from autoexec.margin import apply_margin_cap
from autoexec.server import make_server
from autoexec.sizing import parse_spec
from autoexec.symbols import asset_class_from_spec
from conftest import ACCOUNT, QUOTE, SPEC, FakeBroker, entry, make_executor, position

CRYPTO_BTC = dict(SPEC, path="Crypto\\BTCUSD", description="Bitcoin vs US Dollar", profitCurrency="USD")
UNI_SPEC = dict(SPEC, path="Crypto\\UNIUSD", description="Uniswap vs US Dollar", volumeStep=1, minVolume=1, maxVolume=5000, profitCurrency="USD")
UNI_QUOTE = {"bid": 7.50, "ask": 7.53}
NDX_SPEC = dict(SPEC, path="Indices\\US100.cash", description="US Tech 100", volumeStep=0.1, minVolume=0.1, profitCurrency="USD")
NDX_QUOTE = {"bid": 24000.0, "ask": 24001.5}
XAU_SPEC = dict(SPEC, path="Metals\\XAUUSD", description="Gold vs US Dollar", contractSize=100, tickSize=0.01, tickValue=1, profitCurrency="USD")
XAU_QUOTE = {"bid": 4400.0, "ask": 4400.3}
EURUSD_SPEC = dict(SPEC, path="Forex\\Majors\\EURUSD", contractSize=100000, tickSize=0.00001, tickValue=1, profitCurrency="USD")
EURUSD_QUOTE = {"bid": 1.08000, "ask": 1.08010}


def any_broker(**kw) -> FakeBroker:
    b = FakeBroker(**kw)
    b.set_symbol("BTCUSD", spec=CRYPTO_BTC, quote=QUOTE)
    b.set_symbol("UNIUSD", spec=UNI_SPEC, quote=UNI_QUOTE)
    b.set_symbol("US100.cash", spec=NDX_SPEC, quote=NDX_QUOTE)
    b.set_symbol("XAUUSD", spec=XAU_SPEC, quote=XAU_QUOTE)
    b.set_symbol("EURUSD", spec=EURUSD_SPEC, quote=EURUSD_QUOTE)
    b.margin_leverage.update({"BTCUSD": 2, "UNIUSD": 2, "US100.cash": 50, "XAUUSD": 20, "EURUSD": 100})
    return b


def _ex(tmp_path, broker=None, *, enabled=True, env=None):
    e = {"AUTOEXEC_ORDERS_ENABLED": "1" if enabled else "0"}
    e.update(env or {})
    return make_executor(tmp_path, broker or any_broker(), env=e)


def uni(side="BUY", stop=7.0, target=9.0, **extra):
    return entry(side, stop=stop, target=target, **{"symbol": "UNIUSD", **extra})


def xau(side="BUY", stop=4350.0, target=4550.0, **extra):
    return entry(side, stop=stop, target=target, **{"symbol": "XAUUSD", **extra})


# ---------------------------------------------------------------- #4 percentage commission math

def test_pct_commission_is_two_sides_of_notional(tmp_path):
    ex = _ex(tmp_path)
    d = ex.decide_entry(entry("BUY"))  # BTCUSD, path Crypto -> pct model
    c = d["commission"]
    assert c["model"] == "pct" and c["source"] == "pct" and c["asset_class"] == "crypto"
    # Odin 19:30 ET: 0.065 % per ROUND TRIP = 0.0325 % per side (measured $54.31/lot RT on ~83.5k)
    assert c["pct_per_side"] == 0.0325 and c["notional_per_lot"] == 85020.0
    assert d["commission_per_lot_roundtrip"] == pytest.approx(2 * 0.000325 * 85020)  # 55.263
    # stop 520 + spread 20 + commission 55.263 = 595.263 -> floor(250/595.263 = 0.41998) = 0.41
    assert d["per_lot_loss"] == pytest.approx(595.263) and d["lots"] == 0.41
    assert d["code"] == "PLACED"


def test_pct_rate_configurable_globally_per_class_and_per_symbol(tmp_path):
    ex = _ex(tmp_path, enabled=False, env={"AUTOEXEC_COMMISSION_PCT_PER_SIDE": "0.065"})
    assert ex.decide_entry(entry("BUY"))["commission_per_lot_roundtrip"] == pytest.approx(2 * 0.00065 * 85020)  # 110.526 if per-side were 0.065
    ex2 = _ex(tmp_path / "b", enabled=False, env={"AUTOEXEC_COMMISSION_PCT_PER_SIDE_CRYPTO": "0.05"})
    assert ex2.decide_entry(entry("BUY"))["commission"]["pct_per_side"] == 0.05
    ex3 = _ex(tmp_path / "c", enabled=False, env={"AUTOEXEC_COMMISSION_PCT_PER_SIDE_CRYPTO": "0.05", "AUTOEXEC_COMMISSION_PCT_PER_SIDE_BTCUSD": "0.01"})
    assert ex3.decide_entry(entry("BUY"))["commission"]["pct_per_side"] == 0.01
    assert ex3.decide_entry(uni())["commission"]["pct_per_side"] == 0.05


def test_broker_or_deals_commission_preferred_over_the_model(tmp_path):
    from conftest import deal

    deals = [
        deal("i", time="2026-10-01T10:00:00Z", profit=0, commission=-27.0, entry_type="DEAL_ENTRY_IN", volume=1.0, position_id="A", dtype="DEAL_TYPE_BUY"),
        deal("o", time="2026-10-01T12:00:00Z", profit=5, commission=-27.31, entry_type="DEAL_ENTRY_OUT", volume=1.0, position_id="A"),
    ]
    ex = _ex(tmp_path, any_broker(deals=deals), enabled=False)
    d = ex.decide_entry(entry("BUY"))
    assert d["commission_source"] == "deals" and d["commission_per_lot_roundtrip"] == pytest.approx(54.31)
    assert d["commission"]["model"] == "pct"  # the model is reported even when not used


# ---------------------------------------------------------------- #4 per-asset model and skip

def test_index_and_forex_use_confirmed_defaults_unknown_group_skips(tmp_path):
    # Confirmed defaults (FTMO updates Jul–Sep 2025 + symbols page 2026-10-08 + measured deals):
    # index flat 0, forex flat 5.02. An unknown group still has no default.
    ex = _ex(tmp_path, enabled=False)
    d = ex.decide_entry(entry("BUY", symbol="US100.cash", stop=23800, target=24500))
    assert d["code"] == "DRY_RUN_WOULD_PLACE" and d["commission"]["asset_class"] == "index" and d["commission_per_lot_roundtrip"] == 0.0
    d = ex.decide_entry(entry("BUY", symbol="EURUSD", stop=1.0750, target=1.0900))
    assert d["code"] == "DRY_RUN_WOULD_PLACE" and d["commission"]["asset_class"] == "forex" and d["commission_per_lot_roundtrip"] == 5.02
    b = any_broker()
    b.set_symbol("XYZ", spec=dict(SPEC, path="Weird Group\\XYZ", profitCurrency="USD"), quote={"bid": 10.0, "ask": 10.01})
    ex2 = _ex(tmp_path / "b", b)
    d = ex2.decide_entry(entry("BUY", symbol="XYZ", stop=9.0, target=12.0))
    assert d["code"] == "COMMISSION_UNAVAILABLE" and d["commission"]["model"] is None and d["commission"]["asset_class"] is None
    assert "AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_XYZ" in d["reason"]
    assert ex2.broker.trade_calls == []


def test_metals_flat_per_symbol_value(tmp_path):
    ex = _ex(tmp_path, env={"AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_XAUUSD": "7"})
    d = ex.decide_entry(xau())
    assert d["code"] == "PLACED", d
    c = d["commission"]
    assert c["model"] == "flat" and c["source"] == "env" and c["per_lot_roundtrip"] == 7.0 and c["asset_class"] == "metals"
    # XAUUSD: $100 per unit per lot; stop 4400.3-4350 = 50.3 -> 5030 + spread 30 + 7 = 5067 -> 0.04 lots
    assert d["per_lot_loss"] == pytest.approx(5067.0) and d["lots"] == 0.04


def test_class_level_model_enables_pct_for_indices(tmp_path):
    ex = _ex(tmp_path, env={"AUTOEXEC_COMMISSION_MODEL_INDEX": "pct", "AUTOEXEC_COMMISSION_PCT_PER_SIDE_INDEX": "0.01"})
    d = ex.decide_entry(entry("BUY", symbol="US100.cash", stop=23800, target=24500))
    assert d["code"] == "PLACED" and d["commission"]["model"] == "pct"
    assert d["commission_per_lot_roundtrip"] == pytest.approx(2 * 0.0001 * 24001.5)


def test_per_symbol_model_override_and_asset_class_override(tmp_path):
    ex = _ex(tmp_path, env={"AUTOEXEC_COMMISSION_MODEL_BTCUSD": "flat"})
    d = ex.decide_entry(entry("BUY"))
    assert d["commission"]["model"] == "flat" and d["commission_per_lot_roundtrip"] == 27.0 and d["lots"] == 0.44
    b = any_broker()
    b.set_symbol("US100.cash", spec=dict(NDX_SPEC, path=None), quote=NDX_QUOTE)  # broker gives no path
    ex2 = _ex(tmp_path / "b", b, env={"AUTOEXEC_ASSET_CLASS_US100_CASH": "crypto"})  # operator classifies explicitly
    d2 = ex2.decide_entry(entry("BUY", symbol="US100.cash", stop=23800, target=24500))
    assert d2["commission"]["asset_class"] == "crypto" and d2["commission"]["model"] == "pct" and d2["code"] == "PLACED"


def test_pct_model_refuses_foreign_quote_currency(tmp_path):
    b = any_broker()
    b.set_symbol("EURJPY", spec=dict(EURUSD_SPEC, path="Forex\\EURJPY", profitCurrency="JPY"), quote={"bid": 162.0, "ask": 162.015})
    ex = _ex(tmp_path, b, env={"AUTOEXEC_COMMISSION_MODEL_EURJPY": "pct"})
    d = ex.decide_entry(entry("BUY", symbol="EURJPY", stop=161.0, target=165.0))
    assert d["code"] == "COMMISSION_UNAVAILABLE" and "JPY" in d["reason"]


def test_asset_class_from_path_keywords():
    assert asset_class_from_spec({"path": "Crypto\\BTCUSD"}) == "crypto"
    assert asset_class_from_spec({"path": "Forex\\Majors\\EURUSD"}) == "forex"
    assert asset_class_from_spec({"path": "Indices\\US100.cash"}) == "index"
    assert asset_class_from_spec({"path": "Metals\\XAUUSD"}) == "metals"
    assert asset_class_from_spec({"path": "Stocks\\AAPL"}) == "equity"
    assert asset_class_from_spec({"path": "Energies\\USOIL"}) is None  # unknown group (name exceptions handled in asset_class)
    assert asset_class_from_spec({}) is None and asset_class_from_spec(None) is None


def test_config_rejects_bad_model_and_class():
    with pytest.raises(ValueError):
        Config.from_env({"AUTOEXEC_COMMISSION_MODEL_XAUUSD": "guess"})
    with pytest.raises(ValueError):
        Config.from_env({"AUTOEXEC_ASSET_CLASS_XAUUSD": "stocks"})


# ---------------------------------------------------------------- #3 margin cap on first entries

def test_margin_cap_shrinks_first_entry_lots(tmp_path):
    # equity 95000, existing margin 40000 -> new margin allowed = 47500 - 40000 = 7500 -> BTC per lot 42510 -> 0.17 lots
    b = any_broker(account=dict(ACCOUNT, margin=40000.0))
    ex = _ex(tmp_path, b)
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "PLACED", d
    assert d["margin"]["method"] == "metaapi.calculate-margin"
    assert d["margin"]["per_lot"]["per_lot_usd"] == pytest.approx(42510.0)
    cap = d["margin"]["cap"]
    assert cap["capped"] is True and cap["lots_before"] == 0.41 and cap["lots_after"] == 0.17
    assert d["lots"] == 0.17 and d["risk_usd"] == pytest.approx(0.17 * 595.263)
    assert d["margin"]["projected_level_pct"] >= 200 and cap["projected_level_pct"] == pytest.approx(95000 / (40000 + 0.17 * 42510) * 100)
    assert b.trade_calls[0]["volume"] == 0.17
    assert b.calc_margin_calls[0] == {"symbol": "BTCUSD", "type": "ORDER_TYPE_BUY", "volume": 0.41, "openPrice": 85020.0}


def test_margin_cap_skips_when_min_lot_breaks_200(tmp_path):
    b = any_broker(account=dict(ACCOUNT, margin=47400.0))  # only $100 of new margin allowed; min lot needs 425.1
    ex = _ex(tmp_path, b)
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "MARGIN_CAP_SKIP" and d["accepted"] is False
    assert "minimum volume" in d["reason"]
    assert d["detail"]["margin"]["cap"]["ok"] is False
    assert b.trade_calls == []


def test_margin_cap_exact_boundary_is_allowed(tmp_path):
    # account margin 0; max new margin = 47500 -> 1.11 lots at 42510; sizing gives 0.41 so no cap
    ex = _ex(tmp_path)
    d = ex.decide_entry(entry("BUY"))
    assert d["margin"]["cap"]["capped"] is False and d["margin"]["cap"]["max_lots"] == 1.11


def test_margin_unknown_skips_first_entry(tmp_path):
    b = any_broker()
    b.calc_margin_supported = False
    ex = _ex(tmp_path, b)
    d = ex.decide_entry(uni())  # no calibration for UNIUSD
    assert d["code"] == "MARGIN_UNKNOWN" and d["margin"]["per_lot"]["method"] == "unavailable"
    assert any("calculate-margin" in t for t in d["margin"]["per_lot"]["detail"]["tried"])
    assert b.trade_calls == []
    ex2 = _ex(tmp_path / "b", b, env={"AUTOEXEC_SYMBOL_LEVERAGE_UNIUSD": "2"})
    d2 = ex2.decide_entry(uni())
    assert d2["code"] == "PLACED" and d2["margin"]["method"] == "notional / AUTOEXEC_SYMBOL_LEVERAGE"


def test_margin_calc_retries_429_then_succeeds(tmp_path):
    b = any_broker()
    b.fail_next("calculate_margin", BrokerError("HTTP 429", status=429, retry_after=0.5))
    ex = _ex(tmp_path, b)
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "PLACED" and d["margin"]["method"] == "metaapi.calculate-margin"
    assert ex.sleeps == [0.5]


def test_margin_estimate_logged_on_every_decision(tmp_path):
    ex = _ex(tmp_path, enabled=False)
    ex.decide_entry(entry("BUY"))
    ex.decide_entry(uni())
    recs = [r for r in ex.log.records if r["event"] == "decision"]
    assert all("margin" in r and r["margin"]["method"] and "cap" in r["margin"] for r in recs)


def test_apply_margin_cap_math():
    spec = parse_spec(SPEC)
    cap = apply_margin_cap(lots=Decimal("0.44"), per_lot_usd=Decimal("42510"), method="x", equity=Decimal("95000"), account_margin=Decimal("30000"), min_level_pct=Decimal("200"), spec=spec)
    assert cap.capped and cap.lots_after == Decimal("0.41") and cap.projected_level_pct >= 200
    cap2 = apply_margin_cap(lots=Decimal("0.44"), per_lot_usd=Decimal("42510"), method="x", equity=Decimal("95000"), account_margin=Decimal("47500"), min_level_pct=Decimal("200"), spec=spec)
    assert cap2.ok is False and cap2.lots_after == 0


# ---------------------------------------------------------------- #1 any symbol, broker-validated

def test_any_listed_symbol_accepted_with_canonical_name(tmp_path):
    ex = _ex(tmp_path)
    d = ex.decide_entry(uni(symbol="uniusd"))
    assert d["code"] == "PLACED" and d["symbol"] == "UNIUSD" and d["order"]["symbol"] == "UNIUSD"
    # UNI: fill 7.53, stop 7.0 -> 0.53 + 0.03 + 2*0.000325*7.53 = 0.5648945 -> floor(250/0.5648945, 1) = 442 lots
    assert d["lots"] == 442.0 and d["risk_usd"] <= 250


def test_symbol_not_listed_rejected(tmp_path):
    ex = _ex(tmp_path)
    d = ex.decide_entry(entry("BUY", symbol="DOGEUSD"))
    assert d["code"] == "SYMBOL_NOT_LISTED" and "symbol_specification" not in ex.broker.read_calls


def test_spec_incomplete_rejected(tmp_path):
    b = any_broker()
    b.set_symbol("BADSPEC", spec={"symbol": "BADSPEC", "path": "Crypto\\X", "contractSize": 1}, quote={"bid": 1, "ask": 1.01})
    ex = _ex(tmp_path, b)
    d = ex.decide_entry(entry("BUY", symbol="BADSPEC", stop=0.9, target=1.5))
    assert d["code"] == "SPEC_INCOMPLETE" and set(d["detail"]["missing"]) == {"tickSize", "minVolume", "volumeStep"}
    assert b.trade_calls == []
    # tick value missing everywhere and the symbol not quoted in the account currency -> fail closed with a clear code
    b.set_symbol("NOVALUE", spec=dict(SPEC, tickValue=None, lossTickValue=None, profitTickValue=None, profitCurrency="EUR"), quote=dict(QUOTE))
    ex.invalidate_caches()  # the broker's symbol list is cached for the spec TTL
    d2 = ex.decide_entry(entry("BUY", symbol="NOVALUE"))
    assert d2["code"] == "TICK_VALUE_UNAVAILABLE" and "EUR" in d2["reason"]


def test_spec_read_failure_after_retries_rejected(tmp_path):
    b = any_broker()
    b.fail_next("symbol_specification", *(BrokerError("HTTP 503", status=503) for _ in range(5)))
    ex = _ex(tmp_path, b)
    d = ex.decide_entry(uni())
    assert d["code"] == "SPEC_UNAVAILABLE" and b.trade_calls == []


def test_symbol_list_unavailable_falls_back_to_spec_validation(tmp_path):
    b = any_broker()
    b.fail_reads.add("symbols")
    ex = _ex(tmp_path, b, enabled=False)
    d = ex.decide_entry(uni())
    assert d["code"] == "DRY_RUN_WOULD_PLACE"
    assert [r for r in ex.log.records if r["event"] == "symbol_list_unavailable"]
    b.unknown_symbols.add("DOGEUSD")  # the broker 404s its specification
    assert ex.decide_entry(entry("BUY", symbol="DOGEUSD"))["code"] == "SYMBOL_NOT_LISTED"


def test_symbol_list_cached(tmp_path):
    ex = _ex(tmp_path, enabled=False)
    ex.decide_entry(uni())
    ex.decide_entry(xau())
    ex.status()
    assert ex.broker.read_calls.count("symbols") == 1
    ex.clock["mono"] += 1801
    ex.decide_entry(uni())
    assert ex.broker.read_calls.count("symbols") == 2


def test_allowlist_and_denylist(tmp_path):
    ex = _ex(tmp_path, env={"AUTOEXEC_SYMBOLS_DENY": "XAUUSD"})
    assert ex.decide_entry(xau())["code"] == "SYMBOL_NOT_ALLOWED"
    assert ex.decide_entry(uni())["code"] == "PLACED"
    ex2 = _ex(tmp_path / "b", env={"AUTOEXEC_SYMBOLS": "BTCUSD,XAUUSD", "AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_XAUUSD": "7"})
    assert ex2.decide_entry(uni())["code"] == "SYMBOL_NOT_ALLOWED"
    assert ex2.decide_entry(xau())["code"] == "PLACED"
    with pytest.raises(ValueError):
        Config.from_env({"AUTOEXEC_SYMBOLS_DENY": "BTCUSD"})  # default symbol denied


def test_default_symbol_still_btcusd(tmp_path):
    ex = _ex(tmp_path)
    assert ex.decide_entry(entry("BUY"))["order"]["symbol"] == "BTCUSD"
    assert Config.from_env({}).symbol == "BTCUSD" and Config.from_env({}).symbols == ()


# ---------------------------------------------------------------- #5 account-wide count and breakeven

def test_two_positions_anywhere_block_a_third(tmp_path):
    pos = [position("G", symbol="XAUUSD", magic=4242, comment="GRIFF_GOLD", open_price=4300.0, stop_loss=4300.0), position("N", symbol="US100.cash", magic=0, comment="", open_price=23000.0, stop_loss=23000.0)]
    ex = _ex(tmp_path, any_broker(positions=pos))
    for body in (entry("BUY"), uni(), xau()):
        d = ex.decide_entry(body)
        assert d["code"] == "MAX_POSITIONS" and d["guards"]["total_open"] == 2 and d["guards"]["second_position_scope"] == "all"
    assert ex.broker.trade_calls == []


def test_breakeven_required_on_every_position_account_wide(tmp_path):
    # gold engine position below breakeven blocks a BTC second entry
    pos = [position("G", symbol="XAUUSD", magic=4242, comment="GRIFF_GOLD", open_price=4300.0, stop_loss=4290.0)]
    ex = _ex(tmp_path, any_broker(positions=pos))
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "SECOND_SL_NOT_BREAKEVEN" and d["detail"]["second_position"]["existing"][0]["symbol"] == "XAUUSD"
    # at breakeven on a foreign symbol -> allowed, valued with XAUUSD's own value per unit (100/unit)
    pos2 = [position("G", symbol="XAUUSD", magic=4242, comment="GRIFF_GOLD", open_price=4300.0, stop_loss=4300.0, profit=50.0)]
    ex2 = _ex(tmp_path / "b", any_broker(positions=pos2))
    d2 = ex2.decide_entry(entry("BUY"))
    assert d2["code"] == "PLACED", d2
    assert d2["second_position"]["existing"][0]["risk_at_sl_usd"] == 0.0 and d2["second_position"]["passed"]
    # unknown-spec foreign symbol cannot be valued -> reject
    pos3 = [position("Z", symbol="ZZZ", magic=0, comment="", open_price=10.0, stop_loss=10.0)]
    b3 = any_broker(positions=pos3)
    b3.unknown_symbols.add("ZZZ")
    d3 = _ex(tmp_path / "c", b3).decide_entry(entry("BUY"))
    assert d3["code"] in ("READ_FAILED", "SECOND_SPEC_UNAVAILABLE")


def test_scope_opt_out_is_ignored_account_wide_always(tmp_path):
    # Odin 2026-10-10 19:07 ET: account-wide. A stale AUTOEXEC_SECOND_POSITION_SCOPE=allowed drop-in must not narrow it.
    pos = [position("G", symbol="XAUUSD", magic=4242, comment="GRIFF_GOLD", open_price=4300.0, stop_loss=4290.0)]
    ex = _ex(tmp_path, any_broker(positions=pos), env={"AUTOEXEC_SECOND_POSITION_SCOPE": "allowed", "AUTOEXEC_SYMBOLS": "BTCUSD,UNIUSD"})
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "SECOND_SL_NOT_BREAKEVEN" and d["guards"]["second_position_scope"] == "all"
    assert d["guards"]["second_position_scope_requested"] == "allowed"
    assert [r for r in ex.log.records if r["event"] == "scope_override_ignored" and r["alert"] is True]


# ---------------------------------------------------------------- #6 /symbol

@pytest.fixture
def server(tmp_path):
    b = any_broker(positions=[position("G", symbol="XAUUSD", magic=0, comment="", open_price=4300.0, stop_loss=4300.0)])
    ex = _ex(tmp_path, b, enabled=False, env={"AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_XAUUSD": "7"})
    srv = make_server(ex, host="127.0.0.1", port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield srv, ex, b
    finally:
        srv.shutdown()
        srv.server_close()


def _get(srv, path):
    url = f"http://127.0.0.1:{srv.server_address[1]}{path}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


def test_symbol_endpoint_single(server):
    srv, ex, b = server
    status, body = _get(srv, "/symbol?symbol=XAUUSD&stop_distance=50")
    assert status == 200 and body["ok"] is True and body["code"] == "PASS"
    assert body["broker_symbol"] == "XAUUSD" and body["description"] == "Gold vs US Dollar" and body["path"] == "Metals\\XAUUSD"
    assert body["spec"]["contract_size"] == 100.0 and body["spec_missing"] == []
    assert body["quote"] == {"bid": 4400.0, "ask": 4400.3, "spread": pytest.approx(0.3), "spread_cost_per_lot_usd": pytest.approx(30.0)}
    c = body["commission"]
    assert c["model"] == "flat" and c["source"] == "env" and c["per_lot_roundtrip"] == 7.0
    assert body["margin"]["method"] == "metaapi.calculate-margin" and body["margin"]["per_lot_usd"] == pytest.approx(440030 / 20)
    s = body["sample"]
    assert s["stop_distance"] == 50.0 and s["sizing"]["per_lot_loss"] == pytest.approx(5037.0) and s["lots"] == 0.04
    assert s["margin_cap"]["projected_level_pct"] >= 200
    assert body["snapshot"]["cached"] is False
    assert b.trade_calls == []


def test_symbol_endpoint_list_fail_reasons_and_cache(server):
    srv, ex, b = server
    status, body = _get(srv, "/symbol?symbol=BTCUSD,US100.cash,NOPE")
    assert status == 200 and body["ok"] is False
    by = {r.get("symbol"): r for r in body["symbols"]}
    assert by["BTCUSD"]["ok"] and by["BTCUSD"]["commission"]["model"] == "pct"
    assert by["BTCUSD"]["sample"]["stop_pct_of_price"] == pytest.approx(1.0)  # default AUTOEXEC_SAMPLE_STOP_PCT
    assert by["US100.cash"]["ok"] is True and by["US100.cash"]["commission"]["per_lot_roundtrip"] == 0.0  # confirmed index default
    assert by["NOPE"]["ok"] is False and by["NOPE"]["code"] == "SYMBOL_NOT_LISTED"
    n = len(b.read_calls)
    status, again = _get(srv, "/symbol?symbol=BTCUSD")
    assert again["snapshot"]["cached"] is True and len(b.read_calls) == n
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(srv, "/symbol?symbol=BTCUSD&stop_distance=-1")
    assert exc.value.code == 400


def test_status_includes_symbol_views_for_active_symbols(server):
    srv, ex, b = server
    status, body = _get(srv, "/status")
    per = body["guards"]["per_symbol"]
    assert set(per) == {"BTCUSD", "XAUUSD"}  # default + open-position symbol
    assert per["XAUUSD"]["ok"] and per["BTCUSD"]["commission"]["model"] == "pct"
    assert body["guards"]["active_symbols"] == ["BTCUSD", "XAUUSD"]


def test_cli_symbol_command(tmp_path, monkeypatch, capsys):
    from autoexec import cli

    b = any_broker()
    monkeypatch.setenv("AUTOEXEC_STATE_DIR", str(tmp_path / "cli"))
    monkeypatch.setenv("AUTOEXEC_TOKEN", "SECRET-TOKEN-123")
    monkeypatch.setattr(cli, "MetaApiRest", lambda *a, **k: b)
    b.set_symbol("XYZ", spec=dict(SPEC, path="Weird Group\\XYZ", profitCurrency="USD"), quote={"bid": 10.0, "ask": 10.01})
    rc = cli.main(["symbol", "UNIUSD", "XYZ", "--stop-distance", "0.5"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2 and out["ok"] is False
    assert out["symbols"][0]["ok"] and out["symbols"][0]["sample"]["stop_distance"] == 0.5
    assert out["symbols"][1]["reason"].startswith("COMMISSION_UNAVAILABLE")
    assert b.trade_calls == []


# ---------------------------------------------------------------- dry-run and regression

def test_dry_run_new_symbol_sends_nothing(tmp_path):
    ex = _ex(tmp_path, enabled=False, env={"AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP_XAUUSD": "7"})
    for body in (uni(), xau()):
        d = ex.decide_entry(body)
        assert d["code"] == "DRY_RUN_WOULD_PLACE" and d["sent"] is False and d["order"]["symbol"] == body["symbol"]
    assert ex.broker.trade_calls == [] and ex.broker.calc_margin_calls  # margin was still computed


def test_btc_regression_without_asset_class_is_identical(tmp_path):
    # Broker gives no path -> no asset class -> legacy flat $27 model -> same 0.44 lots as #84/#85/#86.
    ex = _ex(tmp_path, FakeBroker())
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "PLACED" and d["lots"] == 0.44 and d["per_lot_loss"] == 567.0
    assert d["commission"]["model"] == "flat" and d["commission_source"] == "env"
    assert d["margin"]["cap"]["capped"] is False


def test_btc_intended_difference_with_crypto_path(tmp_path):
    # Documented change (Odin 19:30 ET): Crypto path -> pct model at 0.0325 %/side x 2 = $55.26 at 85,020
    # (measured $54.31 on ~83.5k) -> per-lot loss 595.26 -> 0.41 lots (about 0.42) instead of 0.44.
    ex = _ex(tmp_path)
    d = ex.decide_entry(entry("BUY"))
    assert d["lots"] == 0.41 and d["commission_per_lot_roundtrip"] == pytest.approx(55.263)
    assert d["commission"]["pct_per_side"] == 0.0325
    assert d["order"]["stopLoss"] == 84500.0 and d["order"]["takeProfit"] == 86500.0 and d["order"]["magic"] == 20261010


def test_symbol_logged_and_state_file_unchanged(tmp_path):
    ex = _ex(tmp_path)
    ex.decide_entry(uni())
    recs = [r for r in ex.log.records if r["event"] == "decision"]
    assert recs[-1]["symbol"] == "UNIUSD" and recs[-1]["margin"]["method"]
    state = json.loads((tmp_path / "state" / "state.json").read_text())
    assert set(state) == {"last_place_attempt"}
