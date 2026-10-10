"""Mechanic #2: $250 max risk incl. spread + commission, floor to volume step, skip below min lot."""

from __future__ import annotations

from decimal import Decimal

import pytest

from autoexec.sizing import SizingError, floor_to_step, parse_spec, size_position
from conftest import SPEC, entry


def test_per_lot_loss_includes_stop_spread_and_commission(executor, broker):
    # BUY fills at ask 85020; stop 84500 -> distance 520; spread 20; commission 27 -> 567 per lot
    d = executor.decide_entry(entry("BUY", stop=84500, target=86500))
    assert d["accepted"], d
    assert d["stop_distance"] == 520.0
    assert d["spread"] == 20.0
    assert d["spread_cost_per_lot"] == 20.0
    assert d["commission_per_lot_roundtrip"] == 27.0
    assert d["commission_source"] == "env"
    assert d["per_lot_loss"] == 567.0
    # floor(250 / 567 = 0.4409..., step 0.01) = 0.44
    assert d["lots"] == 0.44
    assert d["risk_usd"] == pytest.approx(0.44 * 567, abs=1e-9)
    assert d["risk_usd"] <= 250.0


def test_sell_uses_bid_as_fill_reference(executor, broker):
    # SELL fills at bid 85000; stop 85600 -> distance 600; + 20 spread + 27 = 647 -> 0.38 lots
    d = executor.decide_entry(entry("SELL", stop=85600, target=83000))
    assert d["accepted"], d
    assert d["stop_distance"] == 600.0
    assert d["per_lot_loss"] == 647.0
    assert d["lots"] == 0.38


def test_lots_never_rounded_up(executor):
    # distance 480 + 20 + 27 = 527 -> 250/527 = 0.47438 -> 0.47, not 0.48
    d = executor.decide_entry(entry("BUY", stop=84540, target=86500))
    assert d["lots"] == 0.47
    assert d["risk_usd"] < 250.0


def test_floor_to_step_exact_decimal():
    assert floor_to_step(Decimal("0.4409"), Decimal("0.01")) == Decimal("0.44")
    assert floor_to_step(Decimal("0.4499999"), Decimal("0.01")) == Decimal("0.44")
    assert floor_to_step(Decimal("1.0"), Decimal("0.1")) == Decimal("1.0")
    assert floor_to_step(Decimal("0.29"), Decimal("0.1")) == Decimal("0.2")


def test_skip_when_min_volume_exceeds_max_risk(tmp_path, broker):
    from conftest import make_executor

    # min lot 1.0: per-lot loss 567 > 250 -> skip, no order built
    broker.spec = dict(SPEC, minVolume=1.0, volumeStep=1.0)
    ex = make_executor(tmp_path, broker, env={"AUTOEXEC_ORDERS_ENABLED": "1"})
    d = ex.decide_entry(entry("BUY", stop=84500, target=86500))
    assert d["accepted"] is False
    assert d["code"] == "SKIP_MIN_VOLUME"
    assert "minimum volume" in d["reason"]
    assert d["lots"] == 0.0
    assert "order" not in d
    assert broker.trade_calls == []


def test_commission_and_spread_reduce_lots(tmp_path, broker):
    from conftest import make_executor

    ex0 = make_executor(tmp_path / "a", broker, env={"AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP": "0"})
    broker.quote = dict(broker.quote, bid=85020.0, ask=85020.0)  # zero spread
    d0 = ex0.decide_entry(entry("BUY", stop=84520, target=86500))
    assert d0["per_lot_loss"] == 500.0 and d0["lots"] == 0.5

    broker.quote = dict(broker.quote, bid=85000.0, ask=85020.0)
    ex1 = make_executor(tmp_path / "b", broker, env={"AUTOEXEC_COMMISSION_PER_LOT_ROUNDTRIP": "27"})
    d1 = ex1.decide_entry(entry("BUY", stop=84520, target=86500))
    assert d1["per_lot_loss"] == 547.0 and d1["lots"] == 0.45


def test_capped_at_max_volume(tmp_path, broker):
    from conftest import make_executor

    broker.spec = dict(SPEC, maxVolume=0.1)
    ex = make_executor(tmp_path, broker)
    d = ex.decide_entry(entry("BUY", stop=84500, target=86500))
    assert d["accepted"] and d["lots"] == 0.1
    assert d["sizing"]["reason"] == "capped_at_max_volume"


def test_value_per_unit_from_tick_fields_prefers_loss_tick_value():
    spec = parse_spec(dict(SPEC, lossTickValue=0.02, profitTickValue=0.01, tickValue=0.01))
    assert spec.value_per_unit_per_lot == Decimal("2")
    assert spec.value_source == "lossTickValue/tickSize"


def test_value_per_unit_falls_back_to_contract_size():
    spec = parse_spec({"contractSize": 1, "volumeStep": 0.01, "minVolume": 0.01})
    assert spec.value_per_unit_per_lot == Decimal("1")
    assert spec.value_source == "contractSize"


def test_spec_without_value_fields_fails_closed():
    with pytest.raises(SizingError):
        parse_spec({"volumeStep": 0.01, "minVolume": 0.01})
    with pytest.raises(SizingError):
        parse_spec({"contractSize": 1, "minVolume": 0.01})  # no volumeStep


def test_size_position_rejects_non_positive_stop_distance():
    spec = parse_spec(SPEC)
    with pytest.raises(SizingError):
        size_position(stop_distance=Decimal("0"), spread=Decimal("1"), spec=spec, commission_per_lot_roundtrip=Decimal("27"), max_risk_usd=Decimal("250"))


def test_every_decision_logs_spread_commission_and_per_lot_loss(executor):
    executor.decide_entry(entry("BUY", stop=84500, target=86500))
    decisions = [r for r in executor.log.records if r["event"] == "decision"]
    assert decisions
    rec = decisions[-1]
    for key in ("spread", "commission_per_lot_roundtrip", "commission_source", "per_lot_loss", "lots", "risk_usd"):
        assert key in rec, key
