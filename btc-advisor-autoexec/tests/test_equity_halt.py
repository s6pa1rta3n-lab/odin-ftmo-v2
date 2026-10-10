"""Mechanic #6 (corrected 05:47 ET): halt at or below $90,750 equity, latched across restarts, manual re-enable."""

from __future__ import annotations

import json

from autoexec.config import Config
from autoexec.state import HaltLatch
from conftest import ACCOUNT, FakeBroker, entry, make_executor


def _ex(tmp_path, broker, **env):
    e = {"AUTOEXEC_ORDERS_ENABLED": "1"}
    e.update(env)
    return make_executor(tmp_path, broker, env=e)


def test_default_threshold_is_90750():
    assert Config.from_env({}).equity_halt_usd == 90750.0


def test_equity_at_threshold_blocks_and_latches(tmp_path):
    broker = FakeBroker(account=dict(ACCOUNT, equity=90750.0))
    ex = _ex(tmp_path, broker)
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "EQUITY_HALT" and d["accepted"] is False
    assert broker.trade_calls == []
    halt_file = tmp_path / "state" / "HALT"
    assert halt_file.exists()
    rec = json.loads(halt_file.read_text())
    assert rec["equity"] == 90750.0 and rec["threshold"] == 90750.0
    assert any(r["event"] == "equity_halt_latched" for r in ex.log.records)


def test_equity_just_above_threshold_allows(tmp_path):
    broker = FakeBroker(account=dict(ACCOUNT, equity=90750.01))
    ex = _ex(tmp_path, broker)
    assert ex.decide_entry(entry("BUY"))["code"] == "PLACED"
    assert not (tmp_path / "state" / "HALT").exists()


def test_old_91000_threshold_is_not_in_effect(tmp_path):
    broker = FakeBroker(account=dict(ACCOUNT, equity=91000.0))
    ex = _ex(tmp_path, broker)
    assert ex.decide_entry(entry("BUY"))["code"] == "PLACED"


def test_halt_persists_after_equity_recovers(tmp_path):
    broker = FakeBroker(account=dict(ACCOUNT, equity=90000.0))
    ex = _ex(tmp_path, broker)
    assert ex.decide_entry(entry("BUY"))["code"] == "EQUITY_HALT"
    broker.account["equity"] = 99000.0
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "EQUITY_HALT_LATCHED"
    assert broker.trade_calls == []


def test_halt_persists_across_restart(tmp_path):
    broker = FakeBroker(account=dict(ACCOUNT, equity=90000.0))
    ex = _ex(tmp_path, broker)
    assert ex.decide_entry(entry("BUY"))["code"] == "EQUITY_HALT"
    broker.account["equity"] = 99000.0
    ex2 = _ex(tmp_path, broker)  # new process, same state dir
    assert ex2.halt.active
    assert ex2.decide_entry(entry("BUY"))["code"] == "EQUITY_HALT_LATCHED"
    assert broker.trade_calls == []


def test_manual_reenable_by_deleting_halt_file(tmp_path):
    broker = FakeBroker(account=dict(ACCOUNT, equity=90000.0))
    ex = _ex(tmp_path, broker)
    assert ex.decide_entry(entry("BUY"))["code"] == "EQUITY_HALT"
    broker.account["equity"] = 99000.0
    (tmp_path / "state" / "HALT").unlink()  # the documented re-enable step
    assert ex.decide_entry(entry("BUY"))["code"] == "PLACED"


def test_manual_reenable_via_cli_halt_clear(tmp_path, monkeypatch):
    from autoexec import cli

    broker = FakeBroker(account=dict(ACCOUNT, equity=90000.0))
    ex = _ex(tmp_path, broker)
    assert ex.decide_entry(entry("BUY"))["code"] == "EQUITY_HALT"
    monkeypatch.setenv("AUTOEXEC_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AUTOEXEC_LOG_PATH", str(tmp_path / "state" / "autoexec.jsonl"))
    assert cli.main(["halt-clear"]) == 2  # refuses without --yes
    assert (tmp_path / "state" / "HALT").exists()
    assert cli.main(["halt-clear", "--yes"]) == 0
    assert not (tmp_path / "state" / "HALT").exists()
    broker.account["equity"] = 99000.0
    assert ex.decide_entry(entry("BUY"))["code"] == "PLACED"
    lines = [json.loads(l) for l in open(tmp_path / "state" / "autoexec.jsonl")]
    assert any(r["event"] == "halt_cleared_manually" for r in lines)


def test_reenable_then_equity_still_low_latches_again(tmp_path):
    broker = FakeBroker(account=dict(ACCOUNT, equity=90000.0))
    ex = _ex(tmp_path, broker)
    assert ex.decide_entry(entry("BUY"))["code"] == "EQUITY_HALT"
    HaltLatch(ex.cfg.halt_file).clear()
    assert ex.decide_entry(entry("BUY"))["code"] == "EQUITY_HALT"
    assert ex.halt.active


def test_threshold_configurable(tmp_path):
    broker = FakeBroker(account=dict(ACCOUNT, equity=92000.0))
    ex = _ex(tmp_path, broker, AUTOEXEC_EQUITY_HALT_USD="92500")
    assert ex.decide_entry(entry("BUY"))["code"] == "EQUITY_HALT"


def test_halt_checked_before_sizing_and_positions(tmp_path):
    # even with a bad setup for sizing the halt is reported first after the reads
    broker = FakeBroker(account=dict(ACCOUNT, equity=90000.0))
    broker.spec = dict(broker.spec, minVolume=1.0, volumeStep=1.0)
    ex = _ex(tmp_path, broker)
    assert ex.decide_entry(entry("BUY"))["code"] == "EQUITY_HALT"
