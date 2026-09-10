"""Independent cross-engine correlation and portfolio diversification challenger.

Independently recalculates Pearson and Spearman daily PnL correlation coefficients
between London Reversal and Omni Breakout across 6-month, 1-year, and 2.5-year windows.
Challenges the assertion that rho <= 0.30 and evaluates joint tail risk / co-drawdowns.
"""

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backtester.engine import (
    BacktestEngine,
    BacktestProfile,
    EngineType,
    ExitModel,
    LondonReversalSimulator,
    OmniBreakoutSimulator,
    PyramidModel,
    RiskModel,
    RiskSizer,
)
from backtester.tournament import TIME_WINDOWS, preload_trading_days


def load_profile(file_path: Path) -> BacktestProfile:
    """Load JSON profile into BacktestProfile."""
    with open(file_path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    dims = doc["dimensions"]
    return BacktestProfile(
        engine=EngineType(doc["engine"]),
        risk_model=RiskModel(dims["risk_model"]),
        entry_mode=dims["entry_mode"],
        pyramid_model=PyramidModel(dims["pyramid_model"]),
        exit_model=ExitModel(dims["exit_model"]),
        filters=dims.get("filters", []),
        instrument=doc.get("instrument", "US100.cash"),
    )


def compute_pearson(x: List[float], y: List[float]) -> float:
    """Compute Pearson correlation coefficient from two series."""
    n = len(x)
    if n != len(y) or n < 2:
        return 0.0

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    var_x = sum((a - mean_x) ** 2 for a in x)
    var_y = sum((b - mean_y) ** 2 for b in y)

    denom = math.sqrt(var_x * var_y)
    if denom <= 1e-12:
        return 0.0
    return max(-1.0, min(1.0, cov / denom))


def compute_ranks(series: List[float]) -> List[float]:
    """Compute fractional ranks for Spearman rank correlation."""
    indices = sorted(range(len(series)), key=lambda i: series[i])
    ranks = [0.0] * len(series)
    i = 0
    n = len(series)
    while i < n:
        j = i
        while j < n - 1 and series[indices[j]] == series[indices[j + 1]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indices[k]] = avg_rank
        i = j + 1
    return ranks


def compute_spearman(x: List[float], y: List[float]) -> float:
    """Compute Spearman rank correlation coefficient from two series."""
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    rx = compute_ranks(x)
    ry = compute_ranks(y)
    return compute_pearson(rx, ry)


def simulate_engine_daily_pnls(
    profile: BacktestProfile,
    trading_days: list,
    starting_equity: float = 100000.0,
    tick_value: float = 1.0,
) -> Dict[str, float]:
    """Simulate engine across days and extract day-by-day PnL dictionary."""
    daily_pnl = {}
    equity = starting_equity
    risk_sizer = RiskSizer(profile.risk_model, starting_equity, tick_value=tick_value)

    for day_item in trading_days:
        day_date, day_candles, range_high, range_low, atr = day_item
        day_str = day_date.strftime("%Y-%m-%d")

        if range_high is None or range_low is None:
            daily_pnl[day_str] = 0.0
            continue

        risk_sizer.record_equity(equity)
        if profile.engine == EngineType.LONDON_REVERSAL:
            sim = LondonReversalSimulator(profile, equity, tick_value)
            trades = sim.simulate_day(day_candles, range_high, range_low, atr, risk_sizer)
            equity = sim.equity
        elif profile.engine == EngineType.OMNI_BREAKOUT:
            sim = OmniBreakoutSimulator(profile, equity, tick_value)
            trades = sim.simulate_day(day_candles, range_high, range_low, atr, risk_sizer)
            equity = sim.equity
        else:
            daily_pnl[day_str] = 0.0
            continue

        day_trades_pnl = sum(t.pnl_dollars for t in trades)
        daily_pnl[day_str] = day_trades_pnl

    return daily_pnl


def evaluate_cross_engine_correlation() -> Dict[str, Any]:
    """Independently evaluate cross-engine correlation across all windows."""
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data" / "raw"
    profiles_dir = project_root / "profiles"

    london_prof = load_profile(profiles_dir / "london_winner.json")
    omni_prof = load_profile(profiles_dir / "omni_winner.json")

    windows = ["6m", "1y", "2.5y"]
    results = {}
    all_passed = True

    for win in windows:
        window_dict = {win: TIME_WINDOWS[win]}

        l_days_map = preload_trading_days(str(data_dir), [london_prof.instrument], window_dict, engine_type="london")
        l_days = l_days_map[(london_prof.instrument, win)]

        o_days_map = preload_trading_days(str(data_dir), [omni_prof.instrument], window_dict, engine_type="omni")
        o_days = o_days_map[(omni_prof.instrument, win)]

        london_pnls = simulate_engine_daily_pnls(london_prof, l_days)
        omni_pnls = simulate_engine_daily_pnls(omni_prof, o_days)

        common_days = sorted(set(london_pnls.keys()).intersection(set(omni_pnls.keys())))

        l_series = [london_pnls[d] for d in common_days]
        o_series = [omni_pnls[d] for d in common_days]

        pearson_rho = compute_pearson(l_series, o_series)
        spearman_rho = compute_spearman(l_series, o_series)

        co_loss_days = sum(1 for a, b in zip(l_series, o_series) if a < 0 and b < 0)
        co_loss_pct = (co_loss_days / len(common_days)) if common_days else 0.0

        passed_threshold = pearson_rho <= 0.30
        if not passed_threshold:
            all_passed = False

        results[win] = {
            "total_days": len(common_days),
            "pearson_rho": pearson_rho,
            "spearman_rho": spearman_rho,
            "passed_threshold": passed_threshold,
            "co_loss_days": co_loss_days,
            "co_loss_pct": co_loss_pct,
            "london_pnl_sum": sum(l_series),
            "omni_pnl_sum": sum(o_series),
            "portfolio_pnl_sum": sum(l_series) + sum(o_series),
        }

    return {"all_passed": all_passed, "windows": results}


if __name__ == "__main__":
    report = evaluate_cross_engine_correlation()
    print(f"Overall Correlation Verification: {'PASSED' if report['all_passed'] else 'FAILED'}")
    for win, d in report["windows"].items():
        print(f"\n--- Window: {win} ({d['total_days']} days) ---")
        print(f"Pearson Correlation (rho):  {d['pearson_rho']:+.4f} (Constraint rho <= 0.30: {d['passed_threshold']})")
        print(f"Spearman Rank Correlation:  {d['spearman_rho']:+.4f}")
        print(f"Co-Loss Days:              {d['co_loss_days']} / {d['total_days']} ({d['co_loss_pct']:.2%})")
        print(f"London PnL:                ${d['london_pnl_sum']:.2f}")
        print(f"Omni PnL:                  ${d['omni_pnl_sum']:.2f}")
        print(f"Combined Portfolio PnL:    ${d['portfolio_pnl_sum']:.2f}")
    if not report["all_passed"]:
        sys.exit(1)
    sys.exit(0)
