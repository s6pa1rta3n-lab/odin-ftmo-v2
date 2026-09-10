"""Unified high-performance data download manager for FTMO Odin v2."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import subprocess
import sys
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fetch_all_data")

DUKASCOPY_MAP = {
    "EURUSD": "eurusd",
    "GBPUSD": "gbpusd",
    "USDJPY": "usdjpy",
    "AUDUSD": "audusd",
    "USDCAD": "usdcad",
    "USDCHF": "usdchf",
    "NZDUSD": "nzdusd",
    "EURGBP": "eurgbp",
    "EURJPY": "eurjpy",
    "GBPJPY": "gbpjpy",
    "XAUUSD": "xauusd",
    "XAGUSD": "xagusd",
    "US100.cash": "usatechidxusd",
    "US30.cash": "usa30idxusd",
    "US500.cash": "usa500idxusd",
    "GER40.cash": "deuidxeur",
    "UK100.cash": "gbridxgbp",
    "JPN225.cash": "jpnidxjpy",
    "FRA40.cash": "fraidxeur",
    "AUS200.cash": "ausidxaud",
    "EU50.cash": "eusidxeur",
    "BTCUSD": "btcusd",
    "ETHUSD": "ethusd",
}


def download_dukascopy_instrument(
    symbol: str,
    instrument_id: str,
    from_date: str,
    to_date: str,
    output_dir: Path
) -> bool:
    """Download 1-minute OHLCV data using dukascopy-node CLI."""
    target_filename = f"{symbol}_m1_20240101_20260909.csv"
    final_path = output_dir / target_filename
    alt_filename = f"{symbol}_m1_2024-01-01_2026-09-09.csv"
    alt_path = output_dir / alt_filename

    if final_path.exists() and final_path.stat().st_size > 100000:
        logger.info(f"{symbol} already downloaded at {final_path} ({final_path.stat().st_size} bytes)")
        return True

    temp_dir = output_dir / "_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_name = f"{symbol}_temp"

    cmd = [
        "npx", "dukascopy-node",
        "-i", instrument_id,
        "-from", from_date,
        "-to", to_date,
        "-t", "m1",
        "-v",
        "-f", "csv",
        "-dir", str(temp_dir),
        "-fn", temp_name,
    ]

    logger.info(f"Downloading {symbol} ({instrument_id}) from {from_date} to {to_date}...")
    proc = subprocess.run(cmd, capture_output=True, text=True)

    generated_file = temp_dir / f"{temp_name}.csv"
    if not generated_file.exists():
        candidates = list(temp_dir.glob(f"{temp_name}*"))
        if candidates:
            generated_file = candidates[0]

    if generated_file.exists() and generated_file.stat().st_size > 1000:
        generated_file.replace(final_path)
        if "." in symbol or "BTC" in symbol or "ETH" in symbol:
            import shutil
            shutil.copyfile(final_path, alt_path)
        logger.info(f"Successfully saved {symbol} to {final_path} ({final_path.stat().st_size} bytes)")
        return True
    else:
        logger.error(f"Download failed for {symbol}: {proc.stderr or proc.stdout}")
        return False


def run_batch_downloads(symbols: List[str], max_workers: int = 4) -> Dict[str, bool]:
    """Execute batch downloads for specified instruments."""
    from_date = "2024-01-01"
    to_date = "2026-09-09"
    output_dir = Path(__file__).resolve().parents[1] / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_symbol = {
            executor.submit(
                download_dukascopy_instrument,
                sym,
                DUKASCOPY_MAP[sym],
                from_date,
                to_date,
                output_dir
            ): sym
            for sym in symbols
            if sym in DUKASCOPY_MAP
        }

        for future in future_to_symbol:
            sym = future_to_symbol[future]
            try:
                success = future.result()
                results[sym] = success
            except Exception as e:
                logger.error(f"Error downloading {sym}: {e}")
                results[sym] = False

    return results


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Batch data downloader for FTMO target instruments.")
    parser.add_argument("--symbols", nargs="*", default=None, help="Specific symbols to download")
    parser.add_argument("--workers", type=int, default=4, help="Parallel download concurrency")
    args = parser.parse_args()

    target_symbols = args.symbols or list(DUKASCOPY_MAP.keys())
    logger.info(f"Starting batch download for {len(target_symbols)} instruments...")
    results = run_batch_downloads(target_symbols, max_workers=args.workers)

    success_count = sum(1 for v in results.values() if v)
    logger.info(f"Completed downloads: {success_count}/{len(target_symbols)} successful")
    sys.exit(0 if success_count == len(target_symbols) else 1)


if __name__ == "__main__":
    main()
