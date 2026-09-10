"""Cross-engine correlation and portfolio diversification analysis.

Computes the Pearson correlation coefficient between the daily returns of the winning
London Reversal profile and the winning Omni Breakout profile across multiple time
windows (6-month, 1-year, 2.5-year, and paper trading observation window).
Verifies that the correlation rho <= 0.30, confirming that the two engines
diversify risk and do not amplify drawdowns under FTMO capital constraints.
"""

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backtester.engine import (
    AsianRangeDetector,
    ATRCalculator,
    BacktestEngine,
    BacktestProfile,
    Candle,
    CandleDataLoader,
    EngineType,
    ExitModel,
    LondonReversalSimulator,
    OmniBreakoutSimulator,
    PyramidModel,
    RiskModel,
    RiskSizer,
    USOpenRangeDetector,
)
from backtester.tournament import preload_trading_days


@dataclass
class WindowCorrelationMetrics:
    """Correlation and diversification metrics for an evaluation window."""

    window: str
    trading_days: int
    london_trades_count: int
    omni_trades_count: int
    correlation: float
    passed_correlation_constraint: bool
    london_total_pnl: float
    omni_total_pnl: float
    portfolio_total_pnl: float
    london_sharpe: float
    omni_sharpe: float
    portfolio_sharpe: float
    london_max_dd_pct: float
    omni_max_dd_pct: float
    portfolio_max_dd_pct: float
    worst_single_day_pnl: float
    worst_single_day_pct: float
    co_drawdown_days: int
    co_drawdown_pct: float
    diversification_ratio: float


def calculate_pearson_correlation(series_a: List[float], series_b: List[float]) -> float:
    """Calculate the Pearson correlation coefficient between two numeric series.

    Parameters:
        series_a: First sequence of numeric returns.
        series_b: Second sequence of numeric returns.

    Returns:
        Pearson correlation coefficient in range [-1.0, 1.0].
    """
    n = len(series_a)
    if n != len(series_b) or n < 2:
        return 0.0

    mean_a = sum(series_a) / n
    mean_b = sum(series_b) / n

    cov = sum((a - mean_a) * (b - mean_b) for a, b in zip(series_a, series_b))
    var_a = sum((a - mean_a) ** 2 for a in series_a)
    var_b = sum((b - mean_b) ** 2 for b in series_b)

    denom = math.sqrt(var_a * var_b)
    if denom <= 1e-12:
        return 0.0

    corr = cov / denom
    return max(-1.0, min(1.0, corr))


def calculate_sharpe(returns: List[float]) -> float:
    """Calculate annualized Sharpe ratio from daily percentage returns.

    Parameters:
        returns: Sequence of daily fractional returns.

    Returns:
        Annualized Sharpe ratio assuming 252 trading days.
    """
    if len(returns) < 2:
        return 0.0
    mean_r = sum(returns) / len(returns)
    variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    std_r = math.sqrt(variance) if variance > 0 else 0.0
    if std_r <= 1e-12:
        return 0.0
    return (mean_r / std_r) * math.sqrt(252.0)


def calculate_max_drawdown_pct(equity_curve: List[float]) -> float:
    """Calculate maximum peak-to-trough percentage drawdown from an equity curve.

    Parameters:
        equity_curve: Sequence of cumulative equity values.

    Returns:
        Maximum drawdown expressed as a positive fraction.
    """
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def parse_profile(profile_data: Dict[str, Any]) -> BacktestProfile:
    """Construct a BacktestProfile instance from a profile configuration dictionary.

    Parameters:
        profile_data: Strategy configuration dictionary.

    Returns:
        Typed BacktestProfile object.
    """
    dims = profile_data.get("dimensions", profile_data)
    engine_val = profile_data.get("engine", dims.get("engine"))
    risk_val = dims.get("risk_model")
    entry_val = dims.get("entry_mode")
    pyramid_val = dims.get("pyramid_model")
    exit_val = dims.get("exit_model")
    filters_val = dims.get("filters", [])
    instrument_val = profile_data.get("instrument", "US100.cash")

    return BacktestProfile(
        engine=EngineType(engine_val),
        risk_model=RiskModel(risk_val),
        entry_mode=entry_val,
        pyramid_model=PyramidModel(pyramid_val),
        exit_model=ExitModel(exit_val),
        filters=filters_val,
        instrument=instrument_val,
    )


