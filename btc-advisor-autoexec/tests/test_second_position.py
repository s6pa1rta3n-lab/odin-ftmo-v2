"""Mechanic #3 as replaced on 2026-10-10 05:55 ET: max 2 BTC positions, second only under all conditions."""

from __future__ import annotations

from decimal import Decimal

import pytest

from autoexec import second_position as second
from autoexec.guards import DailyPnl
from conftest import ACCOUNT, MAGIC, SPEC, deal, entry, make_executor, position

# A good first position: long from 84000 with SL moved above entry (breakeven+), in profit.
GOOD_FIRST = dict(pid="P1", side="BUY", volume=0.4, open_price=84000.0, stop_loss=84100.0, take_profit=87000.0, profit=400.0)
# Account with the symbol leverage configured so the margin estimate is computable.
MARGIN_ENV = {"AUTOEXEC_SYMBOL_LEVERAGE": "2"}
# Second setup: BUY stop 84500 target 86500 -> risk/lot 567, reward/lot (86500-85020) - 20 - 27 = 1433 -> R:R 2.53
SECOND = dict(side="BUY", stop=84500.0, target=86500.0)


def _ex(tmp_path, broker, **env):
    e = {"AUTOEXEC_ORDERS_ENABLED": "1"}
    e.update(MARGIN_ENV)
    e.update(env)
    return make_executor(tmp_path, broker, env=e)


# ---------------------------------------------------------------- baseline / #5 count

def test_no_position_open_normal_single_entry(tmp_path, broker):
    ex = _ex(tmp_path, broker)
    d = ex.decide_entry(entry(**SECOND))
    assert d["code"] == "PLACED"
    assert "second_position" not in d


def test_second_position_allowed_when_all_conditions_hold(tmp_path, broker):
    broker.positions_list = [position(**GOOD_FIRST)]
    ex = _ex(tmp_path, broker)
    d = ex.decide_entry(entry(**SECOND))
    assert d["code"] == "PLACED", d
    sp = d["second_position"]
    assert sp["passed"] is True
    assert sp["existing"][0]["breakeven_or_better"] is True
    assert sp["existing"][0]["risk_at_sl_usd"] == 0.0
    assert sp["combined_open_risk_usd"] == pytest.approx(d["risk_usd"])
    assert sp["combined_open_risk_usd"] <= 250.0
    assert sp["reward_risk"] >= 2.0
    assert sp["margin"]["method"] == "metaapi.calculate-margin"  # broker-reported first (19:07 ET #3)
    assert sp["margin"]["projected_level_pct"] > 200
    assert sp["fresh_setup_verified"] is False
    assert len(broker.trade_calls) == 1


def test_manual_position_counts_toward_the_total_and_may_be_the_first(tmp_path, broker):
    broker.positions_list = [position(**dict(GOOD_FIRST, magic=0, comment=""))]
    ex = _ex(tmp_path, broker)
    d = ex.decide_entry(entry(**SECOND))
    assert d["code"] == "PLACED"
    assert d["guards"]["manual_open"] == 1 and d["guards"]["total_open"] == 1


@pytest.mark.parametrize(
    "positions",
    [
        [position(**GOOD_FIRST), position(**dict(GOOD_FIRST, pid="P2"))],  # two auto
        [position(**GOOD_FIRST), position(**dict(GOOD_FIRST, pid="M1", magic=0, comment=""))],  # auto + manual
        [position(**dict(GOOD_FIRST, pid="M1", magic=0, comment="")), position(**dict(GOOD_FIRST, pid="M2", magic=0, comment=""))],  # two manual
    ],
)
def test_third_position_rejected_max_two_total(tmp_path, broker, positions):
    broker.positions_list = positions
    ex = _ex(tmp_path, broker)
    d = ex.decide_entry(entry(**SECOND))
    assert d["code"] == "MAX_POSITIONS"
    assert broker.trade_calls == []


def test_other_symbol_positions_count_account_wide(tmp_path, broker):
    # Odin 19:07 ET #5: every open position on the account counts, whatever the symbol
    broker.positions_list = [position(pid="X1", symbol="XAUUSD", magic=0), position(pid="X2", symbol="US100.cash", magic=0)]
    ex = _ex(tmp_path, broker)
    assert ex.decide_entry(entry(**SECOND))["code"] == "MAX_POSITIONS"
    broker.positions_list = [position(pid="X1", symbol="XAUUSD", magic=0, open_price=4000.0, stop_loss=3990.0)]
    assert ex.decide_entry(entry(**SECOND))["code"] == "SECOND_SL_NOT_BREAKEVEN"


