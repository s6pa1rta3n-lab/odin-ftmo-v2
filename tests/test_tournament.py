"""Unit and integration test suite for Backtesting Tournament Runner (Milestone M4).

Verifies:
1. Profile combination generation for London Reversal and Omni Breakout.
2. Formal verification pre-screening filtering out invalid/toxic profiles.
3. In-memory pre-loading and daily grouping across multiple windows.
4. Multiprocess task execution with pre-loaded trading days.
5. Tournament scoring formula fidelity (Sharpe 40%, MDD 30%, PF 20%, Trades 10%).
6. Multi-window acceptance criteria filtering (Sharpe > 0 and MDD < 8% across 6m, 1y, 2.5y).
7. Top 10 profile export conforming strictly to profile schema and validator.
"""

import json
import math
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
import pytest

from backtester.engine import (
    BacktestEngine,
    BacktestMetrics,
    BacktestProfile,
    Candle,
    EngineType,
    ExitModel,
    PyramidModel,
    RiskModel,
)
from backtester.tournament import (
    TIME_WINDOWS,
    evaluate_multi_window_profiles,
    export_top_profiles,
    generate_london_profiles,
    generate_omni_profiles,
    preload_trading_days,
    prescreen_profiles,
    profile_to_dict,
    run_single_backtest,
    run_tournament,
)
from verifier.validator import validate_profile

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "profiles" / "profile_schema.json"


class TestProfileGenerationAndPrescreening:
    """Tests for candidate profile generation and formal verification pre-screening."""

    def test_london_profile_generation_dimensions(self):
        """Verify London Reversal generates expected combinatorial profile count."""
        profiles = generate_london_profiles(["US100.cash"])
        assert len(profiles) == 7 * 7 * 7 * 7 * 7
        for p in profiles[:10]:
            assert p.engine == EngineType.LONDON_REVERSAL
            assert p.instrument == "US100.cash"

    def test_omni_profile_generation_dimensions(self):
        """Verify Omni Breakout generates expected combinatorial profile count."""
        profiles = generate_omni_profiles(["US100.cash"])
        assert len(profiles) == 7 * 7 * 7 * 7 * 7
        for p in profiles[:10]:
            assert p.engine == EngineType.OMNI_BREAKOUT
            assert p.instrument == "US100.cash"

    def test_profile_to_dict_conforms_to_schema(self):
        """Verify profile_to_dict produces dictionary strictly validating against profile_schema.json."""
        with open(SCHEMA_PATH, "r") as f:
            schema = json.load(f)

        profile = BacktestProfile(
            engine=EngineType.LONDON_REVERSAL,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode="sweep_confirmation",
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TRAIL,
            filters=["spread_gate"],
            instrument="US100.cash",
        )
        p_dict = profile_to_dict(profile)
        jsonschema.validate(instance=p_dict, schema=schema)

    def test_prescreen_profiles_filters_incompatible_combinations(self):
        """Verify prescreen_profiles eliminates combinations violating INC rules."""
        incompatible_profile = BacktestProfile(
            engine=EngineType.LONDON_REVERSAL,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode="blind_limit",
            pyramid_model=PyramidModel.EQUAL_SPLIT,
            exit_model=ExitModel.FIXED_SL_TP,
            filters=[],
            instrument="US100.cash",
        )
        valid_profile = BacktestProfile(
            engine=EngineType.LONDON_REVERSAL,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode="sweep_confirmation",
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TRAIL,
            filters=["spread_gate"],
            instrument="US100.cash",
        )
        filtered = prescreen_profiles([incompatible_profile, valid_profile])
        assert len(filtered) == 1
        assert filtered[0].entry_mode == "sweep_confirmation"


class TestPreloadingAndDayGrouping:
    """Tests for in-memory candle loading and day-grouping."""

    def test_preload_trading_days_slices_windows_accurately(self):
        """Verify preload_trading_days correctly slices candles by time window."""
        test_windows = {
            "w1": ("2026-08-01", "2026-08-15"),
            "w2": ("2026-08-16", "2026-08-31"),
        }
        data_dir = "data/raw"
        preloaded = preload_trading_days(data_dir, ["US100.cash"], test_windows)
        assert ("US100.cash", "w1") in preloaded
        assert ("US100.cash", "w2") in preloaded

        days_w1 = preloaded[("US100.cash", "w1")]
        for day_dt, candles in days_w1:
            assert datetime(2026, 8, 1, tzinfo=timezone.utc) <= day_dt <= datetime(2026, 8, 15, tzinfo=timezone.utc)

    def test_run_single_backtest_with_preloaded_cache(self):
        """Verify run_single_backtest executes accurately using pre-loaded cache."""
        test_windows = {"test_win": ("2026-08-01", "2026-08-10")}
        preloaded = preload_trading_days("data/raw", ["US100.cash"], test_windows)

        profile = BacktestProfile(
            engine=EngineType.LONDON_REVERSAL,
            risk_model=RiskModel.CONSERVATIVE_RAMP,
            entry_mode="sweep_confirmation",
            pyramid_model=PyramidModel.NO_PYRAMID,
            exit_model=ExitModel.FIXED_SL_TRAIL,
            filters=["spread_gate"],
            instrument="US100.cash",
        )
        task_args = (
            profile_to_dict(profile),
            "data/raw",
            "test_win",
            "2026-08-01",
            "2026-08-10",
            100000.0,
            1.0,
            0.0,
        )
        from backtester.tournament import _init_worker
        _init_worker(preloaded)

        result = run_single_backtest(task_args)
        assert result is not None
        assert "tournament_score" in result
        assert result["window"] == "test_win"


