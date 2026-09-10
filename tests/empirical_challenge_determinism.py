"""Backtest determinism and reproducibility test harness.

Executes duplicate independent backtest runs for the winning London Reversal
and Omni Breakout profiles across 6-month, 1-year, and 2.5-year time windows.
Asserts that PnL, Sharpe ratio, Max Drawdown, and trade counts match to 6 decimal places.
"""

import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backtester.engine import (
    BacktestEngine,
    BacktestMetrics,
    BacktestProfile,
    EngineType,
    ExitModel,
    PyramidModel,
    RiskModel,
)
from backtester.tournament import TIME_WINDOWS, preload_trading_days


def load_profile_from_file(file_path: Path) -> BacktestProfile:
    """Load JSON profile file and convert to BacktestProfile instance."""
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


def run_single_backtest(
    profile: BacktestProfile,
    trading_days: list,
    starting_equity: float = 100000.0,
    tick_value: float = 1.0,
    commission_per_lot: float = 0.0,
) -> BacktestMetrics:
    """Execute a single backtest with pre-grouped trading days."""
    engine = BacktestEngine(
        profile=profile,
        candles=[],
        starting_equity=starting_equity,
        tick_value=tick_value,
        commission_per_lot=commission_per_lot,
        trading_days=trading_days,
    )
    return engine.run()


def compare_metrics(m1: BacktestMetrics, m2: BacktestMetrics) -> List[Tuple[str, float, float, float, bool]]:
    """Compare two BacktestMetrics instances field by field to 6 decimal places.

    Returns list of tuples: (field_name, val1, val2, diff, is_match).
    """
    fields = [
        ("total_trades", float(m1.total_trades), float(m2.total_trades)),
        ("winning_trades", float(m1.winning_trades), float(m2.winning_trades)),
        ("losing_trades", float(m1.losing_trades), float(m2.losing_trades)),
        ("total_pnl", m1.total_pnl, m2.total_pnl),
        ("max_drawdown", m1.max_drawdown, m2.max_drawdown),
        ("max_drawdown_pct", m1.max_drawdown_pct, m2.max_drawdown_pct),
        ("sharpe_ratio", m1.sharpe_ratio, m2.sharpe_ratio),
        ("profit_factor", m1.profit_factor, m2.profit_factor),
        ("win_rate", m1.win_rate, m2.win_rate),
        ("ending_equity", m1.ending_equity, m2.ending_equity),
    ]

    comparisons = []
    for name, v1, v2 in fields:
        diff = abs(v1 - v2)
        match = round(diff, 6) == 0.0
        comparisons.append((name, v1, v2, diff, match))
    return comparisons


def execute_determinism_suite() -> Dict[str, Any]:
    """Run full determinism verification across both winners and all windows."""
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data" / "raw"
    profiles_dir = project_root / "profiles"

    london_path = profiles_dir / "london_winner.json"
    omni_path = profiles_dir / "omni_winner.json"

    london_prof = load_profile_from_file(london_path)
    omni_prof = load_profile_from_file(omni_path)

    windows = ["6m", "1y", "2.5y"]
    results = {}
    all_passed = True

    for win in windows:
        window_dict = {win: TIME_WINDOWS[win]}

        london_days_map = preload_trading_days(
            str(data_dir), [london_prof.instrument], window_dict, engine_type="london"
        )
        london_days = london_days_map[(london_prof.instrument, win)]

        l_run1 = run_single_backtest(london_prof, london_days)
        l_run2 = run_single_backtest(london_prof, london_days)
        l_diffs = compare_metrics(l_run1, l_run2)
        l_passed = all(item[4] for item in l_diffs)

        omni_days_map = preload_trading_days(
            str(data_dir), [omni_prof.instrument], window_dict, engine_type="omni"
        )
        omni_days = omni_days_map[(omni_prof.instrument, win)]

        o_run1 = run_single_backtest(omni_prof, omni_days)
        o_run2 = run_single_backtest(omni_prof, omni_days)
        o_diffs = compare_metrics(o_run1, o_run2)
        o_passed = all(item[4] for item in o_diffs)

        if not (l_passed and o_passed):
            all_passed = False

        results[win] = {
            "london": {
                "passed": l_passed,
                "trades": l_run1.total_trades,
                "pnl": l_run1.total_pnl,
                "sharpe": l_run1.sharpe_ratio,
                "max_dd_pct": l_run1.max_drawdown_pct,
                "comparisons": l_diffs,
            },
            "omni": {
                "passed": o_passed,
                "trades": o_run1.total_trades,
                "pnl": o_run1.total_pnl,
                "sharpe": o_run1.sharpe_ratio,
                "max_dd_pct": o_run1.max_drawdown_pct,
                "comparisons": o_diffs,
            },
        }

    return {"all_passed": all_passed, "windows": results}


if __name__ == "__main__":
    res = execute_determinism_suite()
    print(f"Overall Determinism Verification: {'PASSED' if res['all_passed'] else 'FAILED'}")
    for win, data in res["windows"].items():
        print(f"\n--- Window: {win} ---")
        l = data["london"]
        print(f"London Reversal: {'PASSED' if l['passed'] else 'FAILED'} | Trades: {l['trades']} | PnL: ${l['pnl']:.2f} | Sharpe: {l['sharpe']:.4f} | MaxDD: {l['max_dd_pct']:.4%}")
        o = data["omni"]
        print(f"Omni Breakout:   {'PASSED' if o['passed'] else 'FAILED'} | Trades: {o['trades']} | PnL: ${o['pnl']:.2f} | Sharpe: {o['sharpe']:.4f} | MaxDD: {o['max_dd_pct']:.4%}")
