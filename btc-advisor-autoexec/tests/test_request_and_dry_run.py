"""Mechanic #1 (MARKET only, SL+TP required), arming, dry-run sends nothing, kill switch, fail-closed reads."""

from __future__ import annotations

import json

import pytest

from autoexec.broker import BrokerError
from conftest import make_executor, entry


@pytest.mark.parametrize("entry_type", ["LIMIT", "STOP", "STOP_LIMIT", "market_limit", "", None, "PENDING"])
def test_non_market_entry_rejected(executor, broker, entry_type):
    d = executor.decide_entry(entry("BUY", entry_type=entry_type))
    assert d["accepted"] is False
    assert d["code"] == "ENTRY_TYPE_NOT_MARKET"
    assert broker.trade_calls == []
    # rejected before any live read
    assert broker.read_calls == []


def test_market_is_case_insensitive(executor):
    assert executor.decide_entry(entry("BUY", entry_type="market"))["accepted"]


@pytest.mark.parametrize("missing", ["stop", "target"])
def test_missing_sl_or_tp_rejected(executor, broker, missing):
    body = entry("BUY")
    body.pop(missing)
    d = executor.decide_entry(body)
    assert d["accepted"] is False
    assert d["code"] == ("MISSING_SL" if missing == "stop" else "MISSING_TP")
    assert broker.trade_calls == []


@pytest.mark.parametrize("value", [0, "0", None, ""])
def test_zero_or_null_sl_tp_rejected(executor, value):
    assert executor.decide_entry(entry("BUY", stop=value))["code"] == "MISSING_SL"
    assert executor.decide_entry(entry("BUY", target=value))["code"] == "MISSING_TP"


def test_bad_side_rejected(executor):
    d = executor.decide_entry(entry("LONG"))
    assert d["code"] == "BAD_SIDE"


def test_sl_tp_on_wrong_side_rejected(executor):
    assert executor.decide_entry(entry("BUY", stop=85010, target=86500))["code"] == "SL_WRONG_SIDE"  # stop above bid
    assert executor.decide_entry(entry("BUY", stop=84500, target=85010))["code"] == "TP_WRONG_SIDE"  # target below ask
    assert executor.decide_entry(entry("SELL", stop=85010, target=84000))["code"] == "SL_WRONG_SIDE"  # stop below ask
    assert executor.decide_entry(entry("SELL", stop=85600, target=85005))["code"] == "TP_WRONG_SIDE"  # target above bid


def test_order_payload_always_has_sl_and_tp_and_identity(executor):
    d = executor.decide_entry(entry("BUY", stop=84500, target=86500))
    o = d["order"]
    assert o["actionType"] == "ORDER_TYPE_BUY"
    assert o["symbol"] == "BTCUSD"
    assert o["stopLoss"] == 84500.0 and o["takeProfit"] == 86500.0
    assert o["comment"] == "BTC_ADVISOR_AUTO"
    assert o["magic"] == 20261010
    assert o["volume"] == d["lots"]


# ---------------------------------------------------------------- dry-run / arming

def test_orders_disabled_by_default_dry_run_sends_nothing(tmp_path, broker):
    ex = make_executor(tmp_path, broker)
    assert ex.cfg.orders_enabled is False
    assert ex.armed is False
    d = ex.decide_entry(entry("BUY"))
    assert d["accepted"] is True
    assert d["mode"] == "dry_run"
    assert d["sent"] is False
    assert d["code"] == "DRY_RUN_WOULD_PLACE"
    assert d["order"]["volume"] == 0.44
    assert broker.trade_calls == []
    # every guard ran against live reads
    assert {"account_information", "positions", "current_price", "symbol_specification", "history_deals"} <= set(broker.read_calls)
    # would-be order is in the log
    log_lines = [json.loads(l) for l in open(ex.cfg.log_path, encoding="utf-8")]
    decisions = [r for r in log_lines if r["event"] == "decision"]
    assert decisions[-1]["order"]["stopLoss"] == 84500.0
    assert not any(r["event"] == "order_send" for r in log_lines)


