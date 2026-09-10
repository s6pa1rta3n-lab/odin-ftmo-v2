import os
import json
import csv
import time
import asyncio
import aiohttp
from datetime import datetime, timedelta
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SYMBOLS = [
    "US100.cash", "US30.cash", "US500.cash", "GER40.cash", "UK100.cash", 
    "JPN225.cash", "FRA40.cash", "AUS200.cash", "EU50.cash", "BTCUSD", "ETHUSD"
]

START_DATE_STR = "2024-01-01T00:00:00Z"
END_DATE_STR = "2026-09-09T00:00:00Z"
DATA_DIR = Path(__file__).resolve().parents[1] / "raw"

def get_metaapi_credentials():
    """Retrieve MetaApi token and account ID from environment or config files."""
    token = os.getenv("METAAPI_TOKEN")
    account_id = os.getenv("METAAPI_ACCOUNT_ID")
    
    if not token or not account_id:
        search_paths = [
            Path("config_us100.json"),
            Path(__file__).resolve().parents[2] / "config_us100.json",
            Path("/Users/solveetcoagula/Desktop/google_cloud/config_us100.json"),
            Path("/home/solveetcoagula/odin_ftmo/config_us100.json"),
        ]
        for config_path in search_paths:
            if config_path.exists():
                try:
                    with open(config_path, "r") as f:
                        conf = json.load(f)
                        token = token or conf.get("metaapi", {}).get("token")
                        account_id = account_id or conf.get("metaapi", {}).get("account_id")
                        if token and account_id:
                            break
                except Exception as e:
                    logger.warning(f"Failed to read config at {config_path}: {e}")
                
    if not token or not account_id:
        logger.error("METAAPI_TOKEN and METAAPI_ACCOUNT_ID must be set in environment variables or config.")
        
    return token, account_id

def parse_time(t_str):
    if t_str.endswith('Z'):
        t_str = t_str[:-1] + '+00:00'
    return datetime.fromisoformat(t_str)

async def fetch_candles(session, account_id, token, symbol, start_time, limit=1000):
    """Fetch candles from MetaApi using the SDK with broker symbol mapping."""
    broker_symbol = "JP225.cash" if symbol == "JPN225.cash" else symbol
    try:
        from metaapi_cloud_sdk import MetaApi
        api = MetaApi(token)
        account = await api.metatrader_account_api.get_account(account_id)
        raw_candles = await account.get_historical_candles(broker_symbol, "1m", start_time, limit)
        api.close()
        
        result = []
        for c in raw_candles:
            t = c["time"]
            if isinstance(t, datetime):
                time_str = t.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            else:
                time_str = str(t)
            result.append({
                "time": time_str,
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "volume": float(c.get("tickVolume", c.get("volume", 0)))
            })
        return result
    except Exception as e:
        logger.error(f"Error fetching data for {symbol} at {start_time}: {e}")
        return []

def get_last_timestamp(filepath):
    if not filepath.exists():
        return None
        
    try:
        with open(filepath, 'r') as f:
            f.seek(0, os.SEEK_END)
            position = f.tell()
            line = ''
            while position >= 0:
                f.seek(position)
                next_char = f.read(1)
                if next_char == '\n' and line:
                    break
                line = next_char + line
                position -= 1
            if line:
                reader = csv.reader([line])
                row = next(reader)
                if row and row[0] != 'timestamp':
                    return parse_time(row[0])
    except Exception as e:
        logger.warning(f"Could not read last timestamp from {filepath}: {e}")
    return None

async def download_symbol(session, account_id, token, symbol):
    end_date = parse_time(END_DATE_STR)
    
    filename = f"{symbol}_m1_{START_DATE_STR[:10]}_{END_DATE_STR[:10]}.csv"
    filepath = DATA_DIR / filename
    
    current_start = parse_time(START_DATE_STR)
    
    file_mode = 'a'
    write_header = not filepath.exists()
    
    last_ts = get_last_timestamp(filepath)
    if last_ts:
        current_start = last_ts + timedelta(minutes=1)
        logger.info(f"Resuming {symbol} from {current_start}")
        if current_start >= end_date:
            logger.info(f"{symbol} is already up to date.")
            return

    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    total_candles = 0
    with open(filepath, file_mode, newline='') as csvfile:
        writer = csv.writer(csvfile)
        if write_header:
            writer.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
        while current_start < end_date:
            candles = await fetch_candles(session, account_id, token, symbol, current_start)
            if candles is None:
                break
                
            if not candles:
                logger.debug(f"No candles returned for {symbol} at {current_start}. Advancing time.")
                current_start += timedelta(hours=12)
                continue
                
            rows = []
            last_candle_time = current_start
            for c in candles:
                t = parse_time(c['time'])
                if t >= end_date:
                    continue
                rows.append([
                    c['time'],
                    c['open'],
                    c['high'],
                    c['low'],
                    c['close'],
                    c.get('tickVolume', c.get('volume', 0))
                ])
                last_candle_time = t
                
            if rows:
                writer.writerows(rows)
                total_candles += len(rows)
                
            logger.info(f"[{symbol}] Progress: {last_candle_time.strftime('%Y-%m-%d %H:%M')} | Downloaded: {total_candles}")
            
            next_start = last_candle_time + timedelta(minutes=1)
            if next_start <= current_start:
                current_start += timedelta(minutes=1000)
            else:
                current_start = next_start
                
            await asyncio.sleep(0.1)
            
    logger.info(f"Finished downloading {symbol}. Total new candles: {total_candles}")
    validate_data(filepath, symbol)

def validate_data(filepath, symbol):
    if not filepath.exists():
        return
        
    logger.info(f"Validating data for {symbol}...")
    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        
        last_time = None
        gaps = 0
        duplicates = 0
        
        valid_rows = []
        seen_times = set()
        
        for row in reader:
            if not row: continue
            try:
                t_str = row[0]
                if t_str in seen_times:
                    duplicates += 1
                    continue
                seen_times.add(t_str)
                
                t = parse_time(t_str)
                if last_time:
                    diff = (t - last_time).total_seconds()
                    if diff < 0:
                        logger.warning(f"[{symbol}] Timestamp out of order: {last_time} -> {t}")
                    elif diff > 60:
                        gaps += 1
                last_time = t
                valid_rows.append(row)
            except Exception as e:
                logger.error(f"[{symbol}] Error parsing row {row}: {e}")
                
    if duplicates > 0:
        logger.warning(f"[{symbol}] Found {duplicates} duplicates. Removing them...")
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            writer.writerows(valid_rows)
            
    logger.info(f"Validation complete for {symbol}. Gaps detected (incl weekends): {gaps}. Duplicates removed: {duplicates}")

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pull 1-minute historical candles from MetaApi.")
    parser.add_argument("--symbols", nargs="*", default=None, help="Symbols to download")
    args = parser.parse_args()

    token, account_id = get_metaapi_credentials()
    if not token or not account_id:
        logger.error("Missing MetaApi credentials. Exiting.")
        return
        
    target_symbols = args.symbols or SYMBOLS
    async with aiohttp.ClientSession() as session:
        tasks = []
        for symbol in target_symbols:
            tasks.append(download_symbol(session, account_id, token, symbol))
            
        await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
