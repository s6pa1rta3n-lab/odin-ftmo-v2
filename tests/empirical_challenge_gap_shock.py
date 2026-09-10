"""Drawdown and adverse market shock test harness.

Simulates extreme 5x ATR adverse market gap shocks against LondonReversalSimulator
and OmniBreakoutSimulator using winning profiles, and tests EquityWatchdog emergency halts.
Verifies that FTMO constraints ($90,000 floor, 5.0% daily limit, 4.5% circuit breaker)
are strictly preserved even under sudden flash crash conditions.
"""

import json
import math
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backtester.engine import (
    ATRCalculator,
    BacktestEngine,
    BacktestMetrics,
    BacktestProfile,
    Candle,
    EngineType,
    ExitManager,
    ExitModel,
    LondonReversalSimulator,
    OmniBreakoutSimulator,
    Position,
    PyramidModel,
    RiskModel,
    RiskSizer,
)
from verifier.validator import EquityWatchdog, validate_profile_file


def create_candle(
    timestamp: datetime,
    open_p: float,
    high_p: float,
    low_p: float,
    close_p: float,
    volume: float = 100.0,
) -> Candle:
    """Create a single Candle instance with UTC timezone."""
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return Candle(
        timestamp=timestamp,
        open=open_p,
        high=high_p,
        low=low_p,
        close=close_p,
        volume=volume,
    )


def test_london_adverse_gap_shock() -> Dict[str, Any]:
    """Test LondonReversalSimulator under an extreme 5x ATR adverse gap shock.

    Baseline ATR is 40.0 pts on US100.cash. 5x ATR corresponds to 200.0 pts.
    """
    starting_equity = 94939.28
    ftmo_floor = 90000.00
    emergency_floor = 90500.00
    daily_cb_limit = starting_equity * 0.045

    profile_path = PROJECT_ROOT / "profiles" / "london_winner.json"
    with open(profile_path, "r", encoding="utf-8") as f:
        doc = json.load(f)

    profile = BacktestProfile(
        engine=EngineType(doc["engine"]),
        risk_model=RiskModel(doc["dimensions"]["risk_model"]),
        entry_mode=doc["dimensions"]["entry_mode"],
        pyramid_model=PyramidModel(doc["dimensions"]["pyramid_model"]),
        exit_model=ExitModel(doc["dimensions"]["exit_model"]),
        filters=doc["dimensions"].get("filters", []),
        instrument=doc.get("instrument", "US100.cash"),
    )

    base_date = datetime(2026, 9, 8, tzinfo=timezone.utc)
    asian_high = 19600.0
    asian_low = 19500.0
    atr = 40.0

    candles: List[Candle] = []
    base_time = base_date.replace(hour=7, minute=0, second=0, microsecond=0)

    for m in range(15):
        t = base_time + timedelta(minutes=m)
        p = 19505.0 - (m * 0.3)
        candles.append(create_candle(t, p, p + 0.5, p - 0.5, p))

    sweep_t = base_time + timedelta(minutes=15)
    candles.append(create_candle(sweep_t, 19500.5, 19501.0, 19499.0, 19500.5))

    shock_t = base_time + timedelta(minutes=16)
    candles.append(create_candle(shock_t, 19280.0, 19285.0, 19250.0, 19260.0))

    for m in range(17, 360):
        t = base_time + timedelta(minutes=m)
        candles.append(create_candle(t, 19260.0, 19265.0, 19255.0, 19260.0))

    sim = LondonReversalSimulator(profile, starting_equity, tick_value=1.0)
    risk_sizer = RiskSizer(profile.risk_model, starting_equity, tick_value=1.0)

    trades = sim.simulate_day(candles, asian_high, asian_low, atr, risk_sizer)
    ending_equity = sim.equity

    total_loss = starting_equity - ending_equity
    loss_pct = total_loss / starting_equity

    passed_floor = ending_equity >= emergency_floor
    passed_daily_cb = total_loss <= daily_cb_limit

    return {
        "trades_count": len(trades),
        "starting_equity": starting_equity,
        "ending_equity": ending_equity,
        "total_loss": total_loss,
        "loss_pct": loss_pct,
        "passed_floor": passed_floor,
        "passed_daily_cb": passed_daily_cb,
        "trades": [{"pnl_dollars": t.pnl_dollars, "exit_reason": t.exit_reason, "lots": t.lots} for t in trades],
    }


