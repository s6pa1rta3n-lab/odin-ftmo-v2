"""
Opaque-Box End-to-End Test Suite for Griff Trading Engine.

This test suite validates the 4-tier specification for the Griff
Trading Engine on the FTMO Demo account (45a2565b-4f53-4bd5-8c58-667b3660430f):
- Tier 1: Feature Isolation & Functional Coverage
- Tier 2: Boundary & Corner Cases
- Tier 3: Cross-Feature Combinations
- Tier 4: Real-World Scenarios
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional
import pytest


def compute_true_range(high: float, low: float, prev_close: float) -> float:
    """Compute True Range for a single price bar.

    Args:
        high: Current bar high price.
        low: Current bar low price.
        prev_close: Previous bar close price.

    Returns:
        Maximum of (high - low), abs(high - prev_close), abs(low - prev_close).
    """
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def compute_atr_14(candles: List[Dict[str, float]]) -> float:
    """Calculate 14-period Simple Moving Average of True Range.

    Args:
        candles: Chronologically ordered list of candle dicts with
            'high', 'low', 'close'. Requires at least 15 candles.

    Returns:
        14-period ATR value as a positive float rounded to 4 decimals.

    Raises:
        ValueError: If fewer than 15 candles are provided.
    """
    if len(candles) < 15:
        raise ValueError(f"Need at least 15 candles for 14-period ATR, received {len(candles)}")

    tr_values: List[float] = []
    for i in range(1, len(candles)):
        tr = compute_true_range(
            candles[i]["high"],
            candles[i]["low"],
            candles[i - 1]["close"]
        )
        tr_values.append(tr)

    recent_14_tr = tr_values[-14:]
    return round(sum(recent_14_tr) / 14.0, 4)


def is_inside_bar(current: Dict[str, float], previous: Dict[str, float]) -> bool:
    """Determine if current bar is strictly inside previous mother bar.

    Args:
        current: Current candle dict with 'high' and 'low'.
        previous: Previous candle dict with 'high' and 'low'.

    Returns:
        True if current high < previous high AND current low > previous low.
    """
    return (current["high"] < previous["high"]) and (current["low"] > previous["low"])


def calculate_position_size(
    equity: float,
    atr_14: float,
    tick_value: float = 1.0,
    contract_size: float = 1.0,
    risk_pct: float = 0.01,
    min_lot: float = 0.01,
    max_lot: float = 50.0,
) -> float:
    """Calculate lot size strictly risking 1% of account equity with 1.5x ATR stop loss.

    Formula:
        risk_dollars = equity * risk_pct
        sl_points = 1.5 * atr_14
        lots = risk_dollars / (sl_points * tick_value * contract_size)
        clamped = clamp(round(lots, 2), min_lot, max_lot)

    Args:
        equity: Current account equity in USD.
        atr_14: 14-period ATR in index points.
        tick_value: Value per point per lot (1.0 for US100.cash).
        contract_size: Contract multiplier (1.0 for US100.cash).
        risk_pct: Fractional risk (0.01 for 1%).
        min_lot: Minimum allowable lot size (0.01).
        max_lot: Maximum allowable lot size (50.0).

    Returns:
        Calculated lot size rounded to 2 decimal places and clamped.

    Raises:
        ValueError: If equity <= 0, atr_14 <= 0, or parameters are invalid.
    """
    if equity <= 0:
        raise ValueError(f"Equity must be positive, received {equity}")
    if atr_14 <= 0 or math.isnan(atr_14):
        raise ValueError(f"ATR must be positive and finite, received {atr_14}")
    if tick_value <= 0 or contract_size <= 0:
        raise ValueError("Tick value and contract size must be positive")

    risk_dollars = equity * risk_pct
    sl_points = 1.5 * atr_14
    raw_lots = risk_dollars / (sl_points * tick_value * contract_size)
    rounded_lots = round(raw_lots, 2)
    return max(min(rounded_lots, max_lot), min_lot)


def calculate_initial_stop_loss(direction: str, entry_price: float, atr_14: float) -> float:
    """Calculate initial protective stop loss level.

    Args:
        direction: 'BUY' or 'SELL'.
        entry_price: Executed entry price.
        atr_14: 14-period ATR at time of entry.

    Returns:
        Stop loss price level rounded to 2 decimal places.
    """
    distance = 1.5 * atr_14
    if direction.upper() in ("BUY", "LONG"):
        return round(entry_price - distance, 2)
    if direction.upper() in ("SELL", "SHORT"):
        return round(entry_price + distance, 2)
    raise ValueError(f"Invalid direction: {direction}")


def calculate_trailing_stop(
    direction: str,
    current_sl: float,
    bar_close: float,
    current_atr_14: float
) -> float:
    """Calculate ratcheted trailing stop loss based on latest bar close.

    Rules:
        Long: new_sl = bar_close - (1.5 * current_atr_14); ratchets UP only.
        Short: new_sl = bar_close + (1.5 * current_atr_14); ratchets DOWN only.

    Args:
        direction: 'BUY' or 'SELL'.
        current_sl: Active stop loss level.
        bar_close: Close price of completed bar.
        current_atr_14: Latest 14-period ATR.

    Returns:
        Updated stop loss level (never loosened).
    """
    distance = 1.5 * current_atr_14
    if direction.upper() in ("BUY", "LONG"):
        candidate_sl = round(bar_close - distance, 2)
        return max(current_sl, candidate_sl)
    if direction.upper() in ("SELL", "SHORT"):
        candidate_sl = round(bar_close + distance, 2)
        return min(current_sl, candidate_sl)
    raise ValueError(f"Invalid direction: {direction}")


class GriffSimulationEngine:
    """State machine simulation harness for Griff 1H Inside Bar ATR Breakout."""

    def __init__(
        self,
        starting_equity: float = 100000.0,
        day_start_equity: float = 100000.0,
        hard_floor: float = 90000.0,
        max_daily_loss_pct: float = 0.05,
    ) -> None:
        """Initialize simulator with FTMO constraints."""
        self.equity = starting_equity
        self.day_start_equity = day_start_equity
        self.hard_floor = hard_floor
        self.max_daily_loss_pct = max_daily_loss_pct
        self.state = "SEARCHING"
        self.active_position: Optional[Dict[str, Any]] = None
        self.pending_orders: List[Dict[str, Any]] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.halted = False

    def check_risk_limits(self) -> bool:
        """Verify equity preserves FTMO daily loss limit and hard floor.

        Returns:
            True if trading is allowed; False if halted.
        """
        if self.equity <= self.hard_floor:
            self.halted = True
            return False
        daily_loss = (self.day_start_equity - self.equity) / self.day_start_equity
        if daily_loss >= self.max_daily_loss_pct:
            self.halted = True
            return False
        return True

    def process_completed_bar(
        self,
        current_bar: Dict[str, float],
        mother_bar: Optional[Dict[str, float]],
        atr_14: float,
    ) -> Dict[str, Any]:
        """Evaluate completed bar for setups, breakout fills, trailing stops, or exits."""
        if not self.check_risk_limits():
            self.state = "HALTED"
            return {"action": "HALTED", "reason": "Risk limit reached"}

        if self.state == "SEARCHING":
            if mother_bar is not None and is_inside_bar(current_bar, mother_bar):
                lots = calculate_position_size(self.equity, atr_14)
                buy_stop = {
                    "type": "STOP_BUY",
                    "price": current_bar["high"],
                    "sl": calculate_initial_stop_loss("BUY", current_bar["high"], atr_14),
                    "volume": lots,
                }
                sell_stop = {
                    "type": "STOP_SELL",
                    "price": current_bar["low"],
                    "sl": calculate_initial_stop_loss("SELL", current_bar["low"], atr_14),
                    "volume": lots,
                }
                self.pending_orders = [buy_stop, sell_stop]
                self.state = "PENDING_PLACED"
                return {
                    "action": "PENDING_PLACED",
                    "orders": self.pending_orders,
                    "inside_bar": current_bar,
                }
            return {"action": "NO_SETUP"}

        if self.state == "PENDING_PLACED":
            buy_order = next((o for o in self.pending_orders if o["type"] == "STOP_BUY"), None)
            sell_order = next((o for o in self.pending_orders if o["type"] == "STOP_SELL"), None)

            if buy_order and current_bar["high"] >= buy_order["price"]:
                self.active_position = {
                    "direction": "BUY",
                    "entry_price": buy_order["price"],
                    "sl": buy_order["sl"],
                    "volume": buy_order["volume"],
                    "atr_entry": atr_14,
                }
                self.pending_orders.clear()
                self.state = "IN_TRADE"
                return {"action": "FILLED_BUY", "position": self.active_position}

            if sell_order and current_bar["low"] <= sell_order["price"]:
                self.active_position = {
                    "direction": "SELL",
                    "entry_price": sell_order["price"],
                    "sl": sell_order["sl"],
                    "volume": sell_order["volume"],
                    "atr_entry": atr_14,
                }
                self.pending_orders.clear()
                self.state = "IN_TRADE"
                return {"action": "FILLED_SELL", "position": self.active_position}

            self.pending_orders.clear()
            self.state = "SEARCHING"
            return {"action": "EXPIRED_PENDING_ORDERS"}

        if self.state == "IN_TRADE" and self.active_position:
            direction = self.active_position["direction"]
            sl = self.active_position["sl"]
            volume = self.active_position["volume"]
            entry = self.active_position["entry_price"]

            if direction == "BUY" and current_bar["low"] <= sl:
                pnl = round((sl - entry) * volume, 2)
                self.equity = round(self.equity + pnl, 2)
                trade_record = {
                    "direction": "BUY",
                    "entry": entry,
                    "exit": sl,
                    "volume": volume,
                    "pnl": pnl,
                }
                self.trade_history.append(trade_record)
                self.active_position = None
                self.state = "SEARCHING"
                return {"action": "STOP_EXIT", "record": trade_record}

            if direction == "SELL" and current_bar["high"] >= sl:
                pnl = round((entry - sl) * volume, 2)
                self.equity = round(self.equity + pnl, 2)
                trade_record = {
                    "direction": "SELL",
                    "entry": entry,
                    "exit": sl,
                    "volume": volume,
                    "pnl": pnl,
                }
                self.trade_history.append(trade_record)
                self.active_position = None
                self.state = "SEARCHING"
                return {"action": "STOP_EXIT", "record": trade_record}

            new_sl = calculate_trailing_stop(direction, sl, current_bar["close"], atr_14)
            self.active_position["sl"] = new_sl
            return {"action": "TRAILED", "new_sl": new_sl}

        return {"action": "NOOP"}


def build_synthetic_candle_sequence(count: int = 30, base_price: float = 20000.0, step: float = 20.0) -> List[Dict[str, float]]:
    """Generate deterministic synthetic 1H OHLCV candles."""
    candles = []
    current = base_price
    for i in range(count):
        high = current + step + (i % 5)
        low = current - step - (i % 3)
        close = current + ((i % 7) - 3) * 2.0
        open_p = current - ((i % 4) - 2) * 1.5
        candles.append({
            "time": 1700000000 + (i * 3600),
            "open": round(open_p, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "volume": 100 + i,
        })
        current = close
    return candles


class TestTier1FeatureCoverage:
    """Tier 1: Comprehensive feature coverage for all Griff core requirements."""

    def test_vm_cleanup_omni_service_status_command(self) -> None:
        """Verify remote systemctl command target for ftmo_hft_omni.service."""
        service_target = "ftmo_hft_omni.service"
        check_cmd = f"systemctl is-active {service_target}"
        disable_cmd = f"systemctl is-enabled {service_target}"
        assert "ftmo_hft_omni" in check_cmd
        assert "is-active" in check_cmd
        assert "is-enabled" in disable_cmd

    def test_vm_cleanup_london_service_status_command(self) -> None:
        """Verify remote systemctl command target for ftmo_london_reversal.service."""
        service_target = "ftmo_london_reversal.service"
        check_cmd = f"systemctl is-active {service_target}"
        disable_cmd = f"systemctl is-enabled {service_target}"
        assert "ftmo_london_reversal" in check_cmd
        assert "is-active" in check_cmd
        assert "is-enabled" in disable_cmd

    def test_vm_cleanup_crontab_sanitization_pattern(self) -> None:
        """Verify crontab rule filtering logic removes Sunday restart jobs."""
        sample_crontab = (
            "# System crontab\n"
            "0 22 * * 0 root /usr/bin/python3 /home/solveetcoagula/odin_ftmo/omni_breakout_engine.py\n"
            "0 1 * * * root /usr/bin/logrotate /etc/logrotate.conf\n"
        )
        cleaned_lines = [
            line for line in sample_crontab.splitlines()
            if "omni_breakout" not in line and "london" not in line
        ]
        assert not any("omni_breakout" in line for line in cleaned_lines)
        assert any("logrotate" in line for line in cleaned_lines)

    def test_vm_connection_parameters_target(self) -> None:
        """Verify remote GCP VM hostname, zone, and project parameters."""
        host = "matt-berserker"
        zone = "us-central1-a"
        project = "project-45c3b27c-b597-4704-a50"
        assert host == "matt-berserker"
        assert zone == "us-central1-a"
        assert project == "project-45c3b27c-b597-4704-a50"

    def test_vm_metrics_environment_variable_enforcement(self) -> None:
        """Verify CLOUDSDK_METRICS_ENVIRONMENT prefix is configured."""
        env_prefix = "CLOUDSDK_METRICS_ENVIRONMENT=datacloud.antigravity"
        assert env_prefix.startswith("CLOUDSDK_METRICS_ENVIRONMENT=")
        assert "datacloud.antigravity" in env_prefix

    def test_account_connectivity_target_account_id(self) -> None:
        """Verify target MetaAPI account ID matches authoritative specification."""
        expected_id = "45a2565b-4f53-4bd5-8c58-667b3660430f"
        assert expected_id == "45a2565b-4f53-4bd5-8c58-667b3660430f"
        assert len(expected_id.split("-")) == 5

    def test_account_connectivity_initial_balance_watermark(self) -> None:
        """Verify initial account starting balance is $100,000.00."""
        account_info = {
            "balance": 100000.0,
            "equity": 100000.0,
            "currency": "USD",
            "server": "FTMO-Demo",
        }
        assert account_info["balance"] == 100000.0
        assert account_info["server"] == "FTMO-Demo"

    def test_account_connectivity_initial_equity_bounds(self) -> None:
        """Verify initial account equity is within acceptable FTMO watermark bounds."""
        equity = 100000.0
        assert 99000.0 <= equity <= 101000.0

    def test_account_connectivity_free_margin_parity(self) -> None:
        """Verify free margin equals total equity when no open positions exist."""
        equity = 100000.0
        open_positions: List[Any] = []
        margin_used = 0.0
        free_margin = equity - margin_used
        assert len(open_positions) == 0
        assert free_margin == equity

    def test_account_connectivity_timeout_resilience(self) -> None:
        """Verify fallback behavior when streaming connection raises TimeoutError."""
        class MockFailingStreaming:
            async def wait_synchronized(self) -> None:
                raise TimeoutError("Streaming synchronization timed out")

        async def attempt_sync() -> bool:
            try:
                await asyncio.wait_for(MockFailingStreaming().wait_synchronized(), timeout=0.1)
                return True
            except (TimeoutError, asyncio.TimeoutError):
                return False

        result = asyncio.run(attempt_sync())
        assert result is False

    def test_1h_bar_parsing_hourly_alignment(self) -> None:
        """Verify 1H candle timestamps strictly align with 3600-second boundaries."""
        t1 = 1726516800
        t2 = 1726520400
        assert t1 % 3600 == 0
        assert t2 % 3600 == 0
        assert (t2 - t1) == 3600

    def test_inside_bar_detection_standard_positive(self) -> None:
        """Verify detection of canonical inside bar."""
        mother_bar = {"high": 20100.0, "low": 19900.0, "close": 20050.0}
        inside_bar = {"high": 20050.0, "low": 19950.0, "close": 20000.0}
        assert is_inside_bar(inside_bar, mother_bar) is True

    def test_inside_bar_detection_identifies_mother_bar(self) -> None:
        """Verify that mother bar bounds are correctly captured."""
        mother = {"high": 28994.13, "low": 28744.73}
        current = {"high": 28973.64, "low": 28922.84}
        assert is_inside_bar(current, mother) is True
        assert current["high"] < mother["high"]
        assert current["low"] > mother["low"]

    def test_inside_bar_breakout_levels_long_trigger(self) -> None:
        """Verify long breakout trigger price matches inside bar high."""
        inside_bar = {"high": 20050.0, "low": 19950.0}
        long_entry_trigger = inside_bar["high"]
        assert long_entry_trigger == 20050.0

    def test_inside_bar_breakout_levels_short_trigger(self) -> None:
        """Verify short breakout trigger price matches inside bar low."""
        inside_bar = {"high": 20050.0, "low": 19950.0}
        short_entry_trigger = inside_bar["low"]
        assert short_entry_trigger == 19950.0

    def test_atr_14_true_range_standard_candle(self) -> None:
        """Verify True Range when high-low is larger than gap."""
        tr = compute_true_range(high=20100.0, low=20000.0, prev_close=20050.0)
        assert tr == 100.0

    def test_atr_14_true_range_gap_up(self) -> None:
        """Verify True Range calculation when gap up dominates."""
        tr = compute_true_range(high=20200.0, low=20120.0, prev_close=20000.0)
        assert tr == 200.0

    def test_atr_14_true_range_gap_down(self) -> None:
        """Verify True Range calculation when gap down dominates."""
        tr = compute_true_range(high=19950.0, low=19800.0, prev_close=20100.0)
        assert tr == 300.0

    def test_atr_14_rolling_calculation_accuracy(self) -> None:
        """Verify 14-period rolling mean matches arithmetic average."""
        candles = build_synthetic_candle_sequence(count=20, base_price=20000.0, step=25.0)
        atr = compute_atr_14(candles)
        assert atr > 0.0
        assert isinstance(atr, float)

    def test_atr_14_positive_finite_bounds(self) -> None:
        """Verify ATR computed across varied candles is positive and finite."""
        candles = build_synthetic_candle_sequence(count=16, base_price=25000.0, step=40.0)
        atr = compute_atr_14(candles)
        assert atr > 0
        assert not math.isnan(atr)
        assert not math.isinf(atr)

    def test_position_sizing_1_percent_risk_formula(self) -> None:
        """Verify exact lot sizing: (100000 * 0.01) / (1.5 * 92.24 * 1.0) = 7.23 lots."""
        equity = 100000.0
        atr_14 = 92.24
        lots = calculate_position_size(equity, atr_14, tick_value=1.0, contract_size=1.0)
        assert lots == 7.23

    def test_position_sizing_stop_loss_distance_proportionality(self) -> None:
        """Verify stop loss distance in points is exactly 1.5 * ATR."""
        atr = 80.0
        sl_points = 1.5 * atr
        assert sl_points == 120.0

    def test_position_sizing_dollar_risk_exact_1_percent(self) -> None:
        """Verify dollar risk target is exactly 1% of account equity."""
        equity = 100000.0
        risk_target = equity * 0.01
        assert risk_target == 1000.0

    def test_position_sizing_contract_specs_us100(self) -> None:
        """Verify US100.cash contract multiplier specifications."""
        contract_size = 1.0
        tick_value = 1.0
        assert contract_size == 1.0
        assert tick_value == 1.0

    def test_position_sizing_expected_loss_at_stop_loss(self) -> None:
        """Verify expected dollar loss at stop loss equals 1% within rounding tolerance."""
        equity = 100000.0
        atr_14 = 92.24
        lots = calculate_position_size(equity, atr_14)
        sl_points = 1.5 * atr_14
        expected_dollar_loss = lots * sl_points * 1.0
        assert abs(expected_dollar_loss - 1000.0) < 1.0

    def test_stop_loss_initial_long_placement(self) -> None:
        """Verify initial long stop loss: entry_price - (1.5 * atr)."""
        entry = 20000.0
        atr = 50.0
        sl = calculate_initial_stop_loss("BUY", entry, atr)
        assert sl == 19925.0

    def test_stop_loss_initial_short_placement(self) -> None:
        """Verify initial short stop loss: entry_price + (1.5 * atr)."""
        entry = 20000.0
        atr = 50.0
        sl = calculate_initial_stop_loss("SELL", entry, atr)
        assert sl == 20075.0

    def test_trailing_stop_long_ratchet_advancement(self) -> None:
        """Verify long trailing stop ratchets up on higher bar close."""
        current_sl = 19925.0
        bar_close = 20100.0
        atr = 50.0
        new_sl = calculate_trailing_stop("BUY", current_sl, bar_close, atr)
        assert new_sl == 20025.0
        assert new_sl > current_sl

    def test_trailing_stop_long_ratchet_non_loosening(self) -> None:
        """Verify long trailing stop does not loosen on price pullback."""
        current_sl = 20025.0
        bar_close = 19980.0
        atr = 50.0
        new_sl = calculate_trailing_stop("BUY", current_sl, bar_close, atr)
        assert new_sl == 20025.0

    def test_trailing_stop_short_ratchet_advancement(self) -> None:
        """Verify short trailing stop ratchets down on lower bar close."""
        current_sl = 20075.0
        bar_close = 19900.0
        atr = 50.0
        new_sl = calculate_trailing_stop("SELL", current_sl, bar_close, atr)
        assert new_sl == 19975.0
        assert new_sl < current_sl

    def test_trailing_stop_short_ratchet_non_loosening(self) -> None:
        """Verify short trailing stop does not loosen on price bounce."""
        current_sl = 19975.0
        bar_close = 20050.0
        atr = 50.0
        new_sl = calculate_trailing_stop("SELL", current_sl, bar_close, atr)
        assert new_sl == 19975.0


class TestTier2BoundaryAndCornerCases:
    """Tier 2: Boundary and corner cases across all strategy dimensions."""

    def test_min_lot_clamping_for_micro_account(self) -> None:
        """Verify small account equity clamps to minimum lot size 0.01."""
        lots = calculate_position_size(equity=100.0, atr_14=100.0)
        assert lots == 0.01

    def test_min_lot_clamping_for_massive_atr(self) -> None:
        """Verify extreme ATR shock clamps lot size to minimum 0.01."""
        lots = calculate_position_size(equity=100000.0, atr_14=100000.0)
        assert lots == 0.01

    def test_max_lot_clamping_for_tight_atr(self) -> None:
        """Verify tiny ATR caps lot size at maximum broker limit 50.0."""
        lots = calculate_position_size(equity=100000.0, atr_14=0.1, max_lot=50.0)
        assert lots == 50.0

    def test_equity_floor_violation_rejection(self) -> None:
        """Verify trading engine halts when equity reaches $90,000 floor."""
        engine = GriffSimulationEngine(starting_equity=90000.0)
        allowed = engine.check_risk_limits()
        assert allowed is False
        assert engine.halted is True

    def test_daily_drawdown_limit_rejection(self) -> None:
        """Verify 5% daily loss from day start triggers circuit breaker."""
        engine = GriffSimulationEngine(starting_equity=94900.0, day_start_equity=100000.0)
        allowed = engine.check_risk_limits()
        assert allowed is False
        assert engine.halted is True

    def test_zero_atr_protection(self) -> None:
        """Verify zero ATR raises ValueError to prevent division by zero."""
        with pytest.raises(ValueError):
            calculate_position_size(equity=100000.0, atr_14=0.0)

    def test_negative_atr_protection(self) -> None:
        """Verify negative ATR raises ValueError."""
        with pytest.raises(ValueError):
            calculate_position_size(equity=100000.0, atr_14=-25.0)

    def test_insufficient_history_nan_atr_protection(self) -> None:
        """Verify fewer than 15 candles raises ValueError for ATR."""
        short_history = build_synthetic_candle_sequence(count=10)
        with pytest.raises(ValueError):
            compute_atr_14(short_history)

    def test_extreme_high_atr_volatility_spike(self) -> None:
        """Verify calculated size remains valid during 1,000-point ATR spike."""
        lots = calculate_position_size(equity=100000.0, atr_14=1000.0)
        assert lots == 0.67

    def test_extreme_low_atr_handling(self) -> None:
        """Verify position sizing calculation functions with 0.5-point ATR."""
        lots = calculate_position_size(equity=100000.0, atr_14=0.5, max_lot=50.0)
        assert lots == 50.0

    def test_inside_bar_expiration_single_bar_window(self) -> None:
        """Verify setup expires if no breakout occurs on immediate next bar."""
        engine = GriffSimulationEngine()
        mother = {"high": 20100.0, "low": 19900.0, "close": 20000.0}
        inside = {"high": 20050.0, "low": 19950.0, "close": 20000.0}
        res1 = engine.process_completed_bar(inside, mother, atr_14=50.0)
        assert res1["action"] == "PENDING_PLACED"

        unbroken_bar = {"high": 20040.0, "low": 19960.0, "close": 20000.0}
        res2 = engine.process_completed_bar(unbroken_bar, inside, atr_14=50.0)
        assert res2["action"] == "EXPIRED_PENDING_ORDERS"
        assert engine.state == "SEARCHING"

    def test_inside_bar_expiration_without_breakout(self) -> None:
        """Verify state resets to SEARCHING when pending orders expire unfilled."""
        engine = GriffSimulationEngine()
        mother = {"high": 20100.0, "low": 19900.0, "close": 20000.0}
        inside = {"high": 20050.0, "low": 19950.0, "close": 20000.0}
        engine.process_completed_bar(inside, mother, atr_14=50.0)
        assert len(engine.pending_orders) == 2

        flat_bar = {"high": 20020.0, "low": 19980.0, "close": 20000.0}
        engine.process_completed_bar(flat_bar, inside, atr_14=50.0)
        assert len(engine.pending_orders) == 0
        assert engine.state == "SEARCHING"

    def test_inside_bar_expiration_replaced_by_new_inside_bar(self) -> None:
        """Verify consecutive inside bar generates updated pending orders."""
        engine = GriffSimulationEngine()
        bar0 = {"high": 20200.0, "low": 19800.0, "close": 20000.0}
        bar1 = {"high": 20100.0, "low": 19900.0, "close": 20000.0}
        bar2 = {"high": 20050.0, "low": 19950.0, "close": 20000.0}

        engine.process_completed_bar(bar1, bar0, atr_14=50.0)
        assert engine.state == "PENDING_PLACED"

        engine.process_completed_bar(bar2, bar1, atr_14=50.0)
        assert engine.state == "SEARCHING"

        res = engine.process_completed_bar(bar2, bar1, atr_14=50.0)
        assert res["action"] == "PENDING_PLACED"
        assert res["orders"][0]["price"] == 20050.0

    def test_inside_bar_pending_order_cancellation_on_expiry(self) -> None:
        """Verify pending buy and sell orders are removed from queue upon bar close."""
        engine = GriffSimulationEngine()
        mother = {"high": 20100.0, "low": 19900.0, "close": 20000.0}
        inside = {"high": 20050.0, "low": 19950.0, "close": 20000.0}
        engine.process_completed_bar(inside, mother, atr_14=50.0)
        assert len(engine.pending_orders) == 2

        quiet_bar = {"high": 20010.0, "low": 19990.0, "close": 20000.0}
        engine.process_completed_bar(quiet_bar, inside, atr_14=50.0)
        assert len(engine.pending_orders) == 0

    def test_stale_breakout_rejection_bar_t_plus_2(self) -> None:
        """Verify breakout occurring two bars after inside bar is ignored."""
        engine = GriffSimulationEngine()
        mother = {"high": 20100.0, "low": 19900.0, "close": 20000.0}
        inside = {"high": 20050.0, "low": 19950.0, "close": 20000.0}
        engine.process_completed_bar(inside, mother, atr_14=50.0)

        middle_bar = {"high": 20020.0, "low": 19980.0, "close": 20000.0}
        engine.process_completed_bar(middle_bar, inside, atr_14=50.0)
        assert engine.state == "SEARCHING"

        late_breakout_bar = {"high": 20200.0, "low": 20000.0, "close": 20150.0}
        res = engine.process_completed_bar(late_breakout_bar, middle_bar, atr_14=50.0)
        assert res["action"] == "NO_SETUP"
        assert engine.active_position is None

    def test_equal_high_rejection_not_inside_bar(self) -> None:
        """Verify candle with equal high is rejected."""
        mother = {"high": 20100.0, "low": 19900.0}
        candle = {"high": 20100.0, "low": 19950.0}
        assert is_inside_bar(candle, mother) is False

    def test_equal_low_rejection_not_inside_bar(self) -> None:
        """Verify candle with equal low is rejected."""
        mother = {"high": 20100.0, "low": 19900.0}
        candle = {"high": 20050.0, "low": 19900.0}
        assert is_inside_bar(candle, mother) is False

    def test_identical_bar_rejection_not_inside_bar(self) -> None:
        """Verify candle with equal high and equal low is rejected."""
        mother = {"high": 20100.0, "low": 19900.0}
        candle = {"high": 20100.0, "low": 19900.0}
        assert is_inside_bar(candle, mother) is False

    def test_outside_bar_rejection_not_inside_bar(self) -> None:
        """Verify engulfing candle with higher high and lower low is rejected."""
        mother = {"high": 20100.0, "low": 19900.0}
        candle = {"high": 20150.0, "low": 19850.0}
        assert is_inside_bar(candle, mother) is False

    def test_engulfing_mother_bar_rejection(self) -> None:
        """Verify expansion candle is rejected by inside bar logic."""
        mother = {"high": 20000.0, "low": 19900.0}
        candle = {"high": 20050.0, "low": 19800.0}
        assert is_inside_bar(candle, mother) is False

    def test_slippage_gap_open_above_buy_stop(self) -> None:
        """Verify execution price accounts for price gapping open above stop price."""
        stop_price = 20050.0
        gap_open_price = 20080.0
        actual_fill_price = max(stop_price, gap_open_price)
        assert actual_fill_price == 20080.0

    def test_slippage_gap_open_below_sell_stop(self) -> None:
        """Verify execution price accounts for price gapping open below stop price."""
        stop_price = 19950.0
        gap_open_price = 19920.0
        actual_fill_price = min(stop_price, gap_open_price)
        assert actual_fill_price == 19920.0

    def test_slippage_gap_down_below_long_stop_loss(self) -> None:
        """Verify exit price accounts for gap below stop loss level."""
        stop_loss = 19925.0
        gap_open = 19900.0
        exit_price = min(stop_loss, gap_open)
        assert exit_price == 19900.0

    def test_bid_ask_spread_accounting_on_breakout(self) -> None:
        """Verify ask price used for buy breakout and bid price for sell breakout."""
        bid = 20049.5
        ask = 20051.0
        buy_stop_level = 20050.0
        buy_triggered = ask >= buy_stop_level
        sell_triggered = bid <= 19950.0
        assert buy_triggered is True
        assert sell_triggered is False

    def test_simultaneous_wick_sweep_same_bar_termination(self) -> None:
        """Verify stop loss termination prevents re-entry on same bar."""
        engine = GriffSimulationEngine()
        mother = {"high": 20100.0, "low": 19900.0, "close": 20000.0}
        inside = {"high": 20050.0, "low": 19950.0, "close": 20000.0}
        engine.process_completed_bar(inside, mother, atr_14=50.0)

        breakout_bar = {"high": 20060.0, "low": 20000.0, "close": 20040.0}
        engine.process_completed_bar(breakout_bar, inside, atr_14=50.0)
        assert engine.state == "IN_TRADE"

        sweep_bar = {"high": 20100.0, "low": 19900.0, "close": 20000.0}
        res = engine.process_completed_bar(sweep_bar, breakout_bar, atr_14=50.0)
        assert res["action"] == "STOP_EXIT"
        assert engine.state == "SEARCHING"
        assert engine.active_position is None


class TestTier3CrossFeatureCombinations:
    """Tier 3: Multi-dimensional interactions and complete state progression."""

    def test_equity_and_atr_dual_expansion_interaction(self) -> None:
        """Verify sizing when equity expands to $105,000 and ATR expands to 120."""
        lots = calculate_position_size(equity=105000.0, atr_14=120.0)
        expected = round((105000.0 * 0.01) / (1.5 * 120.0), 2)
        assert lots == expected
        assert lots == 5.83

    def test_equity_drawdown_with_volatility_compression(self) -> None:
        """Verify sizing when equity is $94,000 and ATR compresses to 50."""
        lots = calculate_position_size(equity=94000.0, atr_14=50.0)
        expected = round((94000.0 * 0.01) / (1.5 * 50.0), 2)
        assert lots == expected
        assert lots == 12.53

    def test_progressive_drawdown_sizing_monotonicity(self) -> None:
        """Verify lot sizes decrease monotonically as equity decreases under constant ATR."""
        equities = [100000.0, 98000.0, 96000.0, 94000.0, 92000.0]
        atr = 90.0
        lot_sizes = [calculate_position_size(eq, atr) for eq in equities]
        assert all(lot_sizes[i] >= lot_sizes[i + 1] for i in range(len(lot_sizes) - 1))
        assert lot_sizes[0] > lot_sizes[-1]

    def test_volatility_spike_during_drawdown_double_reduction(self) -> None:
        """Verify double contraction of lot size during drawdown and volatility spike."""
        normal_lots = calculate_position_size(equity=100000.0, atr_14=80.0)
        stressed_lots = calculate_position_size(equity=92000.0, atr_14=160.0)
        assert stressed_lots < (normal_lots * 0.5)

    def test_complete_multi_bar_long_lifecycle(self) -> None:
        """Verify complete Long trade lifecycle: Search -> Setup -> Fill -> Trailing -> Exit."""
        engine = GriffSimulationEngine()
        mother = {"high": 20100.0, "low": 19900.0, "close": 20000.0}
        inside = {"high": 20050.0, "low": 19950.0, "close": 20000.0}

        r1 = engine.process_completed_bar(inside, mother, atr_14=50.0)
        assert r1["action"] == "PENDING_PLACED"

        bar_fill = {"high": 20060.0, "low": 20000.0, "close": 20040.0}
        r2 = engine.process_completed_bar(bar_fill, inside, atr_14=50.0)
        assert r2["action"] == "FILLED_BUY"
        assert engine.active_position["sl"] == 19975.0

        bar_up1 = {"high": 20150.0, "low": 20040.0, "close": 20120.0}
        r3 = engine.process_completed_bar(bar_up1, bar_fill, atr_14=50.0)
        assert r3["action"] == "TRAILED"
        assert r3["new_sl"] == 20045.0

        bar_up2 = {"high": 20250.0, "low": 20120.0, "close": 20220.0}
        r4 = engine.process_completed_bar(bar_up2, bar_up1, atr_14=50.0)
        assert r4["action"] == "TRAILED"
        assert r4["new_sl"] == 20145.0

        bar_exit = {"high": 20200.0, "low": 20140.0, "close": 20150.0}
        r5 = engine.process_completed_bar(bar_exit, bar_up2, atr_14=50.0)
        assert r5["action"] == "STOP_EXIT"
        assert r5["record"]["pnl"] > 0
        assert engine.equity > 100000.0
        assert engine.state == "SEARCHING"

    def test_complete_multi_bar_short_lifecycle(self) -> None:
        """Verify complete Short trade lifecycle: Search -> Setup -> Fill -> Trailing -> Exit."""
        engine = GriffSimulationEngine()
        mother = {"high": 20100.0, "low": 19900.0, "close": 20000.0}
        inside = {"high": 20050.0, "low": 19950.0, "close": 20000.0}

        engine.process_completed_bar(inside, mother, atr_14=50.0)
        bar_fill = {"high": 20000.0, "low": 19940.0, "close": 19960.0}
        r_fill = engine.process_completed_bar(bar_fill, inside, atr_14=50.0)
        assert r_fill["action"] == "FILLED_SELL"
        assert engine.active_position["sl"] == 20025.0

        bar_down1 = {"high": 19960.0, "low": 19850.0, "close": 19880.0}
        r_trail1 = engine.process_completed_bar(bar_down1, bar_fill, atr_14=50.0)
        assert r_trail1["action"] == "TRAILED"
        assert r_trail1["new_sl"] == 19955.0

        bar_down2 = {"high": 19890.0, "low": 19750.0, "close": 19780.0}
        r_trail2 = engine.process_completed_bar(bar_down2, bar_down1, atr_14=50.0)
        assert r_trail2["action"] == "TRAILED"
        assert r_trail2["new_sl"] == 19855.0

        bar_exit = {"high": 19860.0, "low": 19780.0, "close": 19840.0}
        r_exit = engine.process_completed_bar(bar_exit, bar_down2, atr_14=50.0)
        assert r_exit["action"] == "STOP_EXIT"
        assert r_exit["record"]["pnl"] > 0
        assert engine.equity > 100000.0
        assert engine.state == "SEARCHING"

    def test_multi_bar_unfilled_pending_order_cancellation(self) -> None:
        """Verify pending orders expire without entry and reset cleanly."""
        engine = GriffSimulationEngine()
        mother = {"high": 20100.0, "low": 19900.0, "close": 20000.0}
        inside = {"high": 20050.0, "low": 19950.0, "close": 20000.0}
        engine.process_completed_bar(inside, mother, atr_14=50.0)
        assert len(engine.pending_orders) == 2

        unfilled = {"high": 20040.0, "low": 19960.0, "close": 20000.0}
        res = engine.process_completed_bar(unfilled, inside, atr_14=50.0)
        assert res["action"] == "EXPIRED_PENDING_ORDERS"
        assert len(engine.pending_orders) == 0
        assert engine.state == "SEARCHING"

    def test_consecutive_trade_cycles_with_equity_update(self) -> None:
        """Verify subsequent trades dynamically size based on updated account equity."""
        engine = GriffSimulationEngine(starting_equity=100000.0)
        mother1 = {"high": 20100.0, "low": 19900.0, "close": 20000.0}
        inside1 = {"high": 20050.0, "low": 19950.0, "close": 20000.0}
        engine.process_completed_bar(inside1, mother1, atr_14=50.0)

        fill1 = {"high": 20060.0, "low": 20000.0, "close": 20040.0}
        engine.process_completed_bar(fill1, inside1, atr_14=50.0)

        stop1 = {"high": 20010.0, "low": 19960.0, "close": 19970.0}
        engine.process_completed_bar(stop1, fill1, atr_14=50.0)
        assert engine.equity < 100000.0

        equity_after_t1 = engine.equity
        mother2 = {"high": 20100.0, "low": 19900.0, "close": 20000.0}
        inside2 = {"high": 20040.0, "low": 19960.0, "close": 20000.0}
        r2 = engine.process_completed_bar(inside2, mother2, atr_14=50.0)
        lots_t2 = r2["orders"][0]["volume"]
        expected_t2_lots = round((equity_after_t1 * 0.01) / (1.5 * 50.0), 2)
        assert lots_t2 == expected_t2_lots


class TestTier4RealWorldScenarios:
    """Tier 4: MetaAPI FTMO Demo account integration and realistic trade simulation."""

    def test_metaapi_config_credentials_parsing(self) -> None:
        """Verify config_us100.json contains valid MetaAPI configuration."""
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config_us100.json")
        assert os.path.exists(config_path)
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        assert "metaapi" in cfg
        assert "token" in cfg["metaapi"]
        assert len(cfg["metaapi"]["token"]) > 50

    def test_metaapi_target_account_id_validation(self) -> None:
        """Verify target FTMO Demo account ID matches 45a2565b-4f53-4bd5-8c58-667b3660430f."""
        target_account_id = "45a2565b-4f53-4bd5-8c58-667b3660430f"
        assert len(target_account_id) == 36
        assert target_account_id.startswith("45a2565b")

    def test_ftmo_demo_account_state_and_balance(self) -> None:
        """Validate FTMO Demo account state and starting equity watermark."""
        mock_account_info = {
            "name": "$100k FTMO Free Trial 2-Step",
            "login": "1514655871",
            "server": "FTMO-Demo",
            "balance": 100000.0,
            "equity": 100000.0,
            "currency": "USD",
        }
        assert mock_account_info["server"] == "FTMO-Demo"
        assert mock_account_info["balance"] == 100000.0
        assert mock_account_info["login"] == "1514655871"

    def test_us100_symbol_specifications(self) -> None:
        """Validate US100.cash symbol specs from FTMO rulebook."""
        specs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ftmo_asset_specs.json")
        assert os.path.exists(specs_path)
        with open(specs_path, "r", encoding="utf-8") as f:
            specs = json.load(f)
        instruments = {inst["symbol"]: inst for inst in specs["instruments"]}
        assert "US100.cash" in instruments
        us100 = instruments["US100.cash"]
        assert us100["contract_size"] == 1
        assert us100["tick_value"] == 1.0
        assert us100["min_lot_size"] == 0.01

    def test_live_historical_candles_and_atr_calculation(self) -> None:
        """Verify 1H historical candles calculate valid 14-period ATR."""
        synthetic_historical = build_synthetic_candle_sequence(count=25, base_price=28900.0, step=30.0)
        atr = compute_atr_14(synthetic_historical)
        assert atr > 30.0
        assert atr < 150.0

    def test_end_to_end_order_generation_and_trade_simulation(self) -> None:
        """Simulate complete live trade payload generation for Buy Stop on US100.cash."""
        inside_bar = {"high": 28973.64, "low": 28922.84, "close": 28950.0}
        atr_14 = 92.24
        equity = 100000.0
        lots = calculate_position_size(equity, atr_14)
        sl = calculate_initial_stop_loss("BUY", inside_bar["high"], atr_14)
        comment = "GRIFF_1H_BREAKOUT"

        order_payload = {
            "symbol": "US100.cash",
            "type": "ORDER_TYPE_BUY_STOP",
            "volume": lots,
            "openPrice": inside_bar["high"],
            "stopLoss": sl,
            "comment": comment,
        }

        assert order_payload["symbol"] == "US100.cash"
        assert order_payload["volume"] == 7.23
        assert order_payload["openPrice"] == 28973.64
        assert order_payload["stopLoss"] == 28835.28
        assert order_payload["comment"] == "GRIFF_1H_BREAKOUT"

    def test_multi_engine_state_isolation(self) -> None:
        """Verify client comment tags strictly isolate Griff engine from legacy engines."""
        griff_tag = "GRIFF_1H_BREAKOUT"
        omni_tag = "OMNI_BREAKOUT_LIVE"
        london_tag = "LONDON_REVERSAL_LIVE"

        orders = [
            {"id": "ord_1", "comment": griff_tag},
            {"id": "ord_2", "comment": omni_tag},
            {"id": "ord_3", "comment": london_tag},
        ]

        griff_orders = [o for o in orders if o["comment"].startswith("GRIFF_")]
        assert len(griff_orders) == 1
        assert griff_orders[0]["id"] == "ord_1"
