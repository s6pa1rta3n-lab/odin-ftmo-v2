import asyncio
from datetime import datetime, timedelta, timezone
import csv
from metaapi_cloud_sdk import MetaApi
import json

async def main():
    with open('config_us100.json', 'r') as f:
        cfg = json.load(f)
    api = MetaApi(cfg['metaapi']['token'])
    
    # Use the hardcoded active account ID
    ACCOUNT_ID = "6ccd891f-8728-4e37-ad41-1e695c6008ef"
    account = await api.metatrader_account_api.get_account(ACCOUNT_ID)
    
    connection = account.get_rpc_connection()
    await connection.connect()
    await connection.wait_synchronized()
    
    symbols = ['XAUUSD', 'BTCUSD']
    end_time = datetime.now(timezone.utc)
    # Using 120 days for a robust test
    start_time = end_time - timedelta(days=120)
    
    for symbol in symbols:
        print(f"Fetching 1M data for {symbol}...")
        try:
            candles = await connection.get_historical_candles(symbol, '1m', start_time, end_time)
            print(f"Downloaded {len(candles)} candles for {symbol}.")
            
            with open(f"data/raw/{symbol}_m1_backtest.csv", "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "open", "high", "low", "close"])
                for c in candles:
                    ts = int(c['time'].timestamp() * 1000)
                    writer.writerow([ts, c['open'], c['high'], c['low'], c['close']])
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
                
    await connection.close()

asyncio.run(main())
