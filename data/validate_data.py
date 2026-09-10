"""Data validation module for 1-minute OHLCV market data."""

import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backtester"))
from engine import CandleDataLoader, Candle


def parse_timestamp_flexible(ts_str: str) -> datetime:
    """Parse various timestamp formats into UTC datetime."""
    ts_str = ts_str.strip()
    if ts_str.isdigit():
        epoch = float(ts_str)
        if epoch > 1e12:
            epoch = epoch / 1000.0
        return datetime.fromtimestamp(epoch, tz=timezone.utc)

    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y.%m.%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(ts_str, fmt)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue

    try:
        epoch = float(ts_str)
        if epoch > 1e12:
            epoch = epoch / 1000.0
        return datetime.fromtimestamp(epoch, tz=timezone.utc)
    except ValueError:
        raise ValueError(f"Cannot parse timestamp: {ts_str}")


def is_weekend_gap(prev_ts: datetime, curr_ts: datetime) -> bool:
    """Determine whether the time gap is an expected weekend closure."""
    prev_weekday = prev_ts.weekday()
    curr_weekday = curr_ts.weekday()
    time_diff_hours = (curr_ts - prev_ts).total_seconds() / 3600.0

    if prev_weekday == 4 and curr_weekday in (6, 0) and time_diff_hours <= 72.0:
        return True
    if prev_weekday == 5 and curr_weekday in (6, 0) and time_diff_hours <= 48.0:
        return True
    if curr_ts.date() == prev_ts.date() and time_diff_hours <= 1.5:
        return False
    return False


