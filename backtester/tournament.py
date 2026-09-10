"""Profile generator and tournament runner for Odin FTMO v2.

Generates all profile combinations, runs backtests across multiple time windows,
ranks profiles by tournament score, and exports top-performing profiles.
"""

import csv
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
BACKTESTER_DIR = Path(__file__).resolve().parent
if str(BACKTESTER_DIR) not in sys.path:
    sys.path.insert(0, str(BACKTESTER_DIR))

try:
    from backtester.engine import (
        BacktestEngine,
        BacktestMetrics,
        BacktestProfile,
        Candle,
        CandleDataLoader,
        EngineType,
        ExitModel,
        PyramidModel,
        RiskModel,
        ATRCalculator,
        AsianRangeDetector,
        USOpenRangeDetector,
    )
except ImportError:
    from engine import (
        BacktestEngine,
        BacktestMetrics,
        BacktestProfile,
        Candle,
        CandleDataLoader,
        EngineType,
        ExitModel,
        PyramidModel,
        RiskModel,
        ATRCalculator,
        AsianRangeDetector,
        USOpenRangeDetector,
    )

try:
    from verifier.validator import validate_profile
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from verifier.validator import validate_profile

LONDON_ENTRY_MODES = [
    "blind_limit",
    "sweep_confirmation",
    "dynamic_buffer",
    "time_weighted",
    "order_flow_spread_gate",
    "multi_timeframe",
    "hybrid_sweep_time_spread",
]

OMNI_ENTRY_MODES = [
    "stop_order_at_range",
    "close_confirmation",
    "volume_spike_gate",
    "retest_entry",
    "momentum_threshold",
    "dual_timeframe",
    "hybrid_retest_volume_spread",
]

LONDON_FILTER_COMBOS = [
    [],
    ["atr_gate"],
    ["day_of_week"],
    ["spread_gate"],
    ["atr_gate", "day_of_week"],
    ["atr_gate", "spread_gate"],
    ["atr_gate", "spread_gate", "day_of_week"],
]

OMNI_FILTER_COMBOS = [
    [],
    ["orb_width_gate"],
    ["day_of_week"],
    ["spread_gate"],
    ["orb_width_gate", "day_of_week"],
    ["orb_width_gate", "spread_gate"],
    ["orb_width_gate", "spread_gate", "day_of_week"],
]

TIME_WINDOWS = {
    "6m": ("2026-03-09", "2026-09-09"),
    "1y": ("2025-09-09", "2026-09-09"),
    "2.5y": ("2024-01-01", "2026-09-09"),
}

_PRELOADED_DAYS_CACHE: Dict[Tuple[str, str], List[Tuple[datetime, List[Candle]]]] = {}


def generate_london_profiles(instruments: List[str]) -> List[BacktestProfile]:
    """Generate all London Reversal profile combinations."""
    profiles = []
    risk_models = list(RiskModel)
    pyramid_models = list(PyramidModel)
    exit_models = list(ExitModel)

    for instrument in instruments:
        for risk, entry, pyramid, exit_m, filters in product(
            risk_models, LONDON_ENTRY_MODES, pyramid_models, exit_models, LONDON_FILTER_COMBOS
        ):
            profiles.append(BacktestProfile(
                engine=EngineType.LONDON_REVERSAL,
                risk_model=risk,
                entry_mode=entry,
                pyramid_model=pyramid,
                exit_model=exit_m,
                filters=filters,
                instrument=instrument,
            ))
    return profiles


def generate_omni_profiles(instruments: List[str]) -> List[BacktestProfile]:
    """Generate all Omni Breakout profile combinations."""
    profiles = []
    risk_models = list(RiskModel)
    pyramid_models = list(PyramidModel)
    exit_models = list(ExitModel)

    for instrument in instruments:
        for risk, entry, pyramid, exit_m, filters in product(
            risk_models, OMNI_ENTRY_MODES, pyramid_models, exit_models, OMNI_FILTER_COMBOS
        ):
            profiles.append(BacktestProfile(
                engine=EngineType.OMNI_BREAKOUT,
                risk_model=risk,
                entry_mode=entry,
                pyramid_model=pyramid,
                exit_model=exit_m,
                filters=filters,
                instrument=instrument,
            ))
    return profiles


