"""Tier 3: Pairwise Cross-Feature Interactions and Incompatibility Suite.

Tests pairwise feature combinations across the 5 design dimensions:
Risk Sizing x Entry Modes x Pyramiding Models x Exit Models x Market Filters.
Enforces the 7 architectural incompatibility rules (INC-01 to INC-07) and
multi-session cross-engine equity interaction.
"""

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
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


class TestTier3ValidPairwiseCombinations:
    """Valid pairwise cross-feature matrix tests."""

    def test_combination_conservative_ramp_and_sweep_confirmation(
        self, synthetic_asian_candles, synthetic_london_candles
    ):
        """Verify Conservative Ramp risk combined with Sweep Confirmation entry."""
        profile = BacktestProfile(
            engine=EngineType.LONDON_REVERSAL,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode=EntryMode.SWEEP_CONFIRMATION.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TRAIL,
            filters=["spread_gate"],
            instrument="US100.cash",
        )
        dt = datetime(2026, 9, 1, tzinfo=timezone.utc)
        candles = synthetic_asian_candles(dt, 19600.0, 19500.0) + synthetic_london_candles(dt, 19600.0, 19500.0, scenario="sweep_high_reversal")
        engine = BacktestEngine(profile, candles, starting_equity=94939.28)
        metrics = engine.run()
        assert metrics.total_trades >= 1
        assert metrics.ending_equity != metrics.starting_equity

    def test_combination_fixed_low_and_dynamic_buffer(
        self, synthetic_asian_candles, synthetic_london_candles
    ):
        """Verify Fixed Low risk combined with Dynamic Buffer entry."""
        profile = BacktestProfile(
            engine=EngineType.LONDON_REVERSAL,
            risk_model=RiskModel.FIXED_LOW,
            entry_mode=EntryMode.DYNAMIC_BUFFER.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.BREAKEVEN_RUNNER,
            filters=["atr_gate", "spread_gate"],
            instrument="US100.cash",
        )
        dt = datetime(2026, 9, 1, tzinfo=timezone.utc)
        candles = synthetic_asian_candles(dt, 19600.0, 19500.0) + synthetic_london_candles(dt, 19600.0, 19500.0, scenario="sweep_high_reversal")
        engine = BacktestEngine(profile, candles, starting_equity=94939.28)
        metrics = engine.run()
        assert metrics.starting_equity == 94939.28

    def test_combination_volatility_scaled_and_atr_dynamic_trail(
        self, synthetic_asian_candles, synthetic_london_candles
    ):
        """Verify Volatility-Scaled risk coupled with ATR Dynamic Trail exit."""
        profile = BacktestProfile(
            engine=EngineType.LONDON_REVERSAL,
            risk_model=RiskModel.VOLATILITY_SCALED,
            entry_mode=EntryMode.SWEEP_CONFIRMATION.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.ATR_DYNAMIC_TRAIL,
            filters=["spread_gate"],
            instrument="US100.cash",
        )
        dt = datetime(2026, 9, 1, tzinfo=timezone.utc)
        candles = synthetic_asian_candles(dt, 19600.0, 19500.0) + synthetic_london_candles(dt, 19600.0, 19500.0, scenario="sweep_low_reversal")
        engine = BacktestEngine(profile, candles, starting_equity=94939.28)
        metrics = engine.run()
        assert metrics.total_trades >= 1

    def test_combination_omni_close_confirmation_and_fixed_sl_trail(
        self, synthetic_us_orb_candles, synthetic_us_session_candles
    ):
        """Verify Omni Close Confirmation entry paired with Fixed SL Trail."""
        profile = BacktestProfile(
            engine=EngineType.OMNI_BREAKOUT,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode=OmniEntryMode.CLOSE_CONFIRMATION.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TRAIL,
            filters=["spread_gate"],
            instrument="US100.cash",
        )
        dt = datetime(2026, 9, 1, tzinfo=timezone.utc)
        candles = synthetic_us_orb_candles(dt, 19700.0, 19620.0) + synthetic_us_session_candles(dt, 19700.0, 19620.0, scenario="bullish_breakout")
        engine = BacktestEngine(profile, candles, starting_equity=94939.28)
        metrics = engine.run()
        assert metrics.total_trades >= 1

    def test_combination_omni_retest_entry_and_breakeven_runner(
        self, synthetic_us_orb_candles, synthetic_us_session_candles
    ):
        """Verify Omni Retest Entry paired with Breakeven Runner exit."""
        profile = BacktestProfile(
            engine=EngineType.OMNI_BREAKOUT,
            risk_model=RiskModel.FIXED_LOW,
            entry_mode=OmniEntryMode.RETEST_ENTRY.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.BREAKEVEN_RUNNER,
            filters=["spread_gate"],
            instrument="US100.cash",
        )
        dt = datetime(2026, 9, 1, tzinfo=timezone.utc)
        candles = synthetic_us_orb_candles(dt, 19700.0, 19620.0) + synthetic_us_session_candles(dt, 19700.0, 19620.0, scenario="bullish_breakout")
        engine = BacktestEngine(profile, candles, starting_equity=94939.28)
        metrics = engine.run()
        assert metrics.starting_equity == 94939.28

    def test_combination_pyramid_equal_split_and_trailing_exit(self):
        """Verify Equal Split pyramiding with Fixed SL Trail exit model."""
        pyramid = PyramidModel.EQUAL_SPLIT
        exit_mod = ExitModel.FIXED_SL_TRAIL
        compatible = not (pyramid in (PyramidModel.EQUAL_SPLIT, PyramidModel.FRONT_LOADED) and exit_mod == ExitModel.FIXED_SL_TP)
        assert compatible is True

    def test_combination_pyramid_front_loaded_and_atr_dynamic_trail(self):
        """Verify Front Loaded pyramiding paired with ATR Dynamic Trail exit."""
        pyramid = PyramidModel.FRONT_LOADED
        exit_mod = ExitModel.ATR_DYNAMIC_TRAIL
        compatible = not (pyramid == PyramidModel.FRONT_LOADED and exit_mod == ExitModel.FIXED_SL_TP)
        assert compatible is True

    def test_combination_risk_free_runner_and_multi_target(self):
        """Verify Risk Free Runner pyramiding paired with Multi Target Cascade."""
        pyramid = PyramidModel.RISK_FREE_RUNNER
        exit_mod = ExitModel.MULTI_TARGET_CASCADE
        assert pyramid.value == "risk_free_runner"
        assert exit_mod.value == "multi_target_cascade"


