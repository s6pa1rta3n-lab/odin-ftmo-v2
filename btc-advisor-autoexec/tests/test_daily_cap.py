"""Mechanic #5: $500 daily cap on the auto-trader's own trades, closed + floating, Prague day reset incl. DST."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from autoexec.trading_day import day_start_utc, day_window_utc, trading_day
from conftest import FakeBroker, MAGIC, deal, entry, make_executor, position

PRAGUE = ZoneInfo("Europe/Prague")


def _ex(tmp_path, broker, now):
    return make_executor(tmp_path, broker, now=now, env={"AUTOEXEC_ORDERS_ENABLED": "1"})


# ---------------------------------------------------------------- Prague day math

def test_day_window_in_cest():
    # 2026-10-10 10:00Z is 12:00 CEST; the Prague day started at 2026-10-09 22:00Z
    start, end = day_window_utc(datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc))
    assert start == datetime(2026, 10, 9, 22, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 10, 10, 22, 0, tzinfo=timezone.utc)


def test_day_window_in_cet_after_dst_ends():
    # DST ends 2026-10-25 01:00Z. On Oct 27 the Prague day starts at 23:00Z the day before.
    start, end = day_window_utc(datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc))
    assert start == datetime(2026, 10, 26, 23, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 10, 27, 23, 0, tzinfo=timezone.utc)


def test_dst_transition_day_is_25_hours():
    start = day_start_utc(date(2026, 10, 25))
    end = day_start_utc(date(2026, 10, 26))
    assert start == datetime(2026, 10, 24, 22, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 10, 25, 23, 0, tzinfo=timezone.utc)
    assert (end - start).total_seconds() == 25 * 3600


def test_trading_day_rolls_at_prague_midnight_not_utc():
    assert trading_day(datetime(2026, 10, 10, 21, 59, tzinfo=timezone.utc)) == date(2026, 10, 10)
    assert trading_day(datetime(2026, 10, 10, 22, 0, tzinfo=timezone.utc)) == date(2026, 10, 11)
    # after DST ends the boundary is 23:00Z
    assert trading_day(datetime(2026, 10, 27, 22, 30, tzinfo=timezone.utc)) == date(2026, 10, 27)
    assert trading_day(datetime(2026, 10, 27, 23, 0, tzinfo=timezone.utc)) == date(2026, 10, 28)


# ---------------------------------------------------------------- cap evaluation

def test_closed_pnl_includes_commission_and_swap(tmp_path):
    # profit -470, commission -20, swap -15 -> -505 <= -500
    broker = FakeBroker(deals=[deal("d1", time="2026-10-10T08:00:00Z", profit=-470.0, commission=-20.0, swap=-15.0)])
    ex = _ex(tmp_path, broker, datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc))
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "DAILY_CAP_HIT", d
    assert d["detail"]["pnl"]["closed"] == -505.0
    assert broker.trade_calls == []
    # latched for today
    assert ex.state.daily_cap_hit_day() == "2026-10-10"


def test_floating_pnl_counts_toward_cap(tmp_path):
    # closed -300, floating on the open auto position -190 profit -10 commission -> -500
    broker = FakeBroker(
        deals=[deal("d1", time="2026-10-10T08:00:00Z", profit=-300.0)],
        positions=[position(profit=-190.0, commission=-10.0, stop_loss=84000.0)],
    )
    ex = _ex(tmp_path, broker, datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc))
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "DAILY_CAP_HIT"
    assert d["detail"]["pnl"]["floating"] == -200.0
    assert d["detail"]["pnl"]["total"] == -500.0


def test_just_inside_cap_allows_entry(tmp_path):
    broker = FakeBroker(deals=[deal("d1", time="2026-10-10T08:00:00Z", profit=-499.99)])
    ex = _ex(tmp_path, broker, datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc))
    assert ex.decide_entry(entry("BUY"))["code"] == "PLACED"


def test_only_auto_magic_trades_count(tmp_path):
    broker = FakeBroker(
        deals=[
            deal("m1", time="2026-10-10T08:00:00Z", profit=-900.0, magic=0, comment=""),  # manual
            deal("g1", time="2026-10-10T08:10:00Z", profit=-900.0, magic=777, comment="GRIFF_X"),  # other engine
            deal("x1", time="2026-10-10T08:20:00Z", profit=-900.0, symbol="XAUUSD", magic=MAGIC),  # auto magic, other symbol: counted (by magic)
            deal("a1", time="2026-10-10T08:30:00Z", profit=-100.0),  # auto
        ],
        positions=[position(pid="M1", magic=0, comment="", profit=-800.0, stop_loss=84100.0)],  # manual floating loss ignored
    )
    ex = _ex(tmp_path, broker, datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc))
    d = ex.decide_entry(entry("BUY"))
    # auto-magic deals: -900 (x1) + -100 (a1) = -1000 -> cap hit; manual/other ignored
    assert d["code"] == "DAILY_CAP_HIT"
    assert d["detail"]["pnl"]["closed"] == -1000.0
    assert d["detail"]["pnl"]["floating"] == 0.0


def test_balance_deals_are_ignored(tmp_path):
    broker = FakeBroker(deals=[deal("b1", time="2026-10-10T08:00:00Z", profit=-5000.0, dtype="DEAL_TYPE_BALANCE", magic=MAGIC)])
    ex = _ex(tmp_path, broker, datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc))
    assert ex.decide_entry(entry("BUY"))["code"] == "PLACED"


def test_deals_before_prague_midnight_do_not_count(tmp_path):
    # 21:30Z on Oct 9 is 23:30 CEST Oct 9 -> previous Prague day
    broker = FakeBroker(deals=[deal("d1", time="2026-10-09T21:30:00Z", profit=-600.0)])
    ex = _ex(tmp_path, broker, datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc))
    assert ex.decide_entry(entry("BUY"))["code"] == "PLACED"
    start, _ = broker.history_windows[0]
    assert start == datetime(2026, 10, 9, 22, 0, tzinfo=timezone.utc)


def test_cap_latches_for_the_day_even_if_floating_recovers(tmp_path):
    broker = FakeBroker(positions=[position(profit=-520.0, stop_loss=84100.0)])
    ex = _ex(tmp_path, broker, datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc))
    assert ex.decide_entry(entry("BUY"))["code"] == "DAILY_CAP_HIT"
    broker.positions_list = []  # position closed in profit later, deals not in history for this fake
    broker.deals = []
    assert ex.decide_entry(entry("BUY"))["code"] == "DAILY_CAP_LATCHED"
    assert broker.trade_calls == []


def test_cap_latch_survives_restart(tmp_path):
    broker = FakeBroker(deals=[deal("d1", time="2026-10-10T08:00:00Z", profit=-600.0)])
    ex = _ex(tmp_path, broker, datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc))
    assert ex.decide_entry(entry("BUY"))["code"] == "DAILY_CAP_HIT"
    broker.deals = []
    ex2 = _ex(tmp_path, broker, datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc))  # same state dir
    assert ex2.decide_entry(entry("BUY"))["code"] == "DAILY_CAP_LATCHED"


def test_cap_resets_at_prague_midnight(tmp_path):
    broker = FakeBroker(deals=[deal("d1", time="2026-10-10T08:00:00Z", profit=-600.0)])
    ex = _ex(tmp_path, broker, datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc))
    assert ex.decide_entry(entry("BUY"))["code"] == "DAILY_CAP_HIT"
    ex.clock["now"] = datetime(2026, 10, 10, 21, 59, tzinfo=timezone.utc)  # still Oct 10 in Prague (23:59 CEST)
    assert ex.decide_entry(entry("BUY"))["code"] == "DAILY_CAP_LATCHED"
    ex.clock["now"] = datetime(2026, 10, 10, 22, 0, tzinfo=timezone.utc)  # 00:00 CEST Oct 11
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "PLACED", d
    assert d["guards"]["trading_day"] == "2026-10-11"


def test_cap_reset_across_dst_end(tmp_path):
    # Sat 2026-10-24 (CEST) big loss; DST ends Sun 25 Oct 01:00Z. Mon 26 Oct starts at 23:00Z Sun.
    broker = FakeBroker(deals=[deal("d1", time="2026-10-25T20:00:00Z", profit=-600.0)])  # 21:00 CET Oct 25
    ex = _ex(tmp_path, broker, datetime(2026, 10, 25, 21, 0, tzinfo=timezone.utc))
    assert ex.decide_entry(entry("BUY"))["code"] == "DAILY_CAP_HIT"
    assert ex.state.daily_cap_hit_day() == "2026-10-25"
    ex.clock["now"] = datetime(2026, 10, 25, 22, 30, tzinfo=timezone.utc)  # 23:30 CET, still Oct 25 (would be Oct 26 under CEST)
    assert ex.decide_entry(entry("BUY"))["code"] == "DAILY_CAP_LATCHED"
    ex.clock["now"] = datetime(2026, 10, 25, 23, 0, tzinfo=timezone.utc)  # 00:00 CET Oct 26
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "PLACED", d
    assert d["guards"]["trading_day"] == "2026-10-26"
    # history_deals is called twice per decision: [today window, commission lookback]
    assert broker.history_windows[-2][0] == datetime(2026, 10, 25, 23, 0, tzinfo=timezone.utc)