def test_orders_enabled_places_with_sl_tp(tmp_path, broker):
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    assert ex.armed is True
    d = ex.decide_entry(entry("BUY"))
    assert d["mode"] == "live" and d["sent"] is True and d["code"] == "PLACED"
    assert len(broker.trade_calls) == 1
    sent = broker.trade_calls[0]
    assert sent["stopLoss"] == 84500.0 and sent["takeProfit"] == 86500.0 and sent["volume"] == 0.44
    assert d["broker_response"]["numericCode"] == 10009
    # post-place sync re-read positions
    assert broker.read_calls.count("positions") == 2


def test_force_dry_run_flag_overrides_enabled(tmp_path, broker):
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    d = ex.decide_entry(entry("BUY"), force_dry_run=True)
    assert d["mode"] == "dry_run" and d["sent"] is False
    assert broker.trade_calls == []


def test_kill_env_blocks_even_when_enabled(tmp_path, broker):
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1", "AUTOEXEC_KILL": "1"})
    assert ex.armed is False
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "KILL_SWITCH" and d["accepted"] is False
    assert broker.trade_calls == []
    t = ex.tighten_stop({"stop": 84800})
    assert t["code"] == "KILL_SWITCH"


def test_kill_file_blocks_without_restart(tmp_path, broker):
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    assert ex.decide_entry(entry("BUY"))["code"] == "PLACED"
    broker.trade_calls.clear()
    ex.state.clear_place_attempt()
    kill = tmp_path / "state" / "KILL"
    kill.write_text("stop\n")
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "KILL_SWITCH"
    assert broker.trade_calls == []
    kill.unlink()
    assert ex.decide_entry(entry("BUY"))["code"] == "PLACED"


@pytest.mark.parametrize("step", ["account_information", "positions", "current_price", "symbol_specification", "history_deals"])
def test_failed_live_read_fails_closed(tmp_path, broker, step):
    broker.fail_reads.add(step)
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    d = ex.decide_entry(entry("BUY"))
    assert d["accepted"] is False and d["code"] == "READ_FAILED"
    assert step in d["reason"]
    assert broker.trade_calls == []


def test_account_login_mismatch_refuses(tmp_path, broker):
    broker.account["login"] = "511338298"
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "ACCOUNT_MISMATCH"
    assert broker.trade_calls == []


def test_post_place_cooldown_blocks_second_entry_until_window_passes(tmp_path, broker):
    from datetime import timedelta

    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1", "AUTOEXEC_POST_PLACE_COOLDOWN_SEC": "60"})
    assert ex.decide_entry(entry("BUY"))["code"] == "PLACED"
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "POST_PLACE_COOLDOWN"
    assert len(broker.trade_calls) == 1
    ex.clock["now"] = ex.clock["now"] + timedelta(seconds=61)
    assert ex.decide_entry(entry("BUY"))["code"] == "PLACED"


def test_broker_error_on_place_is_reported_and_cooldown_starts(tmp_path, broker):
    broker.trade_error = BrokerError("HTTP 504 POST /trade: gateway timeout", status=504)
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "PLACE_ERROR" and d["sent"] is True and d["accepted"] is False
    assert "unknown" in d["reason"].lower()
    assert ex.state.last_place_attempt()["outcome"].startswith("error")
    assert ex.decide_entry(entry("BUY"))["code"] == "POST_PLACE_COOLDOWN"


def test_broker_rejection_code_surfaced(tmp_path, broker):
    broker.trade_response = {"numericCode": 10019, "stringCode": "TRADE_RETCODE_NO_MONEY", "message": "No money"}
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "PLACE_REJECTED" and d["accepted"] is False
    assert "TRADE_RETCODE_NO_MONEY" in d["reason"]