def validate_csv_file(file_path: Path, fix: bool = True) -> Dict[str, any]:
    """Validate a single CSV file for continuity, duplicates, and OHLC integrity."""
    stats = {
        "file": file_path.name,
        "path": str(file_path),
        "total_rows": 0,
        "duplicates_found": 0,
        "duplicates_removed": 0,
        "weekend_gaps": 0,
        "unexpected_gaps": 0,
        "out_of_order": 0,
        "invalid_ohlc": 0,
        "valid": True,
        "start_time": None,
        "end_time": None,
    }

    if not file_path.exists() or file_path.stat().st_size == 0:
        stats["valid"] = False
        stats["error"] = "File is empty or does not exist"
        return stats

    rows_to_keep = []
    seen_timestamps = set()
    prev_ts: Optional[datetime] = None

    with open(file_path, "r", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            stats["valid"] = False
            stats["error"] = "Missing CSV header"
            return stats

        for row_idx, row in enumerate(reader, start=2):
            if not row or len(row) < 5:
                continue

            stats["total_rows"] += 1

            try:
                ts = parse_timestamp_flexible(row[0])
                open_p = float(row[1])
                high_p = float(row[2])
                low_p = float(row[3])
                close_p = float(row[4])
                volume = float(row[5]) if len(row) > 5 else 0.0
            except (ValueError, IndexError):
                stats["invalid_ohlc"] += 1
                continue

            if open_p <= 0 or high_p <= 0 or low_p <= 0 or close_p <= 0:
                stats["invalid_ohlc"] += 1
            if low_p > min(open_p, close_p) * 1.001 or high_p < max(open_p, close_p) * 0.999:
                stats["invalid_ohlc"] += 1
            if volume < 0:
                stats["invalid_ohlc"] += 1

            ts_key = row[0]
            if ts_key in seen_timestamps:
                stats["duplicates_found"] += 1
                continue

            seen_timestamps.add(ts_key)

            if prev_ts is not None:
                delta_sec = (ts - prev_ts).total_seconds()
                if delta_sec < 0:
                    stats["out_of_order"] += 1
                elif delta_sec > 60:
                    if is_weekend_gap(prev_ts, ts):
                        stats["weekend_gaps"] += 1
                    else:
                        stats["unexpected_gaps"] += 1

            prev_ts = ts
            if stats["start_time"] is None:
                stats["start_time"] = ts
            stats["end_time"] = ts

            rows_to_keep.append(row)

    if fix and stats["duplicates_found"] > 0:
        rows_to_keep.sort(key=lambda r: parse_timestamp_flexible(r[0]))
        with open(file_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows_to_keep)
        stats["duplicates_removed"] = stats["duplicates_found"]

    if stats["total_rows"] == 0 or stats["invalid_ohlc"] > 0 or stats["out_of_order"] > 0:
        stats["valid"] = False

    return stats


def verify_candle_loader(
    symbol: str,
    data_dir: Path,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, any]:
    """Verify CandleDataLoader can ingest and sort candles for a symbol."""
    loader = CandleDataLoader(str(data_dir))
    start_dt = start_date or datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_dt = end_date or datetime(2026, 9, 9, tzinfo=timezone.utc)

    candles = loader.load(symbol, start_dt, end_dt)
    loader_stats = {
        "symbol": symbol,
        "candles_loaded": len(candles),
        "valid": len(candles) > 0,
        "first_candle": candles[0].timestamp if candles else None,
        "last_candle": candles[-1].timestamp if candles else None,
    }

    if candles:
        for i in range(1, min(len(candles), 1000)):
            if candles[i].timestamp <= candles[i - 1].timestamp:
                loader_stats["valid"] = False
                loader_stats["error"] = f"Non-monotonic timestamps at index {i}"
                break

    return loader_stats


def validate_all_raw_data(data_dir: Path, fix: bool = True) -> Tuple[List[Dict], bool]:
    """Scan and validate all CSV files in the raw data directory."""
    csv_files = sorted(data_dir.glob("*.csv"))
    results = []
    all_valid = True
    seen_canonical = set()

    for file_path in csv_files:
        resolved = file_path.resolve()
        if resolved in seen_canonical:
            continue
        seen_canonical.add(resolved)
        res = validate_csv_file(file_path, fix=fix)
        results.append(res)
        if not res["valid"]:
            all_valid = False

    return results, all_valid


def main():
    """CLI entry point for data validation."""
    parser = argparse.ArgumentParser(description="Validate 1-minute OHLCV data CSV files.")
    parser.add_argument("--dir", default="data/raw", help="Path to raw data directory")
    parser.add_argument("--file", default=None, help="Path to specific CSV file")
    parser.add_argument("--no-fix", action="store_true", help="Do not remove duplicates automatically")
    parser.add_argument("--check-symbol", default=None, help="Symbol to test with CandleDataLoader")
    args = parser.parse_args()

    fix = not args.no_fix

    if args.file:
        target_path = Path(args.file)
        res = validate_csv_file(target_path, fix=fix)
        print(f"File: {res['file']}")
        print(f"Total rows: {res['total_rows']}")
        print(f"Duplicates found: {res['duplicates_found']}")
        print(f"Weekend gaps: {res['weekend_gaps']}")
        print(f"Unexpected gaps: {res['unexpected_gaps']}")
        print(f"Invalid OHLC rows: {res['invalid_ohlc']}")
        print(f"Valid: {res['valid']}")
        if args.check_symbol:
            loader_res = verify_candle_loader(args.check_symbol, target_path.parent)
            print(f"CandleDataLoader check for '{args.check_symbol}':")
            print(f"  Candles loaded: {loader_res['candles_loaded']}")
            print(f"  Valid: {loader_res['valid']}")
            if not loader_res["valid"]:
                res["valid"] = False
        sys.exit(0 if res["valid"] else 1)

    data_dir = Path(args.dir)
    results, all_valid = validate_all_raw_data(data_dir, fix=fix)

    print(f"\n{'='*95}")
    print(f"{'FILE':<40} {'ROWS':<10} {'DUPS':<8} {'W-GAPS':<8} {'U-GAPS':<8} {'VALID':<6}")
    print(f"{'='*95}")

    for r in results:
        print(
            f"{r['file'][:38]:<40} "
            f"{r['total_rows']:<10} "
            f"{r['duplicates_found']:<8} "
            f"{r['weekend_gaps']:<8} "
            f"{r['unexpected_gaps']:<8} "
            f"{'YES' if r['valid'] else 'NO':<6}"
        )
    print(f"{'='*95}\n")

    if args.check_symbol:
        loader_res = verify_candle_loader(args.check_symbol, data_dir)
        print(f"CandleDataLoader check for '{args.check_symbol}':")
        print(f"  Candles loaded: {loader_res['candles_loaded']}")
        print(f"  Valid: {loader_res['valid']}")
        if not loader_res["valid"]:
            all_valid = False

    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
