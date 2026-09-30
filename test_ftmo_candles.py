import requests
import json
import pandas as pd

ACCOUNT_ID = "37bc945f-49b4-4ae4-954d-30a8f6675fbc"

def get_ftmo_data(symbol, start_time):
    url = f"https://mt-market-data-client-api-v1.backup-new-york.agiliumtrade.ai/users/current/accounts/{ACCOUNT_ID}/historical-market-data/symbols/{symbol}/timeframes/1m/candles?startTime={start_time}&limit=1000"
    headers = {
        "auth-token": "eF6BssVrdvHDEk8Hk86sKkG2SjA1aU5R"
    }
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data = r.json()
        df = pd.DataFrame(data)
        if not df.empty:
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
            return df
    return pd.DataFrame()

# US100 Setup at 21:00 UTC (from 20:00 bar)
df_us100 = get_ftmo_data('US100.cash', '2026-09-22T21:00:00Z')
print("US100 Last 5 candles:")
print(df_us100.tail())

# BTCUSD Setup at 22:00 UTC (from 21:00 bar)
df_btc = get_ftmo_data('BTCUSD', '2026-09-22T22:00:00Z')
print("\nBTCUSD Last 5 candles:")
print(df_btc.tail())

def simulate(df, symbol, high, low, atr, sizing, lot_multiplier=1):
    sl_dist = 1.5 * atr
    position = None
    entry_price = 0
    sl = 0
    highest_pnl = 0
    for idx, row in df.iterrows():
        if position is None:
            if row['high'] > high:
                position = 'LONG'
                entry_price = high
                sl = entry_price - sl_dist
                print(f"[{idx}] TRIGGERED LONG at {entry_price:.2f}. Initial SL: {sl:.2f}")
            elif row['low'] < low:
                position = 'SHORT'
                entry_price = low
                sl = entry_price + sl_dist
                print(f"[{idx}] TRIGGERED SHORT at {entry_price:.2f}. Initial SL: {sl:.2f}")
        else:
            if position == 'LONG':
                if row['low'] < sl:
                    exit_price = sl
                    pnl = (exit_price - entry_price) * sizing * lot_multiplier
                    print(f"[{idx}] STOP LOSS HIT at {exit_price:.2f}. PNL: ${pnl:.2f}")
                    return
                curr_pnl = (row['close'] - entry_price) * sizing * lot_multiplier
                if curr_pnl > highest_pnl: highest_pnl = curr_pnl
            else:
                if row['high'] > sl:
                    exit_price = sl
                    pnl = (entry_price - exit_price) * sizing * lot_multiplier
                    print(f"[{idx}] STOP LOSS HIT at {exit_price:.2f}. PNL: ${pnl:.2f}")
                    return
                curr_pnl = (entry_price - row['close']) * sizing * lot_multiplier
                if curr_pnl > highest_pnl: highest_pnl = curr_pnl
                
    if position:
        last = df.iloc[-1]
        if position == 'LONG':
            floating = (last['close'] - entry_price) * sizing * lot_multiplier
        else:
            floating = (entry_price - last['close']) * sizing * lot_multiplier
        print(f"[CURRENT] FLOATING {position} at {last['close']:.2f}. Floating PNL: ${floating:.2f}. Peak: ${highest_pnl:.2f}")
    else:
        print("Never triggered.")

print("\n--- SIMULATION (FTMO PRICING) ---")
# US100 multiplier = 20
simulate(df_us100, 'US100.cash', 30733.64, 30693.74, 76.91, 6.20, 20)

# BTCUSD multiplier = 1
simulate(df_btc, 'BTCUSD', 86289.00, 86129.52, 544.67, 1.08, 1)