def profile_to_dict(profile: BacktestProfile) -> Dict[str, Any]:
    """Convert a BacktestProfile into standard profile dictionary for schema and verifier."""
    return {
        "profile_id": profile.profile_id(),
        "engine": profile.engine.value,
        "instrument": profile.instrument,
        "version": "1.0.0",
        "dimensions": {
            "risk_model": profile.risk_model.value,
            "entry_mode": profile.entry_mode,
            "pyramid_model": profile.pyramid_model.value,
            "exit_model": profile.exit_model.value,
            "filters": profile.filters,
        },
        "parameters": {
            "sl_pts": 40.0,
            "tp_pts": 20.0,
            "buffer_pts": 0.0,
            "trail_trigger_pts": 15.0,
            "trail_dist_pts": 15.0,
            "max_spread_pts": 3.0,
            "max_tranches": 1 if profile.pyramid_model == PyramidModel.NO_PYRAMID else 3,
            "cooldown_seconds": 60.0,
            "base_lot_size": 5.0,
        },
        "risk_bounds": {
            "max_risk_pct": 0.0075,
            "max_daily_loss_pct": 0.045,
            "account_floor": 90000.0,
            "max_lot_size": 15.0,
        },
    }


def prescreen_profiles(profiles: List[BacktestProfile], starting_equity: float = 100000.0) -> List[BacktestProfile]:
    """Pre-screen candidate profiles against formal verification rules and FTMO invariants."""
    valid_profiles = []
    for profile in profiles:
        prof_dict = profile_to_dict(profile)
        is_valid, violations, _ = validate_profile(prof_dict)
        if is_valid:
            valid_profiles.append(profile)
    return valid_profiles


