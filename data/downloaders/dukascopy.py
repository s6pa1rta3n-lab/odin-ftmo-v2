import asyncio
import aiohttp
import lzma
import struct
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path
import logging
from tqdm.asyncio import tqdm_asyncio
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

POINT_VALUES = {
    'EURUSD': 100000, 'GBPUSD': 100000, 'USDJPY': 1000, 'AUDUSD': 100000,
    'USDCAD': 100000, 'USDCHF': 100000, 'NZDUSD': 100000, 'EURGBP': 100000,
    'EURJPY': 1000, 'GBPJPY': 1000, 'XAUUSD': 1000, 'XAGUSD': 100000
}

URL_PATTERN = "https://datafeed.dukascopy.com/datafeed/{symbol}/{year}/{month}/{day}/{hour}h_ticks.bi5"

async def fetch_hour(session: aiohttp.ClientSession, symbol: str, dt: datetime, retries: int = 3) -> tuple:
    """
    Fetches the tick data for a given symbol and hour.
    """
    url = URL_PATTERN.format(
        symbol=symbol,
        year=dt.year,
        month=f"{dt.month - 1:02d}",
        day=f"{dt.day:02d}",
        hour=f"{dt.hour:02d}"
    )
    
    for attempt in range(retries):
        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    content = await response.read()
                    return dt, content
                elif response.status == 404:
                    return dt, None
                else:
                    await asyncio.sleep(2 ** attempt)
        except Exception as e:
            await asyncio.sleep(2 ** attempt)
    return dt, None

def parse_bi5(content: bytes, dt: datetime, point_value: int) -> pd.DataFrame:
    """
    Parses bi5 lzma compressed tick data into a pandas DataFrame.
    """
    try:
        decompressed = lzma.decompress(content)
    except Exception:
        return pd.DataFrame()
    
    ticks = []
    tick_struct = struct.Struct('>IIIf f')
    struct_size = tick_struct.size
    
    for i in range(0, len(decompressed), struct_size):
        chunk = decompressed[i:i+struct_size]
        if len(chunk) < struct_size:
            break
            
        ms, ask, bid, ask_vol, bid_vol = tick_struct.unpack(chunk)
        timestamp = dt + timedelta(milliseconds=ms)
        price = bid / point_value
        volume = bid_vol
        ticks.append((timestamp, price, volume))
        
    if not ticks:
        return pd.DataFrame()
        
    df = pd.DataFrame(ticks, columns=['timestamp', 'price', 'volume'])
    df.set_index('timestamp', inplace=True)
    return df

def aggregate_to_ohlcv(df_ticks: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates tick data into 1-minute OHLCV bars.
    """
    if df_ticks.empty:
        return pd.DataFrame()
        
    ohlcv = df_ticks.resample('1min').agg({
        'price': ['first', 'max', 'min', 'last'],
        'volume': 'sum'
    })
    
    ohlcv.columns = ['open', 'high', 'low', 'close', 'volume']
    ohlcv.dropna(inplace=True)
    return ohlcv

async def download_symbol(symbol: str, start_dt: datetime, end_dt: datetime, output_dir: Path):
    """
    Downloads and processes data for a single symbol over a date range.
    """
    start_str = start_dt.strftime('%Y%m%d')
    end_str = end_dt.strftime('%Y%m%d')
    output_path = output_dir / f"{symbol}_m1_{start_str}_{end_str}.csv"
    
    if output_path.exists():
        logging.info(f"File {output_path} already exists, skipping {symbol}")
        return
        
    point_value = POINT_VALUES.get(symbol, 100000)
    current_dt = start_dt
    hours_to_fetch = []
    
    while current_dt <= end_dt:
        if current_dt.weekday() < 5:
            hours_to_fetch.append(current_dt)
        current_dt += timedelta(hours=1)
        
    connector = aiohttp.TCPConnector(limit=20)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_hour(session, symbol, dt) for dt in hours_to_fetch]
        results = await tqdm_asyncio.gather(*tasks, desc=f"Downloading {symbol}")
        
    dfs = []
    for dt, content in results:
        if content:
            df_ticks = parse_bi5(content, dt, point_value)
            if not df_ticks.empty:
                df_ohlcv = aggregate_to_ohlcv(df_ticks)
                if not df_ohlcv.empty:
                    dfs.append(df_ohlcv)
                    
    if not dfs:
        logging.warning(f"No data found for {symbol}")
        return
        
    final_df = pd.concat(dfs)
    final_df.sort_index(inplace=True)
    final_df = final_df[~final_df.index.duplicated(keep='first')]
    
    final_df.to_csv(output_path)
    logging.info(f"Saved {len(final_df)} rows for {symbol} to {output_path}")

async def main():
    """
    Main entry point.
    """
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'USDCHF', 'NZDUSD', 'EURGBP', 'EURJPY', 'GBPJPY', 'XAUUSD', 'XAGUSD']
    start_dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime(2026, 9, 9, tzinfo=timezone.utc)
    output_dir = Path(__file__).resolve().parents[1] / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for symbol in symbols:
        await download_symbol(symbol, start_dt, end_dt, output_dir)

if __name__ == '__main__':
    asyncio.run(main())
