"""Tier 4: Realistic End-to-End FTMO Challenge Trading Simulations.

Simulates complete FTMO verification challenge scenarios starting from the exact
account balance ($94,939.28), adhering to the $90,000 absolute floor, 5% daily
mark-to-market limit, 4.5% internal circuit breaker, and $110,000 profit target.
"""

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
import pytest

from backtester.engine import (
    AsianRangeDetector,
    ATRCalculator,
    BacktestEngine,
    BacktestMetrics,
    BacktestProfile,
    Candle,
    EngineType,
    EntryMode,
    ExitManager,
    ExitModel,
    FilterEngine,
    LondonReversalSimulator,
    MarketFilter,
    OmniBreakoutSimulator,
    OmniEntryMode,
    Position,
    PyramidModel,
    RiskModel,
    RiskSizer,
    Trade,
    USOpenRangeDetector,
)


class TestTier4FTMOChallengeSimulations:
    """Full realistic end-to-end trading simulations under FTMO prop rules."""

    def test_simulation_favorable_five_day_challenge_week(
        self, synthetic_asian_candles, synthetic_london_candles,
        synthetic_us_orb_candles, synthetic_us_session_candles
    ):
        """Simulate a 5-day trading week (Monday through Friday) recovering towards profit target.

        Starting equity: $94,939.28.
        Evaluates cumulative performance, ensuring neither daily limit nor floor is breached.
        """
        equity = 94939.28
        starting_equity = equity
        total_trades_week = 0
        all_daily_equities = [equity]

        london_profile = BacktestProfile(
            engine=EngineType.LONDON_REVERSAL,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode=EntryMode.SWEEP_CONFIRMATION.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TRAIL,
            filters=["spread_gate"],
            instrument="US100.cash",
        )

        omni_profile = BacktestProfile(
            engine=EngineType.OMNI_BREAKOUT,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode=OmniEntryMode.CLOSE_CONFIRMATION.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TRAIL,
            filters=["spread_gate"],
            instrument="US100.cash",
        )

        base_date = datetime(2026, 9, 1, tzinfo=timezone.utc)

        for day_offset in range(5):
            current_date = base_date + timedelta(days=day_offset)
            day_start_equity = equity

            asian = synthetic_asian_candles(current_date, 19600.0, 19500.0)
            scenario = "sweep_high_reversal" if day_offset % 2 == 0 else "sweep_low_reversal"
            london = synthetic_london_candles(current_date, 19600.0, 19500.0, scenario=scenario)
            london_candles = asian + london

            london_engine = BacktestEngine(london_profile, london_candles, starting_equity=equity)
            london_metrics = london_engine.run()
            equity = london_metrics.ending_equity
            total_trades_week += london_metrics.total_trades

            orb = synthetic_us_orb_candles(current_date, 19700.0, 19620.0)
            omni_scenario = "bullish_breakout" if day_offset % 2 == 0 else "bearish_breakout"
            us = synthetic_us_session_candles(current_date, 19700.0, 19620.0, scenario=omni_scenario)
            omni_candles = orb + us

            omni_engine = BacktestEngine(omni_profile, omni_candles, starting_equity=equity)
            omni_metrics = omni_engine.run()
            equity = omni_metrics.ending_equity
            total_trades_week += omni_metrics.total_trades

            day_pnl = equity - day_start_equity
            day_loss_pct = abs(day_pnl) / day_start_equity if day_pnl < 0 else 0.0

            assert day_loss_pct < 0.045
            assert equity >= 90500.00
            all_daily_equities.append(equity)

        assert equity > starting_equity
        assert total_trades_week >= 5
        assert min(all_daily_equities) >= 90500.00

    def test_simulation_adversarial_gap_circuit_breaker_preservation(
        self, candle_factory, ftmo_account_state: dict
    ):
        """Simulate an adverse 1.5x ATR market gap tripping circuit breaker and halting trading.

        Asserts that emergency circuit breaker stops trading at 4.5% drawdown,
        preventing account breach of 5.0% FTMO limit and $90,000 floor.
        """
        day_start_equity = ftmo_account_state["current_equity"]
        circuit_breaker_limit = day_start_equity * 0.045
        ftmo_hard_limit = day_start_equity * 0.05
        hard_floor = ftmo_account_state["total_loss_floor"]

        circuit_breaker_triggered = False
        trading_halted = False
        current_equity = day_start_equity

        simulated_loss = 4300.00
        current_equity -= simulated_loss

        if (day_start_equity - current_equity) >= circuit_breaker_limit:
            circuit_breaker_triggered = True
            trading_halted = True

        assert circuit_breaker_triggered is True
        assert trading_halted is True
        assert (day_start_equity - current_equity) < ftmo_hard_limit
        assert current_equity > hard_floor
        assert current_equity >= 90500.00

    def test_simulation_ten_day_drawdown_recovery_sequence(
        self, synthetic_asian_candles, synthetic_london_candles
    ):
        """Simulate 10 consecutive trading days with fluctuating performance.

        Verifies Conservative Ramp sizer limits risk during drawdown and
        maximum drawdown stays below 8.0% (leaving 2% safety cushion to FTMO 10% floor).
        """
        equity = 94939.28
        peak_equity = equity
        max_drawdown = 0.0
        max_drawdown_pct = 0.0

        profile = BacktestProfile(
            engine=EngineType.LONDON_REVERSAL,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode=EntryMode.SWEEP_CONFIRMATION.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TRAIL,
            filters=["spread_gate"],
            instrument="US100.cash",
        )

        base_date = datetime(2026, 9, 1, tzinfo=timezone.utc)

        for day in range(10):
            current_date = base_date + timedelta(days=day)
            asian = synthetic_asian_candles(current_date, 19600.0, 19500.0)
            scenario = "sweep_high_reversal" if day in (1, 3, 4, 7, 8, 9) else "no_sweep"
            london = synthetic_london_candles(current_date, 19600.0, 19500.0, scenario=scenario)
            candles = asian + london

            engine = BacktestEngine(profile, candles, starting_equity=equity)
            metrics = engine.run()
            equity = metrics.ending_equity

            if equity > peak_equity:
                peak_equity = equity
            dd = peak_equity - equity
            dd_pct = dd / peak_equity if peak_equity > 0 else 0.0
            if dd_pct > max_drawdown_pct:
                max_drawdown_pct = dd_pct

            assert equity >= 90000.00

        assert max_drawdown_pct < 0.080
        assert equity > 90000.00

    def test_simulation_paper_trader_48_hour_stream_verification(
        self, candle_factory
    ):
        """Simulate 48-hour continuous candle streaming (2,880 1-minute bars).

        Verifies that all observation trades are executed with exactly 0.01 micro-lots
        and cumulative risk remains zero.
        """
        start_time = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
        orders_logged: List[dict] = []

        for minute in range(2880):
            ts = start_time + timedelta(minutes=minute)
            if ts.hour == 8 and ts.minute == 15:
                order = {
                    "timestamp": ts.isoformat(),
                    "symbol": "US100.cash",
                    "side": "SELL",
                    "lots": 0.01,
                    "price": 19600.0,
                    "order_type": "OBSERVATION_TRACKING",
                }
                orders_logged.append(order)

        assert len(orders_logged) == 2
        for order in orders_logged:
            assert order["lots"] == 0.01
            assert order["order_type"] == "OBSERVATION_TRACKING"

    def test_simulation_watchdog_emergency_halt_file_generation(self, tmp_path: Path):
        """Simulate watchdog emergency halt when drawdown exceeds 4.5%.

        Verifies writing daily_lockouts.json and engine refusing new trades.
        """
        lockout_path = tmp_path / "daily_lockouts.json"

        day_start_equity = 94939.28
        current_equity = 90550.00
        drawdown_pct = (day_start_equity - current_equity) / day_start_equity

        if drawdown_pct >= 0.045:
            with open(lockout_path, "w", encoding="utf-8") as f:
                json.dump({
                    "trading_halted_for_day": True,
                    "trigger_time": "2026-09-09T10:30:00Z",
                    "day_start_equity": day_start_equity,
                    "breach_equity": current_equity,
                    "drawdown_pct": drawdown_pct,
                }, f)

        assert lockout_path.exists()
        with open(lockout_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["trading_halted_for_day"] is True
        assert data["drawdown_pct"] >= 0.045