# ---------------------------------------------------------------- #1 breakeven + combined risk

@pytest.mark.parametrize(
    "first",
    [
        dict(GOOD_FIRST, stop_loss=83900.0),  # long with SL below entry
        dict(GOOD_FIRST, stop_loss=None),  # missing SL
        dict(GOOD_FIRST, stop_loss=0),  # zero SL == missing
        dict(GOOD_FIRST, side="SELL", open_price=86000.0, stop_loss=86100.0, take_profit=83000.0),  # short with SL above entry
        dict(GOOD_FIRST, magic=0, comment="", stop_loss=83999.99),  # manual, one cent below BE
    ],
)
def test_existing_position_not_at_breakeven_rejects_second(tmp_path, broker, first):
    broker.positions_list = [position(**first)]
    ex = _ex(tmp_path, broker)
    d = ex.decide_entry(entry(**SECOND))
    assert d["code"] == "SECOND_SL_NOT_BREAKEVEN", d
    assert broker.trade_calls == []
    assert d["detail"]["second_position"]["existing"][0]["breakeven_or_better"] is False


def test_breakeven_exactly_at_open_is_accepted():
    r = second.existing_position_risk(position(open_price=84000.0, stop_loss=84000.0), Decimal("1"))
    assert r.breakeven_or_better and r.risk_at_sl_usd == 0
    s = second.existing_position_risk(position(side="SELL", open_price=84000.0, stop_loss=84000.0), Decimal("1"))
    assert s.breakeven_or_better and s.risk_at_sl_usd == 0


def test_existing_risk_at_sl_math():
    r = second.existing_position_risk(position(side="BUY", volume=0.4, open_price=84000.0, stop_loss=83500.0), Decimal("1"))
    assert r.risk_at_sl_usd == Decimal("200.0")  # 500 * 1 * 0.4
    s = second.existing_position_risk(position(side="SELL", volume=0.2, open_price=84000.0, stop_loss=84300.0), Decimal("1"))
    assert s.risk_at_sl_usd == Decimal("60.0")


def test_combined_risk_over_250_rejected():
    existing = [second.existing_position_risk(position(open_price=84000.0, stop_loss=84000.0), Decimal("1"))]
    combined = second.combined_open_risk(existing, Decimal("249.48"))
    second.check_combined_risk(combined, max_risk_usd=Decimal("250"))
    with pytest.raises(Exception) as exc:
        second.check_combined_risk(Decimal("250.01"), max_risk_usd=Decimal("250"))
    assert exc.value.code == "SECOND_COMBINED_RISK"


# ---------------------------------------------------------------- #2 R:R and averaging down

def test_second_rejected_when_reward_risk_below_two(tmp_path, broker):
    broker.positions_list = [position(**GOOD_FIRST)]
    ex = _ex(tmp_path, broker)
    # reward/lot = (86000-85020) - 20 - 27 = 933; risk/lot 567 -> 1.65
    d = ex.decide_entry(entry("BUY", stop=84500, target=86000))
    assert d["code"] == "SECOND_RR_TOO_LOW", d
    assert d["reward_risk"] == pytest.approx(933 / 567)
    assert broker.trade_calls == []


def test_reward_risk_after_costs_boundary(tmp_path, broker):
    broker.positions_list = [position(**GOOD_FIRST)]
    ex = _ex(tmp_path, broker)
    # need reward/lot >= 1134 -> target - 85020 - 47 >= 1134 -> target >= 86201
    assert ex.decide_entry(entry("BUY", stop=84500, target=86200))["code"] == "SECOND_RR_TOO_LOW"
    assert ex.decide_entry(entry("BUY", stop=84500, target=86201))["code"] == "PLACED"


def test_first_entry_is_not_subject_to_the_rr_floor(tmp_path, broker):
    ex = _ex(tmp_path, broker)
    d = ex.decide_entry(entry("BUY", stop=84500, target=86000))
    assert d["code"] == "PLACED" and d["reward_risk"] < 2


