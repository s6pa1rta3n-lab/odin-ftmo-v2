"""Commission source resolution, JSONL logging + token redaction, config defaults, HTTP endpoint."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from decimal import Decimal

import pytest

from autoexec.commission import commission_from_deals, resolve_commission
from autoexec.config import Config
from autoexec.jsonlog import JsonLogger, redact
from autoexec.server import make_server
from conftest import SPEC, FakeBroker, deal, entry, make_executor, position

# ---------------------------------------------------------------- commission

RT_DEALS = [
    deal("i1", time="2026-10-01T10:00:00Z", profit=0.0, commission=-5.4, entry_type="DEAL_ENTRY_IN", volume=0.4, position_id="A", dtype="DEAL_TYPE_BUY"),
    deal("o1", time="2026-10-01T12:00:00Z", profit=50.0, commission=-5.4, entry_type="DEAL_ENTRY_OUT", volume=0.4, position_id="A"),
    deal("i2", time="2026-10-02T10:00:00Z", profit=0.0, commission=-2.7, entry_type="DEAL_ENTRY_IN", volume=0.2, position_id="B", dtype="DEAL_TYPE_BUY"),
    deal("o2", time="2026-10-02T12:00:00Z", profit=-20.0, commission=-2.7, entry_type="DEAL_ENTRY_OUT", volume=0.2, position_id="B"),
    deal("i3", time="2026-10-03T10:00:00Z", profit=0.0, commission=-13.5, entry_type="DEAL_ENTRY_IN", volume=1.0, position_id="OPEN", dtype="DEAL_TYPE_BUY"),  # no OUT leg
]


def test_deals_round_trip_math_ignores_open_legs():
    value, n, vol = commission_from_deals(RT_DEALS, "BTCUSD")
    assert n == 2 and vol == Decimal("0.6")
    assert value == Decimal("16.2") / Decimal("0.6")  # 27 per lot round trip


def test_auto_prefers_spec_then_deals_then_model():
    env = Decimal("27")
    assert resolve_commission(mode="auto", env_value=env, spec=SPEC, deals=[], symbol="BTCUSD", model="flat").source == "env"
    r = resolve_commission(mode="auto", env_value=env, spec=SPEC, deals=RT_DEALS, symbol="BTCUSD", model="flat")
    assert r.source == "deals" and r.per_lot_roundtrip == Decimal("27")
    r2 = resolve_commission(mode="auto", env_value=env, spec=dict(SPEC, commission=30.0), deals=RT_DEALS, symbol="BTCUSD", model="flat")
    assert r2.source == "spec" and r2.per_lot_roundtrip == Decimal("30.0")
    # no model at all -> none (never guessed)
    assert resolve_commission(mode="auto", env_value=env, spec=SPEC, deals=[], symbol="XAUUSD", model=None).source == "none"


def test_pinned_sources_fail_closed_without_data():
    env = Decimal("27")
    assert resolve_commission(mode="spec", env_value=env, spec=SPEC, deals=RT_DEALS, symbol="BTCUSD", model="flat").per_lot_roundtrip is None
    assert resolve_commission(mode="deals", env_value=env, spec=SPEC, deals=[], symbol="BTCUSD", model="flat").per_lot_roundtrip is None
    assert resolve_commission(mode="env", env_value=env, spec=dict(SPEC, commission=30.0), deals=RT_DEALS, symbol="BTCUSD", model="flat").per_lot_roundtrip == env


def test_entry_rejected_when_pinned_commission_unavailable(tmp_path):
    ex = make_executor(tmp_path, FakeBroker(), env={"AUTOEXEC_COMMISSION_SOURCE": "deals"})
    d = ex.decide_entry(entry("BUY"))
    assert d["code"] == "COMMISSION_UNAVAILABLE"


def test_observed_commission_used_in_sizing_and_source_logged(tmp_path):
    broker = FakeBroker(deals=[dict(d, commission=d["commission"] * 2) for d in RT_DEALS])  # 54/lot observed
    ex = make_executor(tmp_path, broker)
    d = ex.decide_entry(entry("BUY"))
    assert d["commission_source"] == "deals" and d["commission_per_lot_roundtrip"] == 54.0
    assert d["per_lot_loss"] == 594.0 and d["lots"] == 0.42
    assert d["commission"]["deals_round_trips"] == 2


def test_env_fallback_default_is_27_and_configurable():
    assert Config.from_env({}).commission_per_lot_roundtrip == 27.0
    assert Config.from_env({"AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP": "12.5"}).commission_per_lot_roundtrip == 12.5


# ---------------------------------------------------------------- config

def test_config_defaults_match_approved_mechanics():
    c = Config.from_env({})
    assert c.orders_enabled is False
    assert c.max_risk_usd == 250.0 and c.daily_loss_cap_usd == 500.0 and c.equity_halt_usd == 90750.0
    assert c.max_positions_total == 2 and c.second_position_min_rr == 2.0 and c.min_margin_level_pct == 200.0
    assert c.account_id == "a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf" and c.expected_login == "541458001" and c.symbol == "BTCUSD"
    assert c.client_host == "https://mt-client-api-v1.london.agiliumtrade.ai"
    assert c.day_tz == "Europe/Prague" and c.bind_host == "127.0.0.1"
    assert c.magic != 0 and c.comment == "BTC_ADVISOR_AUTO"
    assert c.margin_per_lot_usd is None and c.symbol_leverage is None and c.margin_use_account_leverage is False


def test_config_rejects_unapproved_values():
    with pytest.raises(ValueError):
        Config.from_env({"AUTOEXEC_MAX_POSITIONS_TOTAL": "3"})
    with pytest.raises(ValueError):
        Config.from_env({"AUTOEXEC_MAGIC": "0"})
    with pytest.raises(ValueError):
        Config.from_env({"AUTOEXEC_COMMISSION_SOURCE": "guess"})


def test_public_dict_has_no_token_or_api_key():
    c = Config.from_env({"AUTOEXEC_API_KEY": "k-123"})
    pd = c.public_dict()
    assert "api_key" not in pd and pd["api_key_set"] is True
    assert "token" not in json.dumps(pd).lower() or "token_source" in pd  # only the *path* to the token file


# ---------------------------------------------------------------- logging

def test_redaction_of_secret_keys_and_raw_token(tmp_path):
    log = JsonLogger(str(tmp_path / "l.jsonl"), stdout=False, token="SECRET-TOKEN-123")
    log.emit("x", headers={"auth-token": "SECRET-TOKEN-123", "Accept": "json"}, nested={"metaapi": {"token": "SECRET-TOKEN-123"}}, note="leak SECRET-TOKEN-123 here")
    line = (tmp_path / "l.jsonl").read_text()
    assert "SECRET-TOKEN-123" not in line
    rec = json.loads(line)
    assert rec["headers"]["auth-token"] == "[REDACTED]" and rec["headers"]["Accept"] == "json"
    assert rec["nested"]["metaapi"]["token"] == "[REDACTED]"
    assert "[REDACTED]" in rec["note"]


def test_redact_helper_handles_lists():
    out = redact([{"api_key": "a"}, {"ok": 1}])
    assert out == [{"api_key": "[REDACTED]"}, {"ok": 1}]


def test_decision_log_is_structured_jsonl_with_required_fields(tmp_path):
    ex = make_executor(tmp_path, FakeBroker(), env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    ex.decide_entry(entry("BUY", request_id="req-1"))
    lines = [json.loads(l) for l in open(ex.cfg.log_path)]
    events = [l["event"] for l in lines]
    assert events[:2] == ["request", "order_send"] or "request" in events
    assert "order_send" in events and "decision" in events and "post_place_sync" in events
    dec = [l for l in lines if l["event"] == "decision"][-1]
    for key in ("decision_id", "action", "mode", "code", "reason", "guards", "order", "broker_response", "request", "sizing", "commission"):
        assert key in dec, key
    assert dec["request"]["request_id"] == "req-1"
    assert "SECRET-TOKEN-123" not in open(ex.cfg.log_path).read()


# ---------------------------------------------------------------- HTTP endpoint

@pytest.fixture
def http_server(tmp_path):
    broker = FakeBroker(positions=[position(pid="P1", stop_loss=84100.0)])  # breakeven+ so a second entry is possible
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_SYMBOL_LEVERAGE": "2"})  # orders disabled
    server = make_server(ex, host="127.0.0.1", port=0, api_key="k-123")
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        yield server, ex, broker
    finally:
        server.shutdown()
        server.server_close()


def _call(server, method, path, body=None, key="k-123"):
    url = f"http://127.0.0.1:{server.server_address[1]}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-Autoexec-Key"] = key
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_http_health_and_auth(http_server):
    server, ex, broker = http_server
    status, body = _call(server, "GET", "/health")
    assert status == 200 and body["ok"] and body["orders_enabled"] is False and body["armed"] is False
    status, body = _call(server, "GET", "/health", key=None)
    assert status == 401 and body["code"] == "UNAUTHORIZED"
    status, _ = _call(server, "GET", "/nope")
    assert status == 404


def test_http_setup_dry_run_sends_nothing(http_server):
    server, ex, broker = http_server
    status, body = _call(server, "POST", "/setup", {"side": "BUY", "entry_type": "MARKET", "stop": 84500, "target": 86500})
    assert status == 200
    assert body["ok"] is True and body["mode"] == "dry_run" and body["sent"] is False
    assert body["code"] == "DRY_RUN_WOULD_PLACE" and body["lots"] == 0.44 and body["risk_usd"] <= 250
    assert body["reason"] and body["order"]["stopLoss"] == 84500.0
    assert body["second_position"]["passed"] is True
    assert broker.trade_calls == []


def test_http_setup_rejections(http_server):
    server, ex, broker = http_server
    status, body = _call(server, "POST", "/setup", {"side": "BUY", "entry_type": "LIMIT", "stop": 84500, "target": 86500})
    assert status == 200 and body["ok"] is False and body["code"] == "ENTRY_TYPE_NOT_MARKET"
    status, body = _call(server, "POST", "/setup", {"side": "BUY", "entry_type": "MARKET", "stop": 84500})
    assert body["code"] == "MISSING_TP"
    status, body = _call(server, "POST", "/setup", None)
    assert status == 200 and body["code"] == "BAD_SIDE"


def test_http_bad_json(http_server):
    server, _, _ = http_server
    url = f"http://127.0.0.1:{server.server_address[1]}/setup"
    req = urllib.request.Request(url, data=b"{not json", headers={"X-Autoexec-Key": "k-123"}, method="POST")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 400


def test_http_tighten_and_status(http_server):
    server, ex, broker = http_server
    status, body = _call(server, "POST", "/tighten", {"stop": 83000})
    assert body["ok"] is False and body["code"] == "SL_NOT_TIGHTER"
    status, body = _call(server, "POST", "/tighten", {"stop": 84500})
    assert body["ok"] is True and body["code"] == "DRY_RUN_WOULD_MODIFY" and body["sent"] is False
    assert broker.trade_calls == []
    status, body = _call(server, "GET", "/status")
    assert status == 200 and body["ok"] is True
    g = body["guards"]
    assert g["equity"] == 95000.0 and g["halt_latched"] is False and g["total_open"] == 1
    assert g["commission"]["source"] == "env" and g["quote"]["spread"] == 20.0
    assert "reads" not in body
    assert "SECRET-TOKEN-123" not in json.dumps(body)


def test_http_status_503_when_reads_fail(http_server):
    server, ex, broker = http_server
    broker.fail_reads.add("account_information")
    status, body = _call(server, "GET", "/status")
    assert status == 503 and body["code"] == "READ_FAILED"


def test_http_dry_run_flag_in_body(tmp_path):
    broker = FakeBroker()
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    server = make_server(ex, host="127.0.0.1", port=0)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        status, body = _call(server, "POST", "/setup", {"side": "BUY", "entry_type": "MARKET", "stop": 84500, "target": 86500, "dry_run": True}, key=None)
        assert body["mode"] == "dry_run" and broker.trade_calls == []
        status, body = _call(server, "POST", "/setup", {"side": "BUY", "entry_type": "MARKET", "stop": 84500, "target": 86500}, key=None)
        assert body["mode"] == "live" and body["code"] == "PLACED" and len(broker.trade_calls) == 1
    finally:
        server.shutdown()
        server.server_close()


# ---------------------------------------------------------------- CLI

def test_cli_setup_and_status(tmp_path, monkeypatch, capsys):
    from autoexec import cli

    broker = FakeBroker()
    monkeypatch.setenv("AUTOEXEC_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AUTOEXEC_TOKEN", "SECRET-TOKEN-123")
    monkeypatch.setattr(cli, "MetaApiRest", lambda *a, **k: broker)
    rc = cli.main(["setup", "--side", "buy", "--stop", "84500", "--target", "86500"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["code"] == "DRY_RUN_WOULD_PLACE" and out["sent"] is False
    assert broker.trade_calls == []
    rc = cli.main(["setup", "--side", "buy", "--entry-type", "LIMIT", "--stop", "84500", "--target", "86500"])
    assert rc == 2 and json.loads(capsys.readouterr().out)["code"] == "ENTRY_TYPE_NOT_MARKET"
    rc = cli.main(["status"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["ok"] and out["guards"]["orders_enabled"] is False
    assert "SECRET-TOKEN-123" not in json.dumps(out)
    rc = cli.main(["kill"])
    assert rc == 0 and (tmp_path / "state" / "KILL").exists()
    assert json.loads(capsys.readouterr().out)["kill_active"] is True
    rc = cli.main(["setup", "--side", "buy", "--stop", "84500", "--target", "86500"])
    assert rc == 2 and json.loads(capsys.readouterr().out)["code"] == "KILL_SWITCH"
    assert cli.main(["unkill"]) == 0 and not (tmp_path / "state" / "KILL").exists()
