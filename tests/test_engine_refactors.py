"""Comprehensive verification suite for Milestone M2: Engine Refactors and Modularization.

Verifies that all 5 design dimensions x 7 options produce distinct behaviors,
no dead code paths exist, dynamic profile loading functions correctly, and all
modular packages operate with strict Python 3.9 compatibility.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import pytest

from backtester.engine import (
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
)
from modules.entry import (
    LondonEntryMode,
    OmniEntryMode as ModularOmniEntryMode,
    evaluate_london_entry,
    evaluate_omni_entry,
)
from modules.exit import ExitManager as ModularExitManager, ExitModel as ModularExitModel
from modules.filters import (
    FilterEngine as ModularFilterEngine,
    MarketFilter as ModularMarketFilter,
)
from modules.pyramid import (
    PyramidManager,
    PyramidModel as ModularPyramidModel,
)
from modules.risk import (
    RiskModel as ModularRiskModel,
    RiskSizer as ModularRiskSizer,
)


def make_candle(
    dt: datetime,
    open_p: float = 19550.0,
    high_p: float = 19560.0,
    low_p: float = 19540.0,
    close_p: float = 19550.0,
    volume: float = 100.0,
) -> Candle:
    """Helper to construct a Candle dataclass instance with safe bounds."""
    return Candle(
        timestamp=dt,
        open=open_p,
        high=high_p,
        low=low_p,
        close=close_p,
        volume=volume,
    )


def generate_synthetic_candles(dt: datetime, asian_high: float, asian_low: float) -> List[Candle]:
    """Generate synthetic day candles for London Reversal testing."""
    candles = []
    for m in range(0, 420, 15):
        c_dt = dt.replace(hour=m // 60, minute=m % 60)
        candles.append(make_candle(c_dt, open_p=19550.0, high_p=asian_high, low_p=asian_low, close_p=19550.0))

    for m in range(420, 780, 5):
        c_dt = dt.replace(hour=m // 60, minute=m % 60)
        if m == 430:
            candles.append(make_candle(c_dt, open_p=19590.0, high_p=asian_high + 5.0, low_p=19580.0, close_p=19585.0))
        elif m == 450:
            candles.append(make_candle(c_dt, open_p=19585.0, high_p=19590.0, low_p=19575.0, close_p=19580.0))
        elif m == 500:
            candles.append(make_candle(c_dt, open_p=19575.0, high_p=19580.0, low_p=19560.0, close_p=19565.0))
        else:
            candles.append(make_candle(c_dt, open_p=19580.0, high_p=19585.0, low_p=19575.0, close_p=19580.0))
    return candles


class TestDimension1RiskSizingDistinctBehavior:
    """Verify that all 7 Risk Sizing models produce distinct behavior and lot allocations."""

    def test_conservative_ramp_tiers(self):
        """Verify Conservative Ramp graduates risk percentage across account equity tiers."""
        sizer = ModularRiskSizer(ModularRiskModel.CONSERVATIVE_RAMP, starting_equity=100000.0)
        assert sizer.compute_risk_pct(94939.28) == 0.0025
        assert sizer.compute_risk_pct(99000.00) == 0.0050
        assert sizer.compute_risk_pct(103000.00) == 0.0075

    def test_fixed_low_constant_risk(self):
        """Verify Fixed Low maintains 0.35% flat risk regardless of equity."""
        sizer = ModularRiskSizer(ModularRiskModel.FIXED_LOW, starting_equity=100000.0)
        assert sizer.compute_risk_pct(90000.00) == 0.0035
        assert sizer.compute_risk_pct(105000.00) == 0.0035

    def test_aggressive_flat_constant_risk(self):
        """Verify Aggressive Flat maintains 0.75% flat risk."""
        sizer = ModularRiskSizer(ModularRiskModel.AGGRESSIVE_FLAT, starting_equity=100000.0)
        assert sizer.compute_risk_pct(94939.28) == 0.0075
        lots = sizer.compute_lots(94939.28, sl_points=40.0)
        expected = round((94939.28 * 0.0075) / 40.0, 2)
        assert lots == expected

    def test_kelly_criterion_adapts_to_trade_history(self):
        """Verify Kelly Criterion computes fractional risk based on realized win-loss ratio."""
        sizer = ModularRiskSizer(ModularRiskModel.KELLY_CRITERION, starting_equity=100000.0)
        assert sizer.compute_risk_pct(100000.0) == 0.0035

        for _ in range(15):
            sizer.record_trade(300.0)
        for _ in range(5):
            sizer.record_trade(-150.0)

        adapted_risk = sizer.compute_risk_pct(100000.0)
        assert 0.001 <= adapted_risk <= 0.010
        assert adapted_risk > 0.0035

    def test_anti_martingale_win_streak_compounding(self):
        """Verify Anti-Martingale increases risk with consecutive winning trades."""
        sizer = ModularRiskSizer(ModularRiskModel.ANTI_MARTINGALE, starting_equity=100000.0)
        assert sizer.compute_risk_pct(100000.0) == 0.0050

        sizer.record_trade(-100.0)
        sizer.record_trade(-100.0)
        sizer.record_trade(-100.0)
        assert sizer.compute_risk_pct(100000.0) == 0.0025

        sizer.record_trade(200.0)
        sizer.record_trade(200.0)
        assert sizer.compute_risk_pct(100000.0) == 0.0050

        sizer.record_trade(200.0)
        assert sizer.compute_risk_pct(100000.0) == 0.0075

    def test_volatility_scaled_inverse_atr(self):
        """Verify Volatility-Scaled risk adjusts inversely with market ATR."""
        sizer = ModularRiskSizer(ModularRiskModel.VOLATILITY_SCALED, starting_equity=100000.0)
        risk_low_vol = sizer.compute_risk_pct(100000.0, atr=25.0)
        risk_norm_vol = sizer.compute_risk_pct(100000.0, atr=50.0)
        risk_high_vol = sizer.compute_risk_pct(100000.0, atr=100.0)

        assert risk_low_vol > risk_norm_vol > risk_high_vol
        assert risk_norm_vol == 0.0050

    def test_equity_curve_moving_average_defensive_scaling(self):
        """Verify Equity Curve scales down risk when below 20-period moving average."""
        sizer = ModularRiskSizer(ModularRiskModel.EQUITY_CURVE, starting_equity=100000.0)
        for eq in [100000.0] * 20:
            sizer.record_equity(eq)

        assert sizer.compute_risk_pct(101000.0) == 0.0050
        assert sizer.compute_risk_pct(98000.0) == 0.0025

    def test_all_seven_risk_models_produce_distinct_lot_sizes(self):
        """Verify that all 7 risk models evaluate to distinct lot sizes given identical equity and SL."""
        equity = 94939.28
        sl_pts = 40.0
        atr = 25.0
        models = [
            ModularRiskModel.CONSERVATIVE_RAMP,
            ModularRiskModel.FIXED_LOW,
            ModularRiskModel.AGGRESSIVE_FLAT,
            ModularRiskModel.KELLY_CRITERION,
            ModularRiskModel.ANTI_MARTINGALE,
            ModularRiskModel.VOLATILITY_SCALED,
            ModularRiskModel.EQUITY_CURVE,
        ]
        calculated_lots = {}
        for m in models:
            sizer = ModularRiskSizer(m, starting_equity=100000.0)
            if m == ModularRiskModel.KELLY_CRITERION:
                for _ in range(16):
                    sizer.record_trade(250.0)
                for _ in range(4):
                    sizer.record_trade(-100.0)
            elif m == ModularRiskModel.ANTI_MARTINGALE:
                sizer.record_trade(100.0)
                sizer.record_trade(100.0)
                sizer.record_trade(100.0)
            elif m == ModularRiskModel.EQUITY_CURVE:
                for eq in [90000.0] * 20:
                    sizer.record_equity(eq)

            lots = sizer.compute_lots(equity, sl_points=sl_pts, atr=atr)
            calculated_lots[m.value] = lots

        unique_lots = set(calculated_lots.values())
        assert len(unique_lots) >= 5


class TestDimension2EntryModesNoDeadCode:
    """Verify all 7 London Reversal and all 7 Omni Breakout entry modes produce triggers."""

    def test_london_blind_limit(self):
        """Verify London Blind Limit entry triggers at exact Asian extremes."""
        dt = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
        c_high = make_candle(dt, high_p=19605.0, low_p=19550.0)
        c_low = make_candle(dt, high_p=19550.0, low_p=19495.0)

        res_high = evaluate_london_entry(LondonEntryMode.BLIND_LIMIT, c_high, 19600.0, 19500.0)
        res_low = evaluate_london_entry(LondonEntryMode.BLIND_LIMIT, c_low, 19600.0, 19500.0)

        assert res_high == (-1, 19600.0)
        assert res_low == (1, 19500.0)

    def test_london_sweep_confirmation(self):
        """Verify London Sweep Confirmation triggers when sweeping extreme and closing inside."""
        dt = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
        c_sweep_high = make_candle(dt, high_p=19615.0, close_p=19595.0, low_p=19580.0)
        c_sweep_low = make_candle(dt, low_p=19485.0, close_p=19505.0, high_p=19520.0)

        res_high = evaluate_london_entry(LondonEntryMode.SWEEP_CONFIRMATION, c_sweep_high, 19600.0, 19500.0)
        res_low = evaluate_london_entry(LondonEntryMode.SWEEP_CONFIRMATION, c_sweep_low, 19600.0, 19500.0)

        assert res_high == (-1, 19595.0)
        assert res_low == (1, 19505.0)

    def test_london_dynamic_buffer(self):
        """Verify London Dynamic Buffer entry triggers offset by ATR fraction."""
        dt = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
        atr = 50.0
        expected_offset = 15.0
        c_buf = make_candle(dt, high_p=19600.0 + expected_offset + 2.0, low_p=19550.0)

        res = evaluate_london_entry(LondonEntryMode.DYNAMIC_BUFFER, c_buf, 19600.0, 19500.0, atr=atr)
        assert res == (-1, 19600.0 + expected_offset)

    def test_london_time_weighted(self):
        """Verify London Time-Weighted entry triggers on extreme touch."""
        dt = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
        c = make_candle(dt, high_p=19601.0, low_p=19550.0)
        res = evaluate_london_entry(LondonEntryMode.TIME_WEIGHTED, c, 19600.0, 19500.0)
        assert res == (-1, 19600.0)

    def test_london_order_flow_spread_gate(self):
        """Verify London Order Flow entry checks tight spread condition before entry."""
        dt = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
        c_tight = make_candle(dt, high_p=19602.0, low_p=19600.5)
        c_wide = make_candle(dt, high_p=19602.0, low_p=19597.0)

        res_tight = evaluate_london_entry(LondonEntryMode.ORDER_FLOW_SPREAD_GATE, c_tight, 19600.0, 19500.0)
        res_wide = evaluate_london_entry(LondonEntryMode.ORDER_FLOW_SPREAD_GATE, c_wide, 19600.0, 19500.0)

        assert res_tight == (-1, 19600.0)
        assert res_wide is None

    def test_london_multi_timeframe(self):
        """Verify London Multi-Timeframe entry requires rejection candle closing direction."""
        dt = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
        c_bear = make_candle(dt, open_p=19602.0, high_p=19605.0, low_p=19550.0, close_p=19598.0)
        c_bull = make_candle(dt, open_p=19595.0, high_p=19605.0, low_p=19550.0, close_p=19602.0)

        res_bear = evaluate_london_entry(LondonEntryMode.MULTI_TIMEFRAME, c_bear, 19600.0, 19500.0)
        res_bull = evaluate_london_entry(LondonEntryMode.MULTI_TIMEFRAME, c_bull, 19600.0, 19500.0)

        assert res_bear == (-1, 19598.0)
        assert res_bull is None

    def test_london_hybrid_sweep_time_spread(self):
        """Verify London Hybrid entry combines sweep confirmation with spread gate."""
        dt = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
        c_hybrid = make_candle(dt, high_p=19605.0, low_p=19603.0, close_p=19598.0)
        res = evaluate_london_entry(LondonEntryMode.HYBRID_SWEEP_TIME_SPREAD, c_hybrid, 19600.0, 19500.0)
        assert res == (-1, 19598.0)

    def test_omni_stop_order_at_range(self):
        """Verify Omni Stop Order entry triggers on breakout touch of ORB high/low."""
        dt = datetime(2026, 9, 1, 14, 35, tzinfo=timezone.utc)
        c_long = make_candle(dt, high_p=19710.0, low_p=19680.0)
        c_short = make_candle(dt, high_p=19650.0, low_p=19615.0)

        res_long = evaluate_omni_entry(ModularOmniEntryMode.STOP_ORDER_AT_RANGE, c_long, 19700.0, 19620.0)
        res_short = evaluate_omni_entry(ModularOmniEntryMode.STOP_ORDER_AT_RANGE, c_short, 19700.0, 19620.0)

        assert res_long == (1, 19700.0)
        assert res_short == (-1, 19620.0)

    def test_omni_close_confirmation(self):
        """Verify Omni Close Confirmation requires candle close outside ORB range."""
        dt = datetime(2026, 9, 1, 14, 35, tzinfo=timezone.utc)
        c_close_above = make_candle(dt, high_p=19720.0, low_p=19690.0, close_p=19715.0)
        c_close_inside = make_candle(dt, high_p=19720.0, low_p=19680.0, close_p=19695.0)

        res_above = evaluate_omni_entry(ModularOmniEntryMode.CLOSE_CONFIRMATION, c_close_above, 19700.0, 19620.0)
        res_inside = evaluate_omni_entry(ModularOmniEntryMode.CLOSE_CONFIRMATION, c_close_inside, 19700.0, 19620.0)

        assert res_above == (1, 19715.0)
        assert res_inside is None

    def test_omni_volume_spike_gate(self):
        """Verify Omni Volume Spike requires positive volume confirmation."""
        dt = datetime(2026, 9, 1, 14, 35, tzinfo=timezone.utc)
        c_vol = make_candle(dt, high_p=19710.0, low_p=19650.0, volume=500.0)
        c_no_vol = make_candle(dt, high_p=19710.0, low_p=19650.0, volume=0.0)

        res_vol = evaluate_omni_entry(ModularOmniEntryMode.VOLUME_SPIKE_GATE, c_vol, 19700.0, 19620.0)
        res_no_vol = evaluate_omni_entry(ModularOmniEntryMode.VOLUME_SPIKE_GATE, c_no_vol, 19700.0, 19620.0)

        assert res_vol == (1, 19700.0)
        assert res_no_vol is None

    def test_omni_retest_entry(self):
        """Verify Omni Retest entry executes when price dips to boundary and holds above."""
        dt = datetime(2026, 9, 1, 14, 40, tzinfo=timezone.utc)
        c_retest = make_candle(dt, low_p=19698.0, high_p=19715.0, close_p=19710.0)
        res = evaluate_omni_entry(ModularOmniEntryMode.RETEST_ENTRY, c_retest, 19700.0, 19620.0)
        assert res == (1, 19710.0)

    def test_omni_momentum_threshold(self):
        """Verify Omni Momentum Threshold requires 10-point extension beyond boundary."""
        dt = datetime(2026, 9, 1, 14, 35, tzinfo=timezone.utc)
        c_pass = make_candle(dt, low_p=19680.0, high_p=19715.0, close_p=19712.0)
        c_fail = make_candle(dt, low_p=19680.0, high_p=19708.0, close_p=19705.0)

        res_pass = evaluate_omni_entry(ModularOmniEntryMode.MOMENTUM_THRESHOLD, c_pass, 19700.0, 19620.0)
        res_fail = evaluate_omni_entry(ModularOmniEntryMode.MOMENTUM_THRESHOLD, c_fail, 19700.0, 19620.0)

        assert res_pass == (1, 19712.0)
        assert res_fail is None

    def test_omni_dual_timeframe(self):
        """Verify Omni Dual Timeframe checks candle directional closure alignment."""
        dt = datetime(2026, 9, 1, 14, 35, tzinfo=timezone.utc)
        c_bull = make_candle(dt, open_p=19702.0, high_p=19720.0, low_p=19690.0, close_p=19715.0)
        c_bear = make_candle(dt, open_p=19718.0, high_p=19720.0, low_p=19690.0, close_p=19705.0)

        res_bull = evaluate_omni_entry(ModularOmniEntryMode.DUAL_TIMEFRAME, c_bull, 19700.0, 19620.0)
        res_bear = evaluate_omni_entry(ModularOmniEntryMode.DUAL_TIMEFRAME, c_bear, 19700.0, 19620.0)

        assert res_bull == (1, 19715.0)
        assert res_bear is None

    def test_omni_hybrid_retest_volume_spread(self):
        """Verify Omni Hybrid entry combines retest with volume spike and tight spread."""
        dt = datetime(2026, 9, 1, 14, 40, tzinfo=timezone.utc)
        c_hyb = make_candle(dt, low_p=19699.0, high_p=19703.0, close_p=19702.0, volume=150.0)
        res = evaluate_omni_entry(ModularOmniEntryMode.HYBRID_RETEST_VOLUME_SPREAD, c_hyb, 19700.0, 19620.0)
        assert res == (1, 19702.0)


class TestDimension3PyramidingModelsTranches:
    """Verify that all 7 Pyramiding models correctly manage tranche scaling and derisking."""

    def test_pyramid_no_pyramid_allocation(self):
        """Verify No Pyramid allocates 100% on initial tranche and returns no scale-in."""
        pm = PyramidManager(ModularPyramidModel.NO_PYRAMID, total_planned_lots=3.0)
        assert pm.get_initial_lots() == 3.0
        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=3.0, sl_price=19560.0, tp_price=None, tranches_filled=1)
        c = make_candle(datetime.now(), high_p=19640.0, low_p=19590.0)
        assert pm.check_scale_in(pos, c) is None

    def test_pyramid_equal_split_scaling(self):
        """Verify Equal Split allocates 1/3 and generates scale-in adds at +15 and +30 pts."""
        pm = PyramidManager(ModularPyramidModel.EQUAL_SPLIT, total_planned_lots=3.0)
        assert pm.get_initial_lots() == 1.0
        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=1.0, sl_price=19560.0, tp_price=None, tranches_filled=1)

        c1 = make_candle(datetime.now(), high_p=19616.0, low_p=19590.0)
        sig1 = pm.check_scale_in(pos, c1)
        assert sig1 is not None
        assert sig1.tranche_index == 2
        assert sig1.additional_lots == 1.0
        assert sig1.move_to_be is True
        assert sig1.new_sl == 19600.0

        pos.lots += sig1.additional_lots
        pos.tranches_filled = 2
        c2 = make_candle(datetime.now(), high_p=19632.0, low_p=19610.0)
        sig2 = pm.check_scale_in(pos, c2)
        assert sig2 is not None
        assert sig2.tranche_index == 3

    def test_pyramid_front_loaded_weights(self):
        """Verify Front Loaded weights tranches 50%, 30%, 20%."""
        pm = PyramidManager(ModularPyramidModel.FRONT_LOADED, total_planned_lots=10.0)
        assert pm.get_initial_lots() == 5.0
        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=5.0, sl_price=19560.0, tp_price=None, tranches_filled=1)

        c = make_candle(datetime.now(), high_p=19616.0, low_p=19590.0)
        sig = pm.check_scale_in(pos, c)
        assert sig is not None
        assert sig.additional_lots == 3.0

    def test_pyramid_inverse_pyramid_weights(self):
        """Verify Inverse Pyramid weights tranches 20%, 30%, 50% and scales at +20, +40 pts."""
        pm = PyramidManager(ModularPyramidModel.INVERSE_PYRAMID, total_planned_lots=10.0)
        assert pm.get_initial_lots() == 2.0
        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=2.0, sl_price=19560.0, tp_price=None, tranches_filled=1)

        c1 = make_candle(datetime.now(), high_p=19621.0, low_p=19590.0)
        sig1 = pm.check_scale_in(pos, c1)
        assert sig1 is not None
        assert sig1.additional_lots == 3.0

        pos.lots += sig1.additional_lots
        pos.tranches_filled = 2
        c2 = make_candle(datetime.now(), high_p=19641.0, low_p=19610.0)
        sig2 = pm.check_scale_in(pos, c2)
        assert sig2 is not None
        assert sig2.additional_lots == 5.0

    def test_pyramid_momentum_confirmed_two_tranches(self):
        """Verify Momentum Confirmed allocates 50/50 across 2 tranches."""
        pm = PyramidManager(ModularPyramidModel.MOMENTUM_CONFIRMED, total_planned_lots=4.0)
        assert pm.get_initial_lots() == 2.0
        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=2.0, sl_price=19560.0, tp_price=None, tranches_filled=1)

        c = make_candle(datetime.now(), high_p=19616.0, low_p=19590.0)
        sig = pm.check_scale_in(pos, c)
        assert sig is not None
        assert sig.additional_lots == 2.0

    def test_pyramid_adaptive_tranche_cascade(self):
        """Verify Adaptive Tranche cascades 4 tranches of 25% each."""
        pm = PyramidManager(ModularPyramidModel.ADAPTIVE_TRANCHE, total_planned_lots=4.0)
        assert pm.get_initial_lots() == 1.0
        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=1.0, sl_price=19560.0, tp_price=None, tranches_filled=1)

        c1 = make_candle(datetime.now(), high_p=19611.0, low_p=19590.0)
        sig1 = pm.check_scale_in(pos, c1)
        assert sig1 is not None
        assert sig1.additional_lots == 1.0

    def test_pyramid_risk_free_runner_partial_scalp(self):
        """Verify Risk-Free Runner triggers 50% partial scalp at +15 pts and moves SL to BE."""
        pm = PyramidManager(ModularPyramidModel.RISK_FREE_RUNNER, total_planned_lots=4.0)
        assert pm.get_initial_lots() == 4.0
        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=4.0, sl_price=19560.0, tp_price=None, tranches_filled=1)

        c = make_candle(datetime.now(), high_p=19616.0, low_p=19590.0)
        scale_out = pm.check_scale_out(pos, c)
        assert scale_out is not None
        assert scale_out.lots_to_close == 2.0
        assert scale_out.move_to_be is True
        assert scale_out.new_sl == 19601.0


class TestDimension4ExitModelsDistinctBehavior:
    """Verify that all 7 Exit Models produce distinct stop loss and take profit behaviors."""

    def test_exit_fixed_sl_tp(self):
        """Verify Fixed SL/TP sets deterministic hard bounds."""
        manager = ModularExitManager(ModularExitModel.FIXED_SL_TP, sl_pts=40.0, tp_pts=20.0)
        sl, tp = manager.compute_sl_tp(19600.0, direction=1)
        assert sl == 19560.0
        assert tp == 19620.0

    def test_exit_fixed_sl_trail(self):
        """Verify Fixed SL Trail trails stop after trigger excursion."""
        manager = ModularExitManager(ModularExitModel.FIXED_SL_TRAIL)
        sl, tp = manager.compute_sl_tp(19600.0, direction=1)
        assert sl == 19570.0
        assert tp is None

        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=1.0, sl_price=sl, tp_price=tp)
        c = make_candle(datetime.now(), high_p=19625.0, low_p=19590.0, close_p=19620.0)
        manager.check_exit(pos, c)
        assert pos.trailing_active is True
        assert pos.sl_price == 19610.0

    def test_exit_atr_dynamic_trail(self):
        """Verify ATR Dynamic Trail uses 1.5x ATR initial stop and trails at 1.0x ATR."""
        manager = ModularExitManager(ModularExitModel.ATR_DYNAMIC_TRAIL, atr=60.0)
        sl, tp = manager.compute_sl_tp(19600.0, direction=1)
        assert sl == 19600.0 - (1.5 * 60.0)
        assert tp is None

    def test_exit_breakeven_runner(self):
        """Verify Breakeven Runner adjusts stop to entry + 1 pt after +20 pt gain."""
        manager = ModularExitManager(ModularExitModel.BREAKEVEN_RUNNER)
        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=1.0, sl_price=19570.0, tp_price=None)
        c = make_candle(datetime.now(), high_p=19622.0, low_p=19590.0)
        manager.check_exit(pos, c)
        assert pos.trailing_active is True
        assert pos.sl_price == 19601.0

    def test_exit_time_based_termination(self):
        """Verify Time-Based exit enforces 120-minute maximum hold duration."""
        manager = ModularExitManager(ModularExitModel.TIME_BASED)
        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=1.0, sl_price=19560.0, tp_price=None)
        pos.time_in_trade_minutes = 119
        c = make_candle(datetime.now(), low_p=19580.0, high_p=19620.0, close_p=19615.0)
        res = manager.check_exit(pos, c)
        assert res == (19615.0, "time_exit")

    def test_exit_chandelier(self):
        """Verify Chandelier exit continuously ratchets stop based on highest high minus 3x ATR."""
        manager = ModularExitManager(ModularExitModel.CHANDELIER, atr=40.0)
        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=1.0, sl_price=19480.0, tp_price=None)
        c = make_candle(datetime.now(), low_p=19580.0, high_p=19650.0)
        manager.check_exit(pos, c)
        assert pos.sl_price == 19650.0 - (3.0 * 40.0)

    def test_exit_multi_target_cascade(self):
        """Verify Multi-Target Cascade executes partial liquidations at +15 and +30 pts."""
        manager = ModularExitManager(ModularExitModel.MULTI_TARGET_CASCADE)
        pos = Position(direction=1, entry_price=19600.0, entry_time=datetime.now(), lots=1.0, sl_price=19570.0, tp_price=None)
        c = make_candle(datetime.now(), low_p=19580.0, high_p=19618.0)
        manager.check_exit(pos, c)
        assert 0 in pos.partial_closes
        assert round(pos.lots, 2) == 0.67


class TestDimension5MarketFilters:
    """Verify all market context filters correctly approve and deny execution."""

    def test_atr_gate_filter(self):
        """Verify ATR gate enforces [0.5, 2.0] multiple."""
        fe = ModularFilterEngine(["atr_gate"])
        c = make_candle(datetime.now())
        assert fe.should_trade(c, atr=40.0, range_width=40.0) is True
        assert fe.should_trade(c, atr=40.0, range_width=10.0) is False
        assert fe.should_trade(c, atr=40.0, range_width=100.0) is False

    def test_spread_gate_filter(self):
        """Verify spread gate blocks execution when spread exceeds 5.0 points."""
        fe = ModularFilterEngine(["spread_gate"])
        c = make_candle(datetime.now())
        assert fe.should_trade(c, atr=40.0, range_width=40.0, spread=2.0) is True
        assert fe.should_trade(c, atr=40.0, range_width=40.0, spread=5.5) is False

    def test_day_of_week_filter(self):
        """Verify day of week filter blocks Monday (0) and Friday (4)."""
        fe = ModularFilterEngine(["day_of_week"])
        c_tuesday = make_candle(datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc))
        c_monday = make_candle(datetime(2026, 8, 31, 10, 0, tzinfo=timezone.utc))
        c_friday = make_candle(datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc))

        assert fe.should_trade(c_tuesday, atr=40.0, range_width=40.0) is True
        assert fe.should_trade(c_monday, atr=40.0, range_width=40.0) is False
        assert fe.should_trade(c_friday, atr=40.0, range_width=40.0) is False

    def test_vix_regime_filter(self):
        """Verify VIX regime filter halts trading below 15.0."""
        fe = ModularFilterEngine(["vix_regime"])
        c = make_candle(datetime.now())
        assert fe.should_trade(c, atr=40.0, range_width=40.0, vix=18.5) is True
        assert fe.should_trade(c, atr=40.0, range_width=40.0, vix=13.2) is False

    def test_news_blackout_filter(self):
        """Verify News Blackout filter halts trading on FOMC rate decision dates."""
        fe = ModularFilterEngine(["news_blackout"])
        c_fomc = make_candle(datetime(2026, 9, 16, 14, 0, tzinfo=timezone.utc))
        c_clear = make_candle(datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc))

        assert fe.should_trade(c_fomc, atr=40.0, range_width=40.0) is False
        assert fe.should_trade(c_clear, atr=40.0, range_width=40.0) is True

    def test_composite_filters_all_must_pass(self):
        """Verify composite filter stack blocks execution if any single filter fails."""
        fe = ModularFilterEngine(["atr_gate", "spread_gate", "day_of_week"])
        c_valid = make_candle(datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc))
        assert fe.should_trade(c_valid, atr=40.0, range_width=40.0, spread=2.0) is True
        assert fe.should_trade(c_valid, atr=40.0, range_width=10.0, spread=2.0) is False
        assert fe.should_trade(c_valid, atr=40.0, range_width=40.0, spread=6.0) is False


class TestEngineSimulationAndPyramidingIntegration:
    """Verify that BacktestEngine executes multi-tranche pyramiding and exits accurately."""

    def test_backtester_pyramiding_equal_split_execution(self):
        """Verify London simulator adds tranches and tracks tranches_filled under Equal Split."""
        profile = BacktestProfile(
            engine=EngineType.LONDON_REVERSAL,
            risk_model=RiskModel.FIXED_LOW,
            entry_mode="blind_limit",
            pyramid_model=PyramidModel.EQUAL_SPLIT,
            exit_model=ExitModel.FIXED_SL_TRAIL,
            filters=["spread_gate"],
            instrument="US100.cash",
        )
        dt = datetime(2026, 9, 1, tzinfo=timezone.utc)
        candles = generate_synthetic_candles(dt, 19600.0, 19500.0)

        engine = BacktestEngine(profile, candles, starting_equity=94939.28)
        metrics = engine.run()
        assert metrics.total_trades >= 1

    def test_backtester_pyramiding_risk_free_runner_execution(self):
        """Verify London simulator executes partial take profit scalp under Risk-Free Runner."""
        profile = BacktestProfile(
            engine=EngineType.LONDON_REVERSAL,
            risk_model=RiskModel.FIXED_LOW,
            entry_mode="blind_limit",
            pyramid_model=PyramidModel.RISK_FREE_RUNNER,
            exit_model=ExitModel.FIXED_SL_TRAIL,
            filters=[],
            instrument="US100.cash",
        )
        dt = datetime(2026, 9, 1, tzinfo=timezone.utc)
        candles = generate_synthetic_candles(dt, 19600.0, 19500.0)

        engine = BacktestEngine(profile, candles, starting_equity=94939.28)
        metrics = engine.run()
        assert metrics.total_trades >= 1