def test_never_averaging_down_same_side_in_floating_loss(tmp_path, broker):
    # long at breakeven stop but currently under water -> reject a second long
    broker.positions_list = [position(**dict(GOOD_FIRST, profit=-12.5))]
    ex = _ex(tmp_path, broker)
    d = ex.decide_entry(entry(**SECOND))
    assert d["code"] == "SECOND_AVERAGING_DOWN"
    assert broker.trade_calls == []


def test_opposite_side_in_floating_loss_is_not_averaging_down(tmp_path, broker):
    broker.positions_list = [position(**dict(GOOD_FIRST, profit=-12.5))]
    ex = _ex(tmp_path, broker)
    # SELL: fill at bid 85000; stop 85600 -> 647/lot; reward (85000-83000) - 47 = 1953 -> 3.0
    d = ex.decide_entry(entry("SELL", stop=85600, target=83000))
    assert d["code"] == "PLACED", d


# ---------------------------------------------------------------- #3 daily room + equity buffer

def test_second_rejected_when_combined_risk_exceeds_daily_room(tmp_path, broker):
    broker.positions_list = [position(**dict(GOOD_FIRST, profit=0.0, commission=0.0))]
    # closed -300 today -> room 200 < new risk 249.48
    broker.deals = [deal("d1", time="2026-10-10T08:00:00Z", profit=-300.0)]
    ex = _ex(tmp_path, broker)
    d = ex.decide_entry(entry(**SECOND))
    assert d["code"] == "SECOND_DAILY_ROOM", d
    assert d["detail"]["second_position"]["daily_cap_room_usd"] == 200.0
    assert broker.trade_calls == []


def test_daily_room_counts_floating_loss(tmp_path, broker):
    # breakeven-or-better long that is nevertheless marked at -260 floating (e.g. spread spike) on the other side
    broker.positions_list = [position(**dict(GOOD_FIRST, side="SELL", open_price=86000.0, stop_loss=85900.0, take_profit=83000.0, profit=-260.0, commission=0.0))]
    ex = _ex(tmp_path, broker)
    d = ex.decide_entry(entry(**SECOND))  # BUY, so not averaging down
    assert d["code"] == "SECOND_DAILY_ROOM"


def test_second_rejected_when_equity_minus_combined_risk_hits_halt(tmp_path, broker):
    broker.positions_list = [position(**GOOD_FIRST)]
    broker.account = dict(ACCOUNT, equity=90999.0)  # above halt, but 90999 - 249.48 = 90749.52 <= 90750
    ex = _ex(tmp_path, broker)
    d = ex.decide_entry(entry(**SECOND))
    assert d["code"] == "SECOND_EQUITY_BUFFER", d
    assert broker.trade_calls == []
    broker.account = dict(ACCOUNT, equity=91000.0)  # 91000 - 249.48 = 90750.52 > 90750
    ex2 = _ex(tmp_path / "b", broker)
    assert ex2.decide_entry(entry(**SECOND))["code"] == "PLACED"


def test_daily_cap_room_helper():
    assert second.daily_cap_room(DailyPnl(Decimal("-100"), Decimal("-50"), 1, 1), cap_usd=Decimal("500")) == Decimal("350")
    assert second.daily_cap_room(DailyPnl(Decimal("120"), Decimal("30"), 1, 1), cap_usd=Decimal("500")) == Decimal("500")


# ---------------------------------------------------------------- #4 margin level

def test_margin_unknown_skips_second_entry(tmp_path, broker):
    broker.positions_list = [position(**GOOD_FIRST)]
    broker.calc_margin_supported = False  # broker cannot compute margin
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})  # no leverage/override configured
    d = ex.decide_entry(entry(**SECOND))
    # the account-wide margin cap (19:07 ET #3) rejects before the second-position check
    assert d["code"] == "MARGIN_UNKNOWN", d
    assert d["margin"]["per_lot"]["method"] == "unavailable"
    assert broker.trade_calls == []


