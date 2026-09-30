"""Unit and integration test suite for griff_engine_live.py module."""

from __future__ import annotations

import argparse
import os
import pytest
from typing import Any, Dict, List

from griff_engine_live import (
    compute_true_range,
    compute_atr_14,
    is_inside_bar,
    calculate_position_size,
    calculate_initial_stop_loss,
    calculate_trailing_stop,
    GriffSimulationEngine,
    GriffLiveEngine,
    load_metaapi_token,
    parse_arguments,
    DEFAULT_ACCOUNT_ID,
    DEFAULT_SYMBOL,
    GRIFF_ORDER_COMMENT,
)


class TestGriffLiveEngineExports:
    """Validate public exports, constants, and basic types."""

    def test_default_constants(self) -> None:
        """Verify default account ID, symbol, and order comment values."""
        assert DEFAULT_ACCOUNT_ID == "45a2565b-4f53-4bd5-8c58-667b3660430f"
        assert DEFAULT_SYMBOL == "US100.cash"
        assert GRIFF_ORDER_COMMENT == "GRIFF_1H_BREAKOUT"

    def test_true_range_calculations(self) -> None:
        """Verify true range edge cases."""
        assert compute_true_range(100.0, 90.0, 95.0) == 10.0
        assert compute_true_range(110.0, 105.0, 90.0) == 20.0
        assert compute_true_range(80.0, 75.0, 100.0) == 25.0

    def test_compute_atr_14_minimum_history(self) -> None:
        """Verify compute_atr_14 requires minimum 15 candles."""
        with pytest.raises(ValueError) as exc:
            compute_atr_14([{"high": 10.0, "low": 5.0, "close": 8.0}] * 14)
        assert "Need at least 15 candles" in str(exc.value)

    def test_is_inside_bar_logic(self) -> None:
        """Verify inside bar strict inequality logic."""
        mother = {"high": 200.0, "low": 100.0}
        assert is_inside_bar({"high": 199.9, "low": 100.1}, mother) is True
        assert is_inside_bar({"high": 200.0, "low": 100.1}, mother) is False
        assert is_inside_bar({"high": 199.9, "low": 100.0}, mother) is False
        assert is_inside_bar({"high": 205.0, "low": 95.0}, mother) is False

    def test_calculate_position_size_validation(self) -> None:
        """Verify input validation and boundary clamping for position sizing."""
        with pytest.raises(ValueError):
            calculate_position_size(-1000.0, 50.0)
        with pytest.raises(ValueError):
            calculate_position_size(100000.0, 0.0)
        with pytest.raises(ValueError):
            calculate_position_size(100000.0, -10.0)

        assert calculate_position_size(100000.0, 92.24) == 7.23
        assert calculate_position_size(100.0, 100.0) == 0.01
        assert calculate_position_size(100000.0, 0.1, max_lot=50.0) == 50.0

    def test_calculate_initial_stop_loss_directions(self) -> None:
        """Verify initial stop loss distance for BUY and SELL."""
        assert calculate_initial_stop_loss("BUY", 1000.0, 20.0) == 970.0
        assert calculate_initial_stop_loss("SELL", 1000.0, 20.0) == 1030.0
        with pytest.raises(ValueError):
            calculate_initial_stop_loss("HOLD", 1000.0, 20.0)

    def test_calculate_trailing_stop_ratchet(self) -> None:
        """Verify trailing stop ratchet behavior."""
        assert calculate_trailing_stop("BUY", 950.0, 1000.0, 20.0) == 970.0
        assert calculate_trailing_stop("BUY", 970.0, 980.0, 20.0) == 970.0
        assert calculate_trailing_stop("SELL", 1050.0, 1000.0, 20.0) == 1030.0
        assert calculate_trailing_stop("SELL", 1030.0, 1020.0, 20.0) == 1030.0
        with pytest.raises(ValueError):
            calculate_trailing_stop("UNKNOWN", 1000.0, 1000.0, 20.0)

    def test_simulation_engine_initialization(self) -> None:
        """Verify GriffSimulationEngine defaults and initial risk check."""
        sim = GriffSimulationEngine(starting_equity=100000.0)
        assert sim.equity == 100000.0
        assert sim.state == "SEARCHING"
        assert sim.check_risk_limits() is True
        assert sim.halted is False

    def test_load_metaapi_token_success(self) -> None:
        """Verify token loading from config_us100.json."""
        token = load_metaapi_token("config_us100.json")
        assert isinstance(token, str)
        assert len(token) > 50

    def test_load_metaapi_token_missing_file_raises(self) -> None:
        """Verify FileNotFoundError on missing configuration file."""
        with pytest.raises(FileNotFoundError):
            load_metaapi_token("non_existent_config.json")

    def test_griff_live_engine_initialization(self) -> None:
        """Verify GriffLiveEngine instantiation attributes."""
        token = load_metaapi_token("config_us100.json")
        engine = GriffLiveEngine(
            token=token,
            account_id="45a2565b-4f53-4bd5-8c58-667b3660430f",
            symbol="US100.cash",
        )
        assert engine.account_id == "45a2565b-4f53-4bd5-8c58-667b3660430f"
        assert engine.symbol == "US100.cash"
        assert engine.risk_pct == 0.01
        assert engine.state == "SEARCHING"
        assert engine.halted is False

    def test_griff_live_engine_risk_limits(self) -> None:
        """Verify live engine risk ceiling and floor enforcement."""
        token = load_metaapi_token("config_us100.json")
        engine = GriffLiveEngine(token=token)
        assert engine.check_risk_limits(100000.0) is True
        assert engine.check_risk_limits(90000.0) is False
        assert engine.halted is True
        assert engine.state == "HALTED"