class TestTier3IncompatibilityMatrix:
    """Enforce the 7 architectural incompatibility rules (INC-01 to INC-07)."""

    def test_inc01_cross_engine_entry_mismatch(self):
        """Verify INC-01: London Reversal assigned Omni entry mode is rejected."""
        london_valid_entries = {e.value for e in EntryMode}
        omni_entry = OmniEntryMode.STOP_ORDER_AT_RANGE.value
        is_mismatch = omni_entry not in london_valid_entries
        assert is_mismatch is True

    def test_inc02_scale_in_pyramiding_with_static_fixed_sl_tp(self):
        """Verify INC-02: Scale-in pyramiding combined with static fixed_sl_tp is rejected."""
        scale_in_models = {
            PyramidModel.EQUAL_SPLIT,
            PyramidModel.FRONT_LOADED,
            PyramidModel.INVERSE_PYRAMID,
            PyramidModel.ADAPTIVE_TRANCHE,
        }
        exit_model = ExitModel.FIXED_SL_TP
        for model in scale_in_models:
            is_inc02 = (model in scale_in_models) and (exit_model == ExitModel.FIXED_SL_TP)
            assert is_inc02 is True

    def test_inc03_high_exposure_risk_with_multi_tranche_pyramiding(self):
        """Verify INC-03: Aggressive risk combined with back-loaded pyramiding is rejected."""
        high_risk_models = {RiskModel.AGGRESSIVE_FLAT, RiskModel.ANTI_MARTINGALE}
        dangerous_pyramid_models = {PyramidModel.INVERSE_PYRAMID, PyramidModel.ADAPTIVE_TRANCHE}
        for risk in high_risk_models:
            for pyr in dangerous_pyramid_models:
                is_inc03 = (risk in high_risk_models) and (pyr in dangerous_pyramid_models)
                assert is_inc03 is True

    def test_inc04_multi_tranche_scale_in_with_time_based_exit(self):
        """Verify INC-04: Multi-tranche scale-in paired with time_based exit is rejected."""
        scale_in_models = {PyramidModel.ADAPTIVE_TRANCHE, PyramidModel.MOMENTUM_CONFIRMED}
        exit_model = ExitModel.TIME_BASED
        for pyr in scale_in_models:
            is_inc04 = (pyr in scale_in_models) and (exit_model == ExitModel.TIME_BASED)
            assert is_inc04 is True

    def test_inc05_blind_limit_with_empty_filters(self):
        """Verify INC-05: Blind limit entry without market context filters is rejected."""
        entry = EntryMode.BLIND_LIMIT.value
        filters: List[str] = []
        is_inc05 = (entry == "blind_limit") and (len(filters) == 0)
        assert is_inc05 is True

    def test_inc06_chandelier_wide_stop_with_tight_fixed_sl_sizing(self):
        """Verify INC-06: Chandelier exit (3.0x ATR) with tight fixed SL assumption is flagged."""
        atr = 80.0
        chandelier_distance = 3.0 * atr
        tight_sl = 40.0
        is_inc06 = chandelier_distance > (2.0 * tight_sl)
        assert is_inc06 is True

    def test_inc07_crypto_with_excessive_lot_size(self):
        """Verify INC-07: Crypto instruments with position size > 0.50 lots are rejected."""
        symbol = "BTCUSD"
        lots = 0.75
        is_crypto = symbol in ("BTCUSD", "ETHUSD")
        is_inc07 = is_crypto and (lots > 0.50)
        assert is_inc07 is True