def test_margin_level_below_200_is_capped_by_shrinking_lots(tmp_path, broker):
    # 19:07 ET #3: instead of rejecting, lots shrink until the projected level is >= 200 %.
    broker.positions_list = [position(**GOOD_FIRST)]
    # existing margin 30000; 0.44 lots would be 18704.4 -> 195 %; max new margin = 95000/2 - 30000 = 17500 -> 0.41 lots
    broker.account = dict(ACCOUNT, margin=30000.0)
    ex = _ex(tmp_path, broker)
    d = ex.decide_entry(entry(**SECOND))
    assert d["code"] == "PLACED", d
    assert d["lots"] == 0.41 and d["margin"]["cap"]["capped"] is True
    assert d["second_position"]["margin"]["projected_level_pct"] >= 200
    assert broker.trade_calls[0]["volume"] == 0.41


def test_margin_from_spec_initial_margin(tmp_path, broker):
    broker.positions_list = [position(**GOOD_FIRST)]
    broker.calc_margin_supported = False
    broker.spec = dict(SPEC, initialMargin=42510.0)  # per 1.0 lot
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    d = ex.decide_entry(entry(**SECOND))
    assert d["code"] == "PLACED", d
    m = d["second_position"]["margin"]
    assert m["method"] == "spec.initialMargin"
    assert m["new_margin_usd"] == pytest.approx(42510.0 * 0.44)


def test_margin_override_takes_priority(tmp_path, broker):
    broker.positions_list = [position(**GOOD_FIRST)]
    broker.calc_margin_supported = False
    broker.spec = dict(SPEC, initialMargin=42510.0)
    ex = _ex(tmp_path, broker, AUTOEXEC_MARGIN_PER_LOT_USD="100000")
    d = ex.decide_entry(entry(**SECOND))
    # 0.44 * 100000 = 44000 -> level 215.9% -> passes, and method is the override
    assert d["second_position"]["margin"]["method"].startswith("override")
    assert d["code"] == "PLACED"
    ex2 = _ex(tmp_path / "b", broker, AUTOEXEC_MARGIN_PER_LOT_USD="110000")  # 0.44 -> 48400 -> 196%: cap shrinks to 0.43 (47300 -> 200.8%)
    d2 = ex2.decide_entry(entry(**SECOND))
    assert d2["code"] == "PLACED" and d2["lots"] == 0.43 and d2["margin"]["cap"]["capped"] is True


def test_account_leverage_only_when_opted_in(tmp_path, broker):
    broker.positions_list = [position(**GOOD_FIRST)]
    broker.calc_margin_supported = False
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1", "AUTOEXEC_MARGIN_USE_ACCOUNT_LEVERAGE": "1"})
    d = ex.decide_entry(entry(**SECOND))
    assert d["code"] == "PLACED"
    assert "account.leverage" in d["second_position"]["margin"]["method"]


def test_margin_spec_in_other_currency_is_not_used():
    est = second.estimate_margin(
        lots=Decimal("0.5"),
        fill_price=Decimal("85020"),
        spec_raw=dict(SPEC, initialMargin=1000, marginCurrency="EUR"),
        spec=__import__("autoexec.sizing", fromlist=["parse_spec"]).parse_spec(SPEC),
        account=dict(ACCOUNT, currency="USD"),
        margin_per_lot_override=None,
        symbol_leverage=None,
        use_account_leverage=False,
    )
    assert est.new_margin_usd is None and est.method == "unavailable"


# ---------------------------------------------------------------- order of evaluation / logging

def test_second_position_values_logged_on_reject_and_accept(tmp_path, broker):
    broker.positions_list = [position(**GOOD_FIRST)]
    ex = _ex(tmp_path, broker)
    ex.decide_entry(entry("BUY", stop=84500, target=86000))  # R:R reject
    rec = [r for r in ex.log.records if r["event"] == "decision"][-1]
    assert rec["code"] == "SECOND_RR_TOO_LOW"
    assert rec["detail"]["second_position"]["existing"][0]["position_id"] == "P1"
    ex.decide_entry(entry(**SECOND))
    rec = [r for r in ex.log.records if r["event"] == "decision"][-1]
    assert rec["code"] == "PLACED" and rec["second_position"]["passed"] is True


def test_second_entry_still_sized_to_250_and_dry_run_sends_nothing(tmp_path, broker):
    broker.positions_list = [position(**GOOD_FIRST)]
    ex = make_executor(tmp_path, broker, env=MARGIN_ENV)  # orders disabled
    d = ex.decide_entry(entry(**SECOND))
    assert d["code"] == "DRY_RUN_WOULD_PLACE" and d["lots"] == 0.44 and d["risk_usd"] <= 250
    assert broker.trade_calls == []