def test_omni_adverse_gap_shock() -> Dict[str, Any]:
    """Test OmniBreakoutSimulator under an extreme 5x ATR adverse gap shock."""
    starting_equity = 94939.28
    ftmo_floor = 90000.00
    emergency_floor = 90500.00
    daily_cb_limit = starting_equity * 0.045

    profile_path = PROJECT_ROOT / "profiles" / "omni_winner.json"
    with open(profile_path, "r", encoding="utf-8") as f:
        doc = json.load(f)

    profile = BacktestProfile(
        engine=EngineType(doc["engine"]),
        risk_model=RiskModel(doc["dimensions"]["risk_model"]),
        entry_mode=doc["dimensions"]["entry_mode"],
        pyramid_model=PyramidModel(doc["dimensions"]["pyramid_model"]),
        exit_model=ExitModel(doc["dimensions"]["exit_model"]),
        filters=doc["dimensions"].get("filters", []),
        instrument=doc.get("instrument", "US100.cash"),
    )

    base_date = datetime(2026, 9, 8, tzinfo=timezone.utc)
    orb_high = 19700.0
    orb_low = 19620.0
    atr = 40.0

    candles: List[Candle] = []
    base_time = base_date.replace(hour=14, minute=30, second=0, microsecond=0)

    for m in range(5):
        t = base_time + timedelta(minutes=m)
        p = 19680.0 + (m * 4.0)
        candles.append(create_candle(t, p, p + 2.0, p - 2.0, p + 1.0))

    breakout_t = base_time + timedelta(minutes=5)
    candles.append(create_candle(breakout_t, 19702.0, 19725.0, 19700.0, 19720.0, volume=800.0))

    shock_t = base_time + timedelta(minutes=6)
    candles.append(create_candle(shock_t, 19500.0, 19505.0, 19480.0, 19490.0))

    for m in range(7, 330):
        t = base_time + timedelta(minutes=m)
        candles.append(create_candle(t, 19490.0, 19495.0, 19485.0, 19490.0))

    sim = OmniBreakoutSimulator(profile, starting_equity, tick_value=1.0)
    risk_sizer = RiskSizer(profile.risk_model, starting_equity, tick_value=1.0)

    trades = sim.simulate_day(candles, orb_high, orb_low, atr, risk_sizer)
    ending_equity = sim.equity

    total_loss = starting_equity - ending_equity
    loss_pct = total_loss / starting_equity

    passed_floor = ending_equity >= emergency_floor
    passed_daily_cb = total_loss <= daily_cb_limit

    return {
        "trades_count": len(trades),
        "starting_equity": starting_equity,
        "ending_equity": ending_equity,
        "total_loss": total_loss,
        "loss_pct": loss_pct,
        "passed_floor": passed_floor,
        "passed_daily_cb": passed_daily_cb,
        "trades": [{"pnl_dollars": t.pnl_dollars, "exit_reason": t.exit_reason, "lots": t.lots} for t in trades],
    }


def test_equity_watchdog_circuit_breaker() -> Dict[str, Any]:
    """Test EquityWatchdog triggering on 4.5% daily loss and $90,500 emergency floor."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        lockout_path = Path(tmp_dir) / "daily_lockouts.json"
        watchdog = EquityWatchdog(
            daily_watermark=94939.28,
            account_floor=90000.00,
            emergency_floor=90500.00,
            circuit_breaker_pct=0.045,
            lockout_file=str(lockout_path),
        )

        act1, r1 = watchdog.check_equity(93000.0)
        act2, r2 = watchdog.check_equity(90600.0)
        locked_cb = watchdog.is_locked_out()

        act3, r3 = watchdog.check_equity(90400.0)
        locked_emerg = watchdog.is_locked_out()

        return {
            "mild_drop_action": act1,
            "cb_drop_action": act2,
            "cb_locked_out": locked_cb,
            "emergency_drop_action": act3,
            "emergency_locked_out": locked_emerg,
            "passed": (
                act1 == "NORMAL"
                and act2 == "CIRCUIT_BREAKER"
                and locked_cb is True
                and act3 == "EMERGENCY_STOP"
                and locked_emerg is True
            ),
        }


def run_all_shock_tests() -> Dict[str, Any]:
    """Execute all adverse market shock tests and return combined report."""
    london_res = test_london_adverse_gap_shock()
    omni_res = test_omni_adverse_gap_shock()
    watchdog_res = test_equity_watchdog_circuit_breaker()

    all_passed = (
        london_res["passed_floor"]
        and london_res["passed_daily_cb"]
        and omni_res["passed_floor"]
        and omni_res["passed_daily_cb"]
        and watchdog_res["passed"]
    )

    return {
        "all_passed": all_passed,
        "london": london_res,
        "omni": omni_res,
        "watchdog": watchdog_res,
    }


if __name__ == "__main__":
    report = run_all_shock_tests()
    print(f"Overall Shock Test: {'PASSED' if report['all_passed'] else 'FAILED'}")
    l = report["london"]
    print(f"London 5x ATR Shock: Loss=${l['total_loss']:.2f} ({l['loss_pct']:.2%}) | Ending Equity=${l['ending_equity']:.2f} | Floor OK={l['passed_floor']} | CB OK={l['passed_daily_cb']}")
    o = report["omni"]
    print(f"Omni 5x ATR Shock:   Loss=${o['total_loss']:.2f} ({o['loss_pct']:.2%}) | Ending Equity=${o['ending_equity']:.2f} | Floor OK={o['passed_floor']} | CB OK={o['passed_daily_cb']}")
    w = report["watchdog"]
    print(f"Watchdog CB Action:  {w['cb_drop_action']} (Locked={w['cb_locked_out']}) | Emergency Action: {w['emergency_drop_action']} (Locked={w['emergency_locked_out']})")
    if not report["all_passed"]:
        sys.exit(1)
    sys.exit(0)