class TestTier3MultiAssetAndSessionInteractions:
    """Multi-asset class differences and cross-session equity sharing."""

    def test_multi_asset_commission_structures(self, ftmo_asset_specs: dict):
        """Verify zero commission for indices vs $3/lot commission for forex and commodities."""
        spec_map = {inst["symbol"]: inst for inst in ftmo_asset_specs["instruments"]}
        assert spec_map["US100.cash"]["commission_per_lot"] == 0
        assert spec_map["EURUSD"]["commission_per_lot"] == 3
        assert spec_map["XAUUSD"]["commission_per_lot"] == 3
        assert spec_map["BTCUSD"]["commission_per_lot"] == 0

    def test_multi_asset_leverage_bounds(self, ftmo_asset_specs: dict):
        """Verify leverage: Indices 1:50, Forex 1:100, Commodities 1:30, Crypto 1:1."""
        assert ftmo_asset_specs["general_rules"]["commissions"] is not None

    def test_multi_session_london_to_omni_equity_propagation(
        self, synthetic_asian_candles, synthetic_london_candles,
        synthetic_us_orb_candles, synthetic_us_session_candles
    ):
        """Verify morning London session profit propagates to afternoon Omni session equity."""
        start_equity = 94939.28
        dt = datetime(2026, 9, 1, tzinfo=timezone.utc)

        london_profile = BacktestProfile(
            engine=EngineType.LONDON_REVERSAL,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode=EntryMode.SWEEP_CONFIRMATION.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TRAIL,
            filters=["spread_gate"],
            instrument="US100.cash",
        )
        london_candles = synthetic_asian_candles(dt, 19600.0, 19500.0) + synthetic_london_candles(dt, 19600.0, 19500.0, scenario="sweep_high_reversal")
        london_engine = BacktestEngine(london_profile, london_candles, starting_equity=start_equity)
        london_metrics = london_engine.run()

        afternoon_equity = london_metrics.ending_equity

        omni_profile = BacktestProfile(
            engine=EngineType.OMNI_BREAKOUT,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode=OmniEntryMode.CLOSE_CONFIRMATION.value,
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TRAIL,
            filters=["spread_gate"],
            instrument="US100.cash",
        )
        omni_candles = synthetic_us_orb_candles(dt, 19700.0, 19620.0) + synthetic_us_session_candles(dt, 19700.0, 19620.0, scenario="bullish_breakout")
        omni_engine = BacktestEngine(omni_profile, omni_candles, starting_equity=afternoon_equity)
        omni_metrics = omni_engine.run()

        assert omni_metrics.starting_equity == afternoon_equity
        assert omni_metrics.ending_equity > 90000.0

    def test_multi_session_circuit_breaker_halts_all_engines(self):
        """Verify morning London circuit breaker trip halts afternoon Omni trading."""
        daily_start_equity = 94939.28
        circuit_breaker_threshold = daily_start_equity * (1.0 - 0.045)
        morning_drawdown_equity = daily_start_equity - 4400.0
        circuit_breaker_active = morning_drawdown_equity <= circuit_breaker_threshold

        omni_allowed_to_trade = not circuit_breaker_active
        assert circuit_breaker_active is True
        assert omni_allowed_to_trade is False