def preload_trading_days(
    data_dir: str,
    instruments: List[str],
    windows: Dict[str, Tuple[str, str]],
    engine_type: Optional[str] = None,
) -> Dict[Tuple[str, str], list]:
    """Pre-load candles and pre-compute daily trading context once for all instruments and time windows."""
    loader = CandleDataLoader(data_dir)
    preloaded = {}

    for instrument in instruments:
        all_starts = [datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc) for s, _ in windows.values()]
        all_ends = [datetime.strptime(e, "%Y-%m-%d").replace(tzinfo=timezone.utc) for _, e in windows.values()]
        min_start = min(all_starts)
        max_end = max(all_ends)

        candles = loader.load(instrument, min_start, max_end)
        if not candles:
            continue

        grouped_days = BacktestEngine.group_candles_by_day(candles)

        if engine_type in ("london", "omni"):
            atr_calc = ATRCalculator(period=14)
            precomputed_days = []
            for day_date, day_candles in grouped_days:
                for c in day_candles:
                    atr_calc.update(c)
                atr = atr_calc.current()
                if engine_type == "london":
                    range_high, range_low = AsianRangeDetector.detect(day_candles, day_date)
                    session_candles = [c for c in day_candles if 7 <= c.timestamp.hour < 13]
                else:
                    range_high, range_low = USOpenRangeDetector.detect(day_candles, day_date)
                    session_candles = [
                        c for c in day_candles
                        if (c.timestamp.hour == 14 and c.timestamp.minute >= 30) or (14 < c.timestamp.hour < 20)
                    ]
                precomputed_days.append((day_date, session_candles, range_high, range_low, atr))
            source_days = precomputed_days
        else:
            source_days = grouped_days

        for window_name, (start_str, end_str) in windows.items():
            start_date = datetime.strptime(start_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            end_date = datetime.strptime(end_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            window_days = [day for day in source_days if start_date <= day[0] <= end_date]
            preloaded[(instrument, window_name)] = window_days

    return preloaded


def _init_worker(preloaded: Dict[Tuple[str, str], List[Tuple[datetime, List[Candle]]]]):
    """Worker initializer storing pre-loaded trading days in module global."""
    global _PRELOADED_DAYS_CACHE
    _PRELOADED_DAYS_CACHE = preloaded


def run_single_backtest(args: tuple) -> Optional[dict]:
    """Run a single backtest using in-memory pre-grouped trading days."""
    if len(args) == 8:
        profile_dict, data_dir, window_name, start_str, end_str, starting_equity, tick_value, commission = args
    elif len(args) == 7:
        profile_dict, data_dir, start_str, end_str, starting_equity, tick_value, commission = args
        window_name = f"{start_str}_to_{end_str}"
    else:
        raise ValueError(f"Invalid args length: {len(args)}")

    cache_key = (profile_dict["instrument"], window_name)
    trading_days = _PRELOADED_DAYS_CACHE.get(cache_key)

    if trading_days is None:
        start_date = datetime.strptime(start_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_date = datetime.strptime(end_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        loader = CandleDataLoader(data_dir)
        candles = loader.load(profile_dict["instrument"], start_date, end_date)
        if not candles:
            return None
        trading_days = BacktestEngine.group_candles_by_day(candles)
        _PRELOADED_DAYS_CACHE[cache_key] = trading_days

    if not trading_days:
        return None

    dims = profile_dict.get("dimensions", profile_dict)
    engine_val = profile_dict.get("engine", dims.get("engine"))
    risk_val = dims.get("risk_model")
    entry_val = dims.get("entry_mode")
    pyramid_val = dims.get("pyramid_model")
    exit_val = dims.get("exit_model")
    filters_val = dims.get("filters", [])
    instrument_val = profile_dict.get("instrument", "US100.cash")

    profile = BacktestProfile(
        engine=EngineType(engine_val),
        risk_model=RiskModel(risk_val),
        entry_mode=entry_val,
        pyramid_model=PyramidModel(pyramid_val),
        exit_model=ExitModel(exit_val),
        filters=filters_val,
        instrument=instrument_val,
    )

    engine = BacktestEngine(
        profile=profile,
        starting_equity=starting_equity,
        tick_value=tick_value,
        commission_per_lot=commission,
        trading_days=trading_days,
    )

    try:
        metrics = engine.run()
        result = asdict(metrics)
        result["window"] = window_name
        result["window_range"] = f"{start_str}_to_{end_str}"
        result["tournament_score"] = metrics.tournament_score()
        return result
    except Exception as e:
        return {"profile_id": profile.profile_id(), "window": window_name, "error": str(e)}


def load_asset_specs(specs_path: str) -> dict:
    """Load FTMO asset specifications."""
    with open(specs_path, "r") as f:
        return json.load(f)


def get_tick_value_and_commission(specs: dict, symbol: str) -> Tuple[float, float]:
    """Extract tick value and commission for a symbol from asset specs."""
    for instrument in specs.get("instruments", []):
        if instrument["symbol"] == symbol:
            return float(instrument.get("tick_value", 1.0)), float(instrument.get("commission_per_lot", 0.0))
    return 1.0, 0.0


def evaluate_multi_window_profiles(
    results: List[dict],
    required_windows: Optional[List[str]] = None,
    max_drawdown_ceiling: float = 0.08,
) -> List[dict]:
    """Aggregate per-window results and filter profiles meeting acceptance criteria.

    Acceptance criteria:
    - Positive Sharpe ratio across all evaluated windows.
    - Max drawdown strictly below max_drawdown_ceiling (8.0%).
    """
    if required_windows is None:
        required_windows = ["6m", "1y", "2.5y"]

    by_profile: Dict[str, Dict[str, dict]] = {}
    for r in results:
        pid = r.get("profile_id")
        win = r.get("window")
        if not pid or not win or "error" in r:
            continue
        if pid not in by_profile:
            by_profile[pid] = {}
        by_profile[pid][win] = r

    qualified_profiles = []
    for pid, win_dict in by_profile.items():
        if not all(w in win_dict for w in required_windows):
            continue

        all_positive_sharpe = all(win_dict[w].get("sharpe_ratio", 0.0) > 0.0 for w in required_windows)
        all_safe_drawdown = all(win_dict[w].get("max_drawdown_pct", 1.0) < max_drawdown_ceiling for w in required_windows)

        if all_positive_sharpe and all_safe_drawdown:
            scores = [win_dict[w].get("tournament_score", 0.0) for w in required_windows]
            composite_score = sum(scores) / len(scores)

            profile_summary = {
                "profile_id": pid,
                "composite_score": composite_score,
                "windows": win_dict,
                "metrics_2_5y": win_dict.get("2.5y", {}),
                "metrics_1y": win_dict.get("1y", {}),
                "metrics_6m": win_dict.get("6m", {}),
            }
            qualified_profiles.append(profile_summary)

    qualified_profiles.sort(key=lambda p: (p["composite_score"], p["profile_id"]), reverse=True)
    return qualified_profiles


def export_top_profiles(
    qualified_profiles: List[dict],
    engine_type: str,
    export_dir: str,
    top_n: int = 10,
) -> List[Path]:
    """Export the top N qualified profiles as standardized JSON files."""
    target_path = Path(export_dir)
    target_path.mkdir(parents=True, exist_ok=True)
    for old_file in target_path.glob("*.json"):
        old_file.unlink()

    exported_paths = []
    top_selection = qualified_profiles[:top_n]

    for rank, summary in enumerate(top_selection, start=1):
        pid = summary["profile_id"]
        parts = pid.split("|")
        engine_str = parts[0]
        risk_str = parts[1]
        entry_str = parts[2]
        pyramid_str = parts[3]
        exit_str = parts[4]
        filter_str = parts[5]
        instrument_str = parts[6] if len(parts) > 6 else "US100.cash"

        filters_list = [] if filter_str == "none" else filter_str.split("+")

        profile_doc = {
            "profile_id": pid,
            "engine": engine_str,
            "instrument": instrument_str,
            "version": "1.0.0",
            "dimensions": {
                "risk_model": risk_str,
                "entry_mode": entry_str,
                "pyramid_model": pyramid_str,
                "exit_model": exit_str,
                "filters": filters_list,
            },
            "parameters": {
                "sl_pts": 40.0,
                "tp_pts": 20.0,
                "buffer_pts": 0.0,
                "trail_trigger_pts": 15.0,
                "trail_dist_pts": 15.0,
                "max_spread_pts": 3.0,
                "max_tranches": 1 if pyramid_str == "no_pyramid" else 3,
                "cooldown_seconds": 60.0,
                "base_lot_size": 5.0,
            },
            "risk_bounds": {
                "max_risk_pct": 0.0075,
                "max_daily_loss_pct": 0.045,
                "account_floor": 90000.0,
                "max_lot_size": 15.0,
            },
        }

        clean_slug = f"rank_{rank:02d}_{risk_str}_{entry_str}_{exit_str}_{pyramid_str}"
        file_path = target_path / f"{clean_slug}.json"

        with open(file_path, "w") as f:
            json.dump(profile_doc, f, indent=2)

        exported_paths.append(file_path)

    return exported_paths


def run_tournament(
    engine_type: str,
    instruments: List[str],
    data_dir: str,
    output_dir: str,
    specs_path: str,
    starting_equity: float = 100000.0,
    max_workers: int = 8,
    windows: Optional[List[str]] = None,
    prescreen: bool = True,
    export_top_10: bool = True,
    top_10_dir: Optional[str] = None,
) -> List[dict]:
    """Run the optimized tournament across profiles, instruments, and time windows."""
    specs = load_asset_specs(specs_path)
    active_windows = windows or list(TIME_WINDOWS.keys())
    selected_windows = {w: TIME_WINDOWS[w] for w in active_windows}

    if engine_type == "london":
        raw_profiles = generate_london_profiles(instruments)
    elif engine_type == "omni":
        raw_profiles = generate_omni_profiles(instruments)
    else:
        raise ValueError(f"Unknown engine type: {engine_type}")

    total_raw = len(raw_profiles)

    if prescreen:
        profiles = prescreen_profiles(raw_profiles, starting_equity=starting_equity)
        print(f"Pre-screening {engine_type}: kept {len(profiles)} / {total_raw} valid profiles ({total_raw - len(profiles)} rejected)")
    else:
        profiles = raw_profiles
        print(f"Generated {len(profiles)} raw profiles for {engine_type} (prescreen disabled)")

    print(f"Pre-loading candle data for instruments: {instruments} across windows: {active_windows}")
    t_load = time.time()
    preloaded = preload_trading_days(data_dir, instruments, selected_windows, engine_type=engine_type)
    print(f"Pre-loaded {len(preloaded)} (symbol, window) datasets in {time.time() - t_load:.2f}s")

    tasks = []
    for profile in profiles:
        tick_value, commission = get_tick_value_and_commission(specs, profile.instrument)
        for window_name in active_windows:
            start_str, end_str = TIME_WINDOWS[window_name]
            profile_dict = {
                "engine": profile.engine.value,
                "risk_model": profile.risk_model.value,
                "entry_mode": profile.entry_mode,
                "pyramid_model": profile.pyramid_model.value,
                "exit_model": profile.exit_model.value,
                "filters": profile.filters,
                "instrument": profile.instrument,
            }
            tasks.append((
                profile_dict,
                data_dir,
                window_name,
                start_str,
                end_str,
                starting_equity,
                tick_value,
                commission,
            ))

    print(f"Dispatched {len(tasks)} backtesting tasks across {max_workers} worker processes")
    results = []
    errors = 0
    start_time = time.time()

    with ProcessPoolExecutor(max_workers=max_workers, initializer=_init_worker, initargs=(preloaded,)) as executor:
        futures = {executor.submit(run_single_backtest, task): i for i, task in enumerate(tasks)}

        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            if result is None:
                errors += 1
            elif "error" in result:
                errors += 1
            else:
                results.append(result)

            if (i + 1) % 500 == 0 or (i + 1) == len(tasks):
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                print(f"  Progress: {i + 1}/{len(tasks)} ({rate:.1f} tasks/sec) | Results: {len(results)} | Errors: {errors}", flush=True)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    results.sort(key=lambda r: (r.get("tournament_score", 0), r.get("profile_id", "")), reverse=True)

    results_csv = output_path / f"{engine_type}_tournament_results.csv"
    if results:
        fieldnames = list(results[0].keys())
        with open(results_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"Results written to {results_csv}")

    results_json = output_path / f"{engine_type}_tournament_results.json"
    with open(results_json, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"JSON results written to {results_json}")

    qualified = evaluate_multi_window_profiles(
        results,
        required_windows=active_windows,
        max_drawdown_ceiling=0.08,
    )
    print(f"Profiles qualifying with Sharpe > 0 and Max DD < 8% across all windows: {len(qualified)}")

    ranked_csv = output_path / f"{engine_type}_multi_window_ranked.csv"
    if qualified:
        ranked_rows = []
        for q in qualified:
            row = {
                "profile_id": q["profile_id"],
                "composite_score": q["composite_score"],
            }
            for w in active_windows:
                w_m = q["windows"].get(w, {})
                row[f"{w}_sharpe"] = w_m.get("sharpe_ratio", 0.0)
                row[f"{w}_mdd_pct"] = w_m.get("max_drawdown_pct", 0.0)
                row[f"{w}_trades"] = w_m.get("total_trades", 0)
                row[f"{w}_pnl"] = w_m.get("total_pnl", 0.0)
            ranked_rows.append(row)

        with open(ranked_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(ranked_rows[0].keys()))
            writer.writeheader()
            writer.writerows(ranked_rows)

    top_json = output_path / f"{engine_type}_top_10.json"
    with open(top_json, "w") as f:
        json.dump(qualified[:10], f, indent=2, default=str)

    if export_top_10 and qualified:
        dest_dir = top_10_dir or f"profiles/{'london_reversal' if engine_type == 'london' else 'omni_breakout'}/top_10"
        exported = export_top_profiles(qualified, engine_type, dest_dir, top_n=10)
        print(f"Exported top {len(exported)} profiles to {dest_dir}")

    top_10 = results[:10]
    print(f"\n{'='*80}")
    print(f"TOP 10 INDIVIDUAL WINDOW RUNS ({engine_type.upper()})")
    print(f"{'='*80}")
    for i, r in enumerate(top_10):
        print(f"#{i+1} | Score: {r.get('tournament_score', 0):.4f} | Window: {r.get('window', 'N/A')}")
        print(f"  Profile: {r.get('profile_id')}")
        print(f"  Trades: {r.get('total_trades', 0)} | Win Rate: {r.get('win_rate', 0):.1%}")
        print(f"  PnL: ${r.get('total_pnl', 0):,.2f} | Sharpe: {r.get('sharpe_ratio', 0):.2f}")
        print(f"  Max DD: {r.get('max_drawdown_pct', 0):.2%} | PF: {r.get('profit_factor', 0):.2f}")

    return results


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Odin FTMO v2 Tournament Runner")
    parser.add_argument("engine", choices=["london", "omni", "both"], help="Engine type to backtest")
    parser.add_argument("--instruments", nargs="+", default=["US100.cash"], help="Instruments to test")
    parser.add_argument("--data-dir", default="data/raw", help="Path to candle data")
    parser.add_argument("--output-dir", default="backtester/results", help="Path for results output")
    parser.add_argument("--specs", default="data/ftmo_asset_specs.json", help="FTMO asset specs JSON")
    parser.add_argument("--equity", type=float, default=100000.0, help="Starting equity")
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers")
    parser.add_argument("--windows", nargs="+", choices=["6m", "1y", "2.5y"], default=None, help="Time windows")
    parser.add_argument("--no-prescreen", action="store_true", help="Disable formal pre-screening")

    args = parser.parse_args()

    if args.engine in ("london", "both"):
        run_tournament(
            engine_type="london",
            instruments=args.instruments,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            specs_path=args.specs,
            starting_equity=args.equity,
            max_workers=args.workers,
            windows=args.windows,
            prescreen=not args.no_prescreen,
        )

    if args.engine in ("omni", "both"):
        run_tournament(
            engine_type="omni",
            instruments=args.instruments,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            specs_path=args.specs,
            starting_equity=args.equity,
            max_workers=args.workers,
            windows=args.windows,
            prescreen=not args.no_prescreen,
        )


if __name__ == "__main__":
    main()