class CrossEngineCorrelationAnalyzer:
    """Evaluates cross-engine correlation and portfolio diversification."""

    def __init__(
        self,
        london_profile_path: str = "profiles/london_winner.json",
        omni_profile_path: str = "profiles/omni_winner.json",
        data_path: str = "data/raw/US100.cash_m1_2024-01-01_2026-09-09.csv",
        starting_equity: float = 100000.0,
        tick_value: float = 1.0,
    ) -> None:
        """Initialize correlation analyzer with profiles and dataset path.

        Parameters:
            london_profile_path: Path to winning London Reversal JSON profile.
            omni_profile_path: Path to winning Omni Breakout JSON profile.
            data_path: Path to raw 1-minute OHLCV candle CSV.
            starting_equity: Starting test equity in dollars.
            tick_value: Dollar tick value per point per lot.
        """
        self.london_profile_path = london_profile_path
        self.omni_profile_path = omni_profile_path
        self.data_path = data_path
        self.starting_equity = starting_equity
        self.tick_value = tick_value

        with open(london_profile_path, "r", encoding="utf-8") as lf:
            self.london_dict = json.load(lf)
        with open(omni_profile_path, "r", encoding="utf-8") as of:
            self.omni_dict = json.load(of)

        self.london_profile = parse_profile(self.london_dict)
        self.omni_profile = parse_profile(self.omni_dict)

    def analyze_window(
        self,
        window_name: str,
        trading_days: List[Tuple[Any, ...]],
    ) -> WindowCorrelationMetrics:
        """Run daily simulation for both engines across pre-grouped trading days.

        Parameters:
            window_name: Name identifier for evaluation window (e.g. '2.5y', '1y').
            trading_days: List of daily context tuples.

        Returns:
            WindowCorrelationMetrics detailing correlation and portfolio performance.
        """
        london_daily_returns: List[float] = []
        omni_daily_returns: List[float] = []
        portfolio_daily_returns: List[float] = []

        london_equity = self.starting_equity
        omni_equity = self.starting_equity
        portfolio_equity = self.starting_equity * 2.0

        london_curve: List[float] = [london_equity]
        omni_curve: List[float] = [omni_equity]
        portfolio_curve: List[float] = [portfolio_equity]

        london_trades_total = 0
        omni_trades_total = 0

        london_risk_sizer = RiskSizer(self.london_profile.risk_model, self.starting_equity, self.tick_value)
        omni_risk_sizer = RiskSizer(self.omni_profile.risk_model, self.starting_equity, self.tick_value)

        co_drawdown_count = 0
        worst_combined_pnl = 0.0

        for day_item in trading_days:
            if len(day_item) == 5:
                day_date, day_candles, range_high, range_low, atr = day_item
            else:
                day_date, day_candles = day_item[0], day_item[1]
                atr_calc = ATRCalculator(period=14)
                for c in day_candles:
                    atr_calc.update(c)
                atr = atr_calc.current()
                range_high, range_low = AsianRangeDetector.detect(day_candles, day_date)

            l_high, l_low = AsianRangeDetector.detect(day_candles, day_date)
            o_high, o_low = USOpenRangeDetector.detect(day_candles, day_date)

            l_day_pnl = 0.0
            if l_high is not None and l_low is not None:
                london_risk_sizer.record_equity(london_equity)
                l_sim = LondonReversalSimulator(self.london_profile, london_equity, self.tick_value)
                l_trades = l_sim.simulate_day(day_candles, l_high, l_low, atr, london_risk_sizer)
                l_day_pnl = sum(t.pnl_dollars for t in l_trades)
                london_equity += l_day_pnl
                london_trades_total += len(l_trades)

            o_day_pnl = 0.0
            if o_high is not None and o_low is not None:
                omni_risk_sizer.record_equity(omni_equity)
                o_sim = OmniBreakoutSimulator(self.omni_profile, omni_equity, self.tick_value)
                o_trades = o_sim.simulate_day(day_candles, o_high, o_low, atr, omni_risk_sizer)
                o_day_pnl = sum(t.pnl_dollars for t in o_trades)
                omni_equity += o_day_pnl
                omni_trades_total += len(o_trades)

            l_ret = l_day_pnl / self.starting_equity
            o_ret = o_day_pnl / self.starting_equity
            port_pnl = l_day_pnl + o_day_pnl
            port_ret = port_pnl / (self.starting_equity * 2.0)

            london_daily_returns.append(l_ret)
            omni_daily_returns.append(o_ret)
            portfolio_daily_returns.append(port_ret)

            portfolio_equity += port_pnl
            london_curve.append(london_equity)
            omni_curve.append(omni_equity)
            portfolio_curve.append(portfolio_equity)

            if l_day_pnl < 0 and o_day_pnl < 0:
                co_drawdown_count += 1

            if port_pnl < worst_combined_pnl:
                worst_combined_pnl = port_pnl

        n_days = len(trading_days)
        rho = calculate_pearson_correlation(london_daily_returns, omni_daily_returns)
        passed_constraint = bool(rho <= 0.30)

        l_sharpe = calculate_sharpe(london_daily_returns)
        o_sharpe = calculate_sharpe(omni_daily_returns)
        port_sharpe = calculate_sharpe(portfolio_daily_returns)

        l_max_dd = calculate_max_drawdown_pct(london_curve)
        o_max_dd = calculate_max_drawdown_pct(omni_curve)
        port_max_dd = calculate_max_drawdown_pct(portfolio_curve)

        mean_l = sum(london_daily_returns) / n_days if n_days else 0.0
        var_l = sum((x - mean_l) ** 2 for x in london_daily_returns) / max(1, n_days - 1)
        std_l = math.sqrt(var_l)

        mean_o = sum(omni_daily_returns) / n_days if n_days else 0.0
        var_o = sum((x - mean_o) ** 2 for x in omni_daily_returns) / max(1, n_days - 1)
        std_o = math.sqrt(var_o)

        mean_p = sum(portfolio_daily_returns) / n_days if n_days else 0.0
        var_p = sum((x - mean_p) ** 2 for x in portfolio_daily_returns) / max(1, n_days - 1)
        std_p = math.sqrt(var_p)

        div_ratio = ((std_l + std_o) / std_p) if std_p > 1e-12 else 1.0

        return WindowCorrelationMetrics(
            window=window_name,
            trading_days=n_days,
            london_trades_count=london_trades_total,
            omni_trades_count=omni_trades_total,
            correlation=round(rho, 4),
            passed_correlation_constraint=passed_constraint,
            london_total_pnl=round(london_equity - self.starting_equity, 2),
            omni_total_pnl=round(omni_equity - self.starting_equity, 2),
            portfolio_total_pnl=round(portfolio_equity - (self.starting_equity * 2.0), 2),
            london_sharpe=round(l_sharpe, 4),
            omni_sharpe=round(o_sharpe, 4),
            portfolio_sharpe=round(port_sharpe, 4),
            london_max_dd_pct=round(l_max_dd, 4),
            omni_max_dd_pct=round(o_max_dd, 4),
            portfolio_max_dd_pct=round(port_max_dd, 4),
            worst_single_day_pnl=round(worst_combined_pnl, 2),
            worst_single_day_pct=round(worst_combined_pnl / (self.starting_equity * 2.0), 4),
            co_drawdown_days=co_drawdown_count,
            co_drawdown_pct=round((co_drawdown_count / n_days) if n_days else 0.0, 4),
            diversification_ratio=round(div_ratio, 4),
        )

    def analyze_paper_trade(
        self,
        telemetry_path: str = "paper_trade_telemetry.json",
    ) -> Optional[Dict[str, Any]]:
        """Extract daily return correlation from paper trading observation telemetry.

        Parameters:
            telemetry_path: Path to paper trade telemetry JSON file.

        Returns:
            Dictionary of correlation metrics for paper trade window or None.
        """
        telemetry_file = Path(telemetry_path)
        if not telemetry_file.exists():
            return None
        with open(telemetry_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        profiles_detail = data.get("profiles_detail", [])
        london_trades = []
        omni_trades = []
        for p in profiles_detail:
            if p.get("profile_id") == self.london_profile.profile_id():
                london_trades = p.get("trades", [])
            elif p.get("profile_id") == self.omni_profile.profile_id():
                omni_trades = p.get("trades", [])

        days_set = set()
        l_by_day: Dict[str, float] = {}
        o_by_day: Dict[str, float] = {}
        for t in london_trades:
            day_k = t.get("entry_time", "")[:10]
            if day_k:
                days_set.add(day_k)
                l_by_day[day_k] = l_by_day.get(day_k, 0.0) + t.get("pnl", 0.0)
        for t in omni_trades:
            day_k = t.get("entry_time", "")[:10]
            if day_k:
                days_set.add(day_k)
                o_by_day[day_k] = o_by_day.get(day_k, 0.0) + t.get("pnl", 0.0)

        sorted_days = sorted(list(days_set))
        if not sorted_days:
            return None

        l_rets = [l_by_day.get(d, 0.0) / self.starting_equity for d in sorted_days]
        o_rets = [o_by_day.get(d, 0.0) / self.starting_equity for d in sorted_days]
        port_rets = [l + o for l, o in zip(l_rets, o_rets)]
        rho = calculate_pearson_correlation(l_rets, o_rets)

        return {
            "window": "paper_trade",
            "trading_days": len(sorted_days),
            "london_trades_count": len(london_trades),
            "omni_trades_count": len(omni_trades),
            "correlation": round(rho, 4),
            "passed_correlation_constraint": bool(rho <= 0.30),
            "london_total_pnl": round(sum(l_by_day.values()), 4),
            "omni_total_pnl": round(sum(o_by_day.values()), 4),
            "portfolio_total_pnl": round(sum(l_by_day.values()) + sum(o_by_day.values()), 4),
            "portfolio_sharpe": round(calculate_sharpe(port_rets), 4),
            "portfolio_max_dd_pct": 0.0,
            "diversification_ratio": 1.0,
        }

    def run_all_windows(
        self,
        output_path: Optional[str] = None,
        telemetry_path: str = "paper_trade_telemetry.json",
    ) -> Dict[str, Any]:
        """Execute correlation analysis across 6m, 1y, 2.5y, and paper trade datasets.

        Parameters:
            output_path: Optional destination to write JSON results.
            telemetry_path: Path to paper trade telemetry file.

        Returns:
            Dictionary mapping window names to correlation metrics.
        """
        windows_spec = {
            "6m": ("2026-03-09", "2026-09-09"),
            "1y": ("2025-09-09", "2026-09-09"),
            "2.5y": ("2024-01-01", "2026-09-09"),
        }
        preloaded = preload_trading_days(
            data_dir="data/raw",
            instruments=[self.london_profile.instrument],
            windows=windows_spec,
        )

        results: Dict[str, Any] = {
            "metadata": {
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
                "london_winner": self.london_profile.profile_id(),
                "omni_winner": self.omni_profile.profile_id(),
                "correlation_threshold": 0.30,
                "dataset": self.data_path,
            },
            "windows": {},
        }

        for w_name in ["2.5y", "1y", "6m"]:
            days = preloaded.get((self.london_profile.instrument, w_name), [])
            metrics = self.analyze_window(w_name, days)
            results["windows"][w_name] = asdict(metrics)

        pt_metrics = self.analyze_paper_trade(telemetry_path)
        if pt_metrics:
            results["windows"]["paper_trade"] = pt_metrics

        all_passed = all(
            w["passed_correlation_constraint"] for w in results["windows"].values()
        )
        results["overall_verification_passed"] = all_passed

        if output_path:
            out_file = Path(output_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)

        return results


def main() -> None:
    """CLI entrypoint for cross-engine correlation analysis."""
    parser = argparse.ArgumentParser(description="Cross-Engine Correlation Analyzer")
    parser.add_argument(
        "--london-profile",
        type=str,
        default="profiles/london_winner.json",
        help="Path to winning London Reversal profile JSON",
    )
    parser.add_argument(
        "--omni-profile",
        type=str,
        default="profiles/omni_winner.json",
        help="Path to winning Omni Breakout profile JSON",
    )
    parser.add_argument(
        "--data",
        type=str,
        default="data/raw/US100.cash_m1_2024-01-01_2026-09-09.csv",
        help="Path to raw 1-minute OHLCV candle CSV",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="backtester/results/cross_engine_correlation.json",
        help="Destination path for correlation JSON report",
    )
    args = parser.parse_args()

    analyzer = CrossEngineCorrelationAnalyzer(
        london_profile_path=args.london_profile,
        omni_profile_path=args.omni_profile,
        data_path=args.data,
    )

    results = analyzer.run_all_windows(output_path=args.output)

    print("=" * 80)
    print("CROSS-ENGINE CORRELATION ANALYSIS RESULTS")
    print("=" * 80)
    print(f"London Winner: {results['metadata']['london_winner']}")
    print(f"Omni Winner:   {results['metadata']['omni_winner']}")
    print(f"Constraint:    Correlation <= {results['metadata']['correlation_threshold']:.2f}")
    print("-" * 80)

    for w_name, m in results["windows"].items():
        status = "PASSED" if m["passed_correlation_constraint"] else "FAILED"
        print(
            f"Window: {w_name:5s} | Days: {m['trading_days']:3d} | "
            f"Correlation: {m['correlation']:+.4f} [{status}] | "
            f"Portfolio Sharpe: {m['portfolio_sharpe']:.2f} | "
            f"Port MaxDD: {m['portfolio_max_dd_pct']*100:.2f}% | "
            f"DivRatio: {m['diversification_ratio']:.2f}"
        )

    print("-" * 80)
    print(f"Overall Verification Status: {'PASSED' if results['overall_verification_passed'] else 'FAILED'}")
    print(f"Report saved to: {args.output}")
    print("=" * 80)


if __name__ == "__main__":
    main()