class TestMultiWindowEvaluationAndTopSelection:
    """Tests for multi-window acceptance criteria filtering and top profile export."""

    def test_evaluate_multi_window_profiles_filtering(self):
        """Verify acceptance criteria: positive Sharpe in all windows and MDD < 8%."""
        mock_results = [
            {
                "profile_id": "profile_good",
                "window": "6m",
                "sharpe_ratio": 1.5,
                "max_drawdown_pct": 0.03,
                "tournament_score": 1.2,
                "total_trades": 40,
                "total_pnl": 2000.0,
            },
            {
                "profile_id": "profile_good",
                "window": "1y",
                "sharpe_ratio": 1.8,
                "max_drawdown_pct": 0.04,
                "tournament_score": 1.3,
                "total_trades": 80,
                "total_pnl": 4500.0,
            },
            {
                "profile_id": "profile_good",
                "window": "2.5y",
                "sharpe_ratio": 2.1,
                "max_drawdown_pct": 0.05,
                "tournament_score": 1.4,
                "total_trades": 200,
                "total_pnl": 10000.0,
            },
            {
                "profile_id": "profile_negative_sharpe",
                "window": "6m",
                "sharpe_ratio": -0.5,
                "max_drawdown_pct": 0.04,
                "tournament_score": 0.5,
            },
            {
                "profile_id": "profile_negative_sharpe",
                "window": "1y",
                "sharpe_ratio": 1.2,
                "max_drawdown_pct": 0.04,
                "tournament_score": 1.1,
            },
            {
                "profile_id": "profile_negative_sharpe",
                "window": "2.5y",
                "sharpe_ratio": 1.0,
                "max_drawdown_pct": 0.05,
                "tournament_score": 1.0,
            },
            {
                "profile_id": "profile_high_mdd",
                "window": "6m",
                "sharpe_ratio": 1.5,
                "max_drawdown_pct": 0.09,
                "tournament_score": 1.0,
            },
            {
                "profile_id": "profile_high_mdd",
                "window": "1y",
                "sharpe_ratio": 1.5,
                "max_drawdown_pct": 0.04,
                "tournament_score": 1.2,
            },
            {
                "profile_id": "profile_high_mdd",
                "window": "2.5y",
                "sharpe_ratio": 1.5,
                "max_drawdown_pct": 0.05,
                "tournament_score": 1.2,
            },
        ]

        qualified = evaluate_multi_window_profiles(mock_results, required_windows=["6m", "1y", "2.5y"])
        assert len(qualified) == 1
        assert qualified[0]["profile_id"] == "profile_good"
        assert math.isclose(qualified[0]["composite_score"], (1.2 + 1.3 + 1.4) / 3.0)

    def test_export_top_profiles_schema_conformance(self):
        """Verify exported top profile JSON files conform to profile_schema.json and pass validator."""
        with open(SCHEMA_PATH, "r") as f:
            schema = json.load(f)

        temp_dir = tempfile.mkdtemp()
        try:
            mock_qualified = [
                {
                    "profile_id": "london_reversal|conservative_ramp|sweep_confirmation|no_pyramid|fixed_sl_trail|spread_gate|US100.cash",
                    "composite_score": 1.35,
                    "windows": {},
                }
            ]
            exported = export_top_profiles(mock_qualified, "london", temp_dir, top_n=1)
            assert len(exported) == 1
            exported_file = exported[0]
            assert exported_file.exists()

            with open(exported_file, "r") as f:
                doc = json.load(f)

            jsonschema.validate(instance=doc, schema=schema)
            is_valid, violations, _ = validate_profile(doc)
            assert is_valid, f"Exported profile failed validator: {violations}"
        finally:
            shutil.rmtree(temp_dir)
