"""Reliability fix (Trading Ops, 2026-10-10 09:57 ET): 429/5xx retry, Retry-After, caches.

Guards, sizing, decisions and the state-file format are unchanged; these tests only
cover the transport/caching layer and the loud /tighten failure path.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from autoexec.broker import BrokerError, parse_retry_after
from autoexec.retry import RetryPolicy, run_with_retry
from conftest import FakeBroker, entry, make_executor, position

LONG = dict(pid="P1", side="BUY", open_price=84000.0, stop_loss=83500.0, take_profit=86000.0)


def _429(retry_after=None):
    return BrokerError("HTTP 429 GET /x: TooManyRequests", status=429, retry_after=retry_after)


def _5xx(code=503):
    return BrokerError(f"HTTP {code} GET /x: upstream", status=code)


def _events(ex, name):
    return [r for r in ex.log.records if r["event"] == name]


# ---------------------------------------------------------------- Retry-After parsing

def test_parse_retry_after_seconds_and_http_date():
    assert parse_retry_after("2") == 2.0
    assert parse_retry_after(" 0.5 ") == 0.5
    assert parse_retry_after("-3") == 0.0
    now = datetime(2026, 10, 10, 10, 0, 0, tzinfo=timezone.utc)
    assert parse_retry_after("Sat, 10 Oct 2026 10:00:07 GMT", now=now) == 7.0
    assert parse_retry_after("Sat, 10 Oct 2026 09:59:00 GMT", now=now) == 0.0
    assert parse_retry_after(None) is None and parse_retry_after("") is None and parse_retry_after("soon") is None


# ---------------------------------------------------------------- run_with_retry unit

class _Log:
    def __init__(self):
        self.records = []

    def emit(self, event, **data):
        rec = {"event": event}
        rec.update(data)
        self.records.append(rec)
        return rec


def _harness():
    log = _Log()
    clock = {"t": 0.0}
    sleeps = []

    def sleep(s):
        sleeps.append(s)
        clock["t"] += s

    return log, clock, sleeps, sleep


def test_retry_429_then_success_uses_backoff_and_logs():
    log, clock, sleeps, sleep = _harness()
    calls = []

    def fn():
        calls.append(1)
        if len(calls) == 1:
            raise _429()
        return "ok"

    out = run_with_retry(fn, policy=RetryPolicy(), label="positions", logger=log, sleep=sleep, monotonic=lambda: clock["t"])
    assert out == "ok" and len(calls) == 2 and sleeps == [1.0]
    events = [r["event"] for r in log.records]
    assert events == ["broker_rate_limited", "broker_retry", "broker_retry_succeeded"]
    assert log.records[0]["status"] == 429 and log.records[0]["retry_after_sec"] is None
    assert log.records[1]["delay_source"] == "backoff" and log.records[1]["attempt"] == 1
    assert log.records[2]["attempts"] == 2 and log.records[2]["outcome"] == "ok"


def test_retry_honors_retry_after():
    log, clock, sleeps, sleep = _harness()
    attempts = iter([_429(retry_after=2.5), _429(retry_after=0.25), None])

    def fn():
        exc = next(attempts)
        if exc:
            raise exc
        return 42

    assert run_with_retry(fn, policy=RetryPolicy(), label="quote", logger=log, sleep=sleep, monotonic=lambda: clock["t"]) == 42
    assert sleeps == [2.5, 0.25]
    retries = [r for r in log.records if r["event"] == "broker_retry"]
    assert [r["delay_source"] for r in retries] == ["retry-after", "retry-after"]
    limited = [r for r in log.records if r["event"] == "broker_rate_limited"]
    assert [r["retry_after_sec"] for r in limited] == [2.5, 0.25]


def test_retry_exhaustion_raises_last_error_and_logs():
    log, clock, sleeps, sleep = _harness()
    n = {"c": 0}

    def fn():
        n["c"] += 1
        raise _429(retry_after=1.0)

    with pytest.raises(BrokerError) as exc:
        run_with_retry(fn, policy=RetryPolicy(attempts=3), label="account_information", logger=log, sleep=sleep, monotonic=lambda: clock["t"])
    assert exc.value.status == 429 and n["c"] == 3 and sleeps == [1.0, 1.0]
    last = log.records[-1]
    assert last["event"] == "broker_retry_exhausted" and last["attempts"] == 3 and last["outcome"] == "failed"
    assert len([r for r in log.records if r["event"] == "broker_rate_limited"]) == 3


def test_retry_stops_when_delay_would_exceed_budget():
    log, clock, sleeps, sleep = _harness()

    def fn():
        raise _429(retry_after=30.0)  # longer than the 10s budget

    with pytest.raises(BrokerError):
        run_with_retry(fn, policy=RetryPolicy(budget_sec=10.0), label="positions", logger=log, sleep=sleep, monotonic=lambda: clock["t"])
    assert sleeps == []  # never slept: honouring Retry-After would overrun the budget
    last = log.records[-1]
    assert last["event"] == "broker_retry_exhausted" and "budget" in last["reason"]


def test_total_retry_time_within_budget_with_backoff():
    log, clock, sleeps, sleep = _harness()

    def fn():
        raise _5xx(502)

    with pytest.raises(BrokerError):
        run_with_retry(fn, policy=RetryPolicy(attempts=3, budget_sec=10.0, base_sec=1.0, max_sec=4.0), label="x", logger=log, sleep=sleep, monotonic=lambda: clock["t"])
    assert sleeps == [1.0, 2.0] and sum(sleeps) <= 10.0


def test_5xx_retried_but_4xx_not():
    log, clock, sleeps, sleep = _harness()
    seq = iter([_5xx(500), _5xx(503), "ok"])

    def fn():
        v = next(seq)
        if isinstance(v, Exception):
            raise v
        return v

    assert run_with_retry(fn, policy=RetryPolicy(), label="x", logger=log, sleep=sleep, monotonic=lambda: clock["t"]) == "ok"
    assert len(sleeps) == 2

    def bad():
        raise BrokerError("HTTP 400 bad request", status=400)

    with pytest.raises(BrokerError):
        run_with_retry(bad, policy=RetryPolicy(), label="x", logger=log, sleep=sleep, monotonic=lambda: clock["t"])
    assert len(sleeps) == 2  # no extra sleep: 400 is not retried

    def transport():
        raise BrokerError("transport error", status=None)

    with pytest.raises(BrokerError):
        run_with_retry(transport, policy=RetryPolicy(), label="x", logger=log, sleep=sleep, monotonic=lambda: clock["t"])
    assert len(sleeps) == 2


# ---------------------------------------------------------------- reads through the executor

def test_read_429_then_success_on_setup(tmp_path):
    broker = FakeBroker()
    broker.fail_next("positions", _429(retry_after=0.5))
    ex = make_executor(tmp_path, broker)
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "DRY_RUN_WOULD_PLACE", d
    assert ex.sleeps == [0.5]
    assert broker.read_calls.count("positions") == 2
    assert _events(ex, "broker_rate_limited")[0]["op"] == "positions"
    assert _events(ex, "broker_retry_succeeded")[0]["attempts"] == 2


def test_read_5xx_then_success_on_tighten(tmp_path):
    broker = FakeBroker(positions=[position(**LONG)])
    broker.fail_next("current_price", _5xx(502), _5xx(503))
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    d = ex.tighten_stop({"stop": 83800})
    assert d["code"] == "MODIFIED", d
    assert ex.sleeps == [1.0, 2.0]
    assert len(broker.trade_calls) == 1


def test_read_retry_exhaustion_returns_read_failed_and_logs(tmp_path):
    broker = FakeBroker()
    broker.fail_next("account_information", _429(1.0), _429(1.0), _429(1.0), _429(1.0))
    ex = make_executor(tmp_path, broker)
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "READ_FAILED" and "account_information" in d["reason"]
    assert broker.read_calls.count("account_information") == 3
    assert _events(ex, "broker_retry_exhausted")[-1]["op"] == "account_information"
    assert broker.trade_calls == []


# ---------------------------------------------------------------- modify retry (/tighten)

def test_modify_429_then_success(tmp_path):
    broker = FakeBroker(positions=[position(**LONG)])
    broker.fail_next("trade", _429(retry_after=2.0))
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    d = ex.tighten_stop({"stop": 83800})
    assert d["code"] == "MODIFIED" and d["accepted"] is True, d
    assert len(broker.trade_calls) == 2
    assert broker.trade_calls[0] == broker.trade_calls[1]  # identical idempotent payload
    assert ex.sleeps == [2.0]
    assert _events(ex, "broker_rate_limited")[0]["op"] == "trade:POSITION_MODIFY"


def test_modify_retry_exhaustion_is_loud(tmp_path):
    broker = FakeBroker(positions=[position(**LONG)])
    broker.fail_next("trade", _429(1.0), _429(1.0), _429(1.0))
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    d = ex.tighten_stop({"stop": 83800})
    assert d["accepted"] is False and d["code"] == "MODIFY_ERROR" and d["alert"] is True
    assert "after retries" in d["reason"] and d["broker_response"]["status"] == 429
    assert len(broker.trade_calls) == 3
    alert = _events(ex, "tighten_failed")[-1]
    assert alert["alert"] is True and alert["level"] == "ALERT" and alert["code"] == "MODIFY_ERROR"
    assert alert["position"]["id"] == "P1" and alert["request"]["stop"] == 83800
    lines = [json.loads(l) for l in open(ex.cfg.log_path)]
    assert [l for l in lines if l["event"] == "tighten_failed"]


def test_modify_5xx_then_success(tmp_path):
    broker = FakeBroker(positions=[position(**LONG)])
    broker.fail_next("trade", _5xx(500))
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    assert ex.tighten_stop({"stop": 83800})["code"] == "MODIFIED"
    assert len(broker.trade_calls) == 2


@pytest.mark.parametrize("setup", [
    lambda b: b.fail_reads.add("positions"),  # read failure after retries
    lambda b: b.fail_next("trade", BrokerError("HTTP 400 invalid stops", status=400)),  # non-retryable modify error
    lambda b: setattr(b, "trade_response", {"numericCode": 10016, "stringCode": "TRADE_RETCODE_INVALID_STOPS"}),  # broker rejection
])
def test_every_failed_tighten_returns_code_and_alerts(tmp_path, setup):
    broker = FakeBroker(positions=[position(**LONG)])
    setup(broker)
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    d = ex.tighten_stop({"stop": 83800})
    assert d["accepted"] is False and d["code"] in {"READ_FAILED", "MODIFY_ERROR", "MODIFY_REJECTED"}
    assert d["alert"] is True
    alerts = _events(ex, "tighten_failed")
    assert alerts and alerts[-1]["code"] == d["code"] and alerts[-1]["alert"] is True


def test_guard_rejected_tighten_also_alerts(tmp_path):
    broker = FakeBroker(positions=[position(**LONG)])
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    d = ex.tighten_stop({"stop": 83000})  # widen
    assert d["code"] == "SL_NOT_TIGHTER" and d["alert"] is True
    assert _events(ex, "tighten_failed")[-1]["code"] == "SL_NOT_TIGHTER"


def test_successful_tighten_has_no_alert(tmp_path):
    broker = FakeBroker(positions=[position(**LONG)])
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    d = ex.tighten_stop({"stop": 83800})
    assert d["code"] == "MODIFIED" and "alert" not in d
    assert _events(ex, "tighten_failed") == []


# ---------------------------------------------------------------- entry placement is NOT retried

def test_entry_place_429_is_not_retried_and_cooldown_starts(tmp_path):
    broker = FakeBroker()
    broker.fail_next("trade", _429(retry_after=1.0))
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "PLACE_ERROR" and d["sent"] is True and d["accepted"] is False
    assert len(broker.trade_calls) == 1  # exactly one attempt
    assert ex.sleeps == []  # no retry sleep
    assert ex.state.last_place_attempt()["outcome"].startswith("error")
    assert ex.decide_entry(entry("BUY"))["code"] == "POST_PLACE_COOLDOWN"
    assert len(broker.trade_calls) == 1
    assert _events(ex, "broker_retry") == []
    assert [r for r in _events(ex, "broker_rate_limited") if r.get("op", "").startswith("trade")] == []


def test_entry_place_5xx_is_not_retried(tmp_path):
    broker = FakeBroker()
    broker.fail_next("trade", _5xx(503))
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "PLACE_ERROR" and len(broker.trade_calls) == 1 and ex.sleeps == []


# ---------------------------------------------------------------- /status snapshot cache

def _status_calls(broker):
    return len(broker.read_calls)


def test_status_cache_hit_within_ttl_and_refresh_after(tmp_path):
    broker = FakeBroker()
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_STATUS_CACHE_SEC": "15"})
    s1 = ex.status()
    assert s1["ok"] and s1["snapshot"]["cached"] is False
    n = _status_calls(broker)
    # first status: account, positions, broker symbol list, spec + price for the default symbol,
    # deals today, deals lookback, calculate-margin for the per-symbol view
    assert n == 8
    ex.clock["mono"] += 10
    s2 = ex.status()
    assert s2["ok"] and s2["snapshot"]["cached"] is True and s2["snapshot"]["age_sec"] == 10.0
    assert _status_calls(broker) == n  # no live calls
    ex.clock["mono"] += 6  # 16s since the snapshot
    s3 = ex.status()
    assert s3["snapshot"]["cached"] is False
    # refresh: account, positions, quote, deals today, calculate-margin = 5 fresh reads;
    # symbol list, spec and lookback still cached (30 min)
    assert _status_calls(broker) == n + 5
    assert s3["reads"]["cache_hits"] == ["symbol_specification(BTCUSD)", "history_deals(lookback)"]


def test_status_cache_keeps_local_guard_inputs_live(tmp_path):
    broker = FakeBroker()
    ex = make_executor(tmp_path, broker)
    assert ex.status()["guards"]["halt_latched"] is False
    ex.halt.latch(equity=1, threshold=90750, reason="t")
    (tmp_path / "state" / "KILL").write_text("x")
    s = ex.status()
    assert s["snapshot"]["cached"] is True
    assert s["guards"]["halt_latched"] is True and s["guards"]["kill_active"] is True


def test_status_failure_is_logged_and_negative_cached(tmp_path):
    broker = FakeBroker()
    broker.fail_reads.add("current_price")
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_STATUS_CACHE_SEC": "15"})
    s1 = ex.status()
    assert s1["ok"] is False and s1["code"] == "READ_FAILED" and s1["snapshot"]["cached"] is False
    failed = _events(ex, "status_read_failed")
    assert failed and failed[-1]["alert"] is True and failed[-1]["step"] == "current_price(BTCUSD)"
    n = len(broker.read_calls)
    s2 = ex.status()
    assert s2["ok"] is False and s2["snapshot"]["cached"] is True
    assert len(broker.read_calls) == n  # no new live calls during the TTL
    broker.fail_reads.clear()
    ex.clock["mono"] += 16
    assert ex.status()["ok"] is True


def test_status_cache_disabled_with_zero_ttl(tmp_path):
    broker = FakeBroker()
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_STATUS_CACHE_SEC": "0"})
    ex.status()
    n = len(broker.read_calls)
    ex.status()
    assert len(broker.read_calls) == n + 5  # fresh reads (account, positions, quote, deals today, calculate-margin) except the 30-min caches


def test_setup_and_tighten_bypass_status_cache(tmp_path):
    broker = FakeBroker(positions=[position(**LONG)])
    ex = make_executor(tmp_path, broker)
    assert ex.status()["ok"]
    n = len(broker.read_calls)
    # change the broker state; a cached /status would not see it, a fresh read must
    broker.positions_list = []
    s = ex.status()
    assert s["snapshot"]["cached"] is True and s["guards"]["total_open"] == 1
    d = ex.decide_entry(entry("BUY"))
    assert d["guards"]["total_open"] == 0 and d["code"] == "DRY_RUN_WOULD_PLACE"
    assert broker.read_calls[n:].count("positions") == 1
    t = ex.tighten_stop({"stop": 83800})
    assert t["code"] == "NO_AUTO_POSITION"  # saw the fresh (empty) book, not the snapshot
    assert broker.read_calls[n:].count("positions") == 2
    # and the status snapshot is untouched by those fresh reads
    assert ex.status()["guards"]["total_open"] == 1


# ---------------------------------------------------------------- spec / commission caches

def test_spec_and_commission_lookback_cached_for_ttl(tmp_path):
    broker = FakeBroker()
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_SPEC_CACHE_SEC": "1800", "AUTOEXEC_COMMISSION_CACHE_SEC": "1800"})
    ex.decide_entry(entry("BUY"))
    assert broker.read_calls.count("symbol_specification") == 1 and broker.read_calls.count("history_deals") == 2
    ex.clock["mono"] += 1799
    ex.decide_entry(entry("BUY"))
    assert broker.read_calls.count("symbol_specification") == 1 and broker.read_calls.count("history_deals") == 3  # today only
    ex.clock["mono"] += 2  # past the TTL
    ex.decide_entry(entry("BUY"))
    assert broker.read_calls.count("symbol_specification") == 2 and broker.read_calls.count("history_deals") == 5


def test_spec_and_commission_cache_configurable_and_disableable(tmp_path):
    broker = FakeBroker()
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_SPEC_CACHE_SEC": "0", "AUTOEXEC_COMMISSION_CACHE_SEC": "60"})
    ex.decide_entry(entry("BUY"))
    ex.decide_entry(entry("BUY"))
    assert broker.read_calls.count("symbol_specification") == 2  # disabled -> fresh every time
    assert broker.read_calls.count("history_deals") == 3  # lookback cached once
    ex.clock["mono"] += 61
    ex.decide_entry(entry("BUY"))
    assert broker.read_calls.count("history_deals") == 5


def test_cached_spec_gives_identical_sizing(tmp_path):
    broker = FakeBroker()
    ex = make_executor(tmp_path, broker)
    d1 = ex.decide_entry(entry("BUY"))
    d2 = ex.decide_entry(entry("BUY"))
    assert (d1["lots"], d1["per_lot_loss"], d1["commission_per_lot_roundtrip"], d1["sizing"]) == (d2["lots"], d2["per_lot_loss"], d2["commission_per_lot_roundtrip"], d2["sizing"])


def test_state_file_format_unchanged_by_caches(tmp_path):
    broker = FakeBroker()
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    ex.status()
    ex.decide_entry(entry("BUY"))
    state = json.loads((tmp_path / "state" / "state.json").read_text())
    assert set(state.keys()) == {"last_place_attempt"}
    assert set(state["last_place_attempt"].keys()) == {"at_epoch", "request_id", "outcome"}


def test_retry_config_from_env(tmp_path):
    broker = FakeBroker()
    broker.fail_next("positions", _5xx(503), _5xx(503), _5xx(503), _5xx(503), _5xx(503))
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_RETRY_ATTEMPTS": "5", "AUTOEXEC_RETRY_BUDGET_SEC": "60", "AUTOEXEC_RETRY_BASE_SEC": "0.5", "AUTOEXEC_RETRY_MAX_SEC": "1"})
    assert ex.decide_entry(entry("BUY"))["code"] == "READ_FAILED"
    assert broker.read_calls.count("positions") == 5 and ex.sleeps == [0.5, 1.0, 1.0, 1.0]
    ex1 = make_executor(tmp_path / "b", FakeBroker(), env={"AUTOEXEC_RETRY_ATTEMPTS": "1"})
    ex1.broker.fail_next("positions", _429())
    assert ex1.decide_entry(entry("BUY"))["code"] == "READ_FAILED" and ex1.sleeps == []
