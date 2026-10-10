"""Mechanic #4: stops may only tighten; removing SL/TP is rejected."""

from __future__ import annotations

import pytest

from conftest import entry, make_executor, position

LONG = dict(pid="P1", side="BUY", open_price=84000.0, stop_loss=83500.0, take_profit=86000.0)
SHORT = dict(pid="S1", side="SELL", open_price=86000.0, stop_loss=86500.0, take_profit=83000.0)


def _ex(tmp_path, broker, positions, enabled=True):
    broker.positions_list = positions
    return make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1" if enabled else "0"})


def test_tighten_long_accepted_and_preserves_tp(tmp_path, broker):
    ex = _ex(tmp_path, broker, [position(**LONG)])
    d = ex.tighten_stop({"stop": 83800})
    assert d["accepted"] and d["code"] == "MODIFIED", d
    sent = broker.trade_calls[0]
    assert sent == {"actionType": "POSITION_MODIFY", "positionId": "P1", "stopLoss": 83800.0, "takeProfit": 86000.0}
    assert d["previous_stop"] == 83500.0


def test_tighten_long_above_entry_locks_profit(tmp_path, broker):
    ex = _ex(tmp_path, broker, [position(**LONG)])
    d = ex.tighten_stop({"stop": 84600})  # above open 84000, below bid 85000
    assert d["code"] == "MODIFIED"


def test_widen_long_rejected(tmp_path, broker):
    ex = _ex(tmp_path, broker, [position(**LONG)])
    d = ex.tighten_stop({"stop": 83000})
    assert d["accepted"] is False and d["code"] == "SL_NOT_TIGHTER"
    assert broker.trade_calls == []


def test_same_stop_is_not_tighter(tmp_path, broker):
    ex = _ex(tmp_path, broker, [position(**LONG)])
    assert ex.tighten_stop({"stop": 83500})["code"] == "SL_NOT_TIGHTER"


def test_tighten_short_accepted_and_widen_rejected(tmp_path, broker):
    ex = _ex(tmp_path, broker, [position(**SHORT)])
    assert ex.tighten_stop({"stop": 86700})["code"] == "SL_NOT_TIGHTER"
    d = ex.tighten_stop({"stop": 86200})
    assert d["code"] == "MODIFIED"
    assert broker.trade_calls[-1]["stopLoss"] == 86200.0 and broker.trade_calls[-1]["takeProfit"] == 83000.0


@pytest.mark.parametrize("stop", [0, "0", None, ""])
def test_removing_sl_rejected(tmp_path, broker, stop):
    ex = _ex(tmp_path, broker, [position(**LONG)])
    d = ex.tighten_stop({"stop": stop})
    assert d["code"] == "SL_REMOVED"
    assert broker.trade_calls == []


def test_position_without_tp_refuses_modify(tmp_path, broker):
    ex = _ex(tmp_path, broker, [position(**dict(LONG, take_profit=None))])
    d = ex.tighten_stop({"stop": 83800})
    assert d["code"] == "TP_MISSING_ON_POSITION"
    assert broker.trade_calls == []


def test_tp_change_not_supported(tmp_path, broker):
    ex = _ex(tmp_path, broker, [position(**LONG)])
    assert ex.tighten_stop({"stop": 83800, "target": 0})["code"] == "TP_CHANGE_NOT_SUPPORTED"
    assert ex.tighten_stop({"stop": 83800, "tp": 87000})["code"] == "TP_CHANGE_NOT_SUPPORTED"


def test_stop_through_market_rejected(tmp_path, broker):
    ex = _ex(tmp_path, broker, [position(**LONG)])
    assert ex.tighten_stop({"stop": 85000})["code"] == "SL_WRONG_SIDE"  # at bid
    ex2 = _ex(tmp_path / "s", broker, [position(**SHORT)])
    assert ex2.tighten_stop({"stop": 85020})["code"] == "SL_WRONG_SIDE"  # at ask


def test_no_auto_position(tmp_path, broker):
    ex = _ex(tmp_path, broker, [])
    assert ex.tighten_stop({"stop": 83800})["code"] == "NO_AUTO_POSITION"


def test_manual_position_is_not_tightened(tmp_path, broker):
    ex = _ex(tmp_path, broker, [position(**dict(LONG, magic=0, comment=""))])
    d = ex.tighten_stop({"stop": 83800})
    assert d["code"] == "NO_AUTO_POSITION"
    assert broker.trade_calls == []


def test_two_auto_positions_need_position_id(tmp_path, broker):
    ex = _ex(tmp_path, broker, [position(**LONG), position(**dict(LONG, pid="P2"))])
    assert ex.tighten_stop({"stop": 83800})["code"] == "AMBIGUOUS_POSITION"
    d = ex.tighten_stop({"stop": 83800, "position_id": "P2"})
    assert d["code"] == "MODIFIED" and broker.trade_calls[-1]["positionId"] == "P2"
    assert ex.tighten_stop({"stop": 83800, "position_id": "nope"})["code"] == "POSITION_NOT_FOUND"


def test_dry_run_tighten_sends_nothing(tmp_path, broker):
    ex = _ex(tmp_path, broker, [position(**LONG)], enabled=False)
    d = ex.tighten_stop({"stop": 83800})
    assert d["accepted"] and d["code"] == "DRY_RUN_WOULD_MODIFY" and d["sent"] is False
    assert d["order"]["stopLoss"] == 83800.0 and d["order"]["takeProfit"] == 86000.0
    assert broker.trade_calls == []


def test_tighten_allowed_while_halted_or_capped(tmp_path, broker):
    # Tightening reduces risk; the halt/cap block entries, not stop tightening.
    ex = _ex(tmp_path, broker, [position(**LONG)])
    ex.halt.latch(equity=90000, threshold=90750, reason="test")
    ex.state.latch_daily_cap("2026-10-10", -600.0)
    assert ex.decide_entry(entry("BUY"))["code"] == "EQUITY_HALT_LATCHED"
    assert ex.tighten_stop({"stop": 83800})["code"] == "MODIFIED"


def test_tighten_read_failure_fails_closed(tmp_path, broker):
    ex = _ex(tmp_path, broker, [position(**LONG)])
    broker.fail_reads.add("positions")
    assert ex.tighten_stop({"stop": 83800})["code"] == "READ_FAILED"
    assert broker.trade_calls == []
