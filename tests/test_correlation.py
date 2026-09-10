"""Unit and integration test suite for cross-engine correlation and diversification."""

import json
from pathlib import Path
import pytest

from backtester.correlation import (
    CrossEngineCorrelationAnalyzer,
    calculate_max_drawdown_pct,
    calculate_pearson_correlation,
    calculate_sharpe,
)


class TestCorrelationMathPrimitives:
    """Tests core mathematical primitives for returns correlation and risk."""

    def test_calculate_pearson_correlation_identical_series(self) -> None:
        """Verify correlation of identical series equals 1.0."""
        s1 = [0.01, 0.02, -0.01, 0.03, -0.02]
        s2 = [0.01, 0.02, -0.01, 0.03, -0.02]
        corr = calculate_pearson_correlation(s1, s2)
        assert corr == pytest.approx(1.0, rel=1e-5)

    def test_calculate_pearson_correlation_opposite_series(self) -> None:
        """Verify correlation of perfectly inverted series equals -1.0."""
        s1 = [0.01, 0.02, -0.01, 0.03, -0.02]
        s2 = [-0.01, -0.02, 0.01, -0.03, 0.02]
        corr = calculate_pearson_correlation(s1, s2)
        assert corr == pytest.approx(-1.0, rel=1e-5)

    def test_calculate_pearson_correlation_orthogonal_series(self) -> None:
        """Verify correlation of uncorrelated series equals 0.0."""
        s1 = [1.0, -1.0, 1.0, -1.0]
        s2 = [1.0, 1.0, -1.0, -1.0]
        corr = calculate_pearson_correlation(s1, s2)
        assert corr == pytest.approx(0.0, abs=1e-5)

    def test_calculate_sharpe_ratio_positive(self) -> None:
        """Verify annualized Sharpe computation on positive return series."""
        returns = [0.01, 0.015, 0.008, 0.012, 0.009]
        sharpe = calculate_sharpe(returns)
        assert sharpe > 0.0

    def test_calculate_max_drawdown_pct_peak_to_trough(self) -> None:
        """Verify max drawdown percentage calculation."""
        curve = [100.0, 110.0, 99.0, 105.0, 88.0, 120.0]
        max_dd = calculate_max_drawdown_pct(curve)
        assert max_dd == pytest.approx(0.20, rel=1e-3)


class TestCrossEngineCorrelationIntegration:
    """Tests integration with backtesting engine and verification threshold."""

    def test_cross_engine_correlation_constraint_across_all_windows(self) -> None:
        """Verify correlation between London and Omni winners <= 0.30 across all windows."""
        analyzer = CrossEngineCorrelationAnalyzer(
            london_profile_path="profiles/london_winner.json",
            omni_profile_path="profiles/omni_winner.json",
            data_path="data/raw/US100.cash_m1_2024-01-01_2026-09-09.csv",
        )
        results = analyzer.run_all_windows()
        assert results["overall_verification_passed"] is True

        for w_name, metrics in results["windows"].items():
            assert metrics["passed_correlation_constraint"] is True
            assert metrics["correlation"] <= 0.30

    def test_correlation_json_output_schema(self, tmp_path: Path) -> None:
        """Verify correlation report writes valid JSON conforming to expected schema."""
        out_file = tmp_path / "correlation_test.json"
        analyzer = CrossEngineCorrelationAnalyzer(
            london_profile_path="profiles/london_winner.json",
            omni_profile_path="profiles/omni_winner.json",
            data_path="data/raw/US100.cash_m1_2024-01-01_2026-09-09.csv",
        )
        results = analyzer.run_all_windows(output_path=str(out_file))
        assert out_file.exists()

        with open(out_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "metadata" in data
        assert "windows" in data
        assert "overall_verification_passed" in data
        assert "2.5y" in data["windows"]
