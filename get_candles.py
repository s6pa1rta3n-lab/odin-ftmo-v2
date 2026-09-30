import requests
import json
import pandas as pd

with open('/home/solveetcoagula/odin_ftmo/config_us100.json', 'r') as f:
    config = json.load(f)
token = config['metaapi']['token']
account_id = "37bc945f-49b4-4ae4-954d-30a8f6675fbc"

def get_ftmo_data(symbol, timeframe, limit=500):
    url = f"https://mt-market-data-client-api-v1.backup-new-york.agiliumtrade.ai/users/current/accounts/{account_id}/historical-market-data/symbols/{symbol}/timeframes/{timeframe}/candles?limit={limit}"
    headers = {"auth-token": token}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data = r.json()
        df = pd.DataFrame(data)
        if not df.empty:
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
            if df.index.tz is not None: df.index = df.index.tz_convert(None)
            return df
    return pd.DataFrame()

df_us100_1m = get_ftmo_data('US100.cash', '1m', 1000)
df_us100_1h = get_ftmo_data('US100.cash', '1h', 50)
df_us100_1m = df_us100_1m[df_us100_1m.index >= pd.to_datetime('2026-09-22 21:00:00')]

def compute_atr_14(df_1h, until_time):
    # Slice up to `until_time` (exclusive)
    df_sliced = df_1h[df_1h.index < until_time].copy()
    if len(df_sliced) < 15:
        return 76.91 # Fallback
    trs = []
    for i in range(1, len(df_sliced)):
        h = df_sliced.iloc[i]['high']
        l = df_sliced.iloc[i]['low']
        pc = df_sliced.iloc[i-1]['close']
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    recent = trs[-14:]
    return sum(recent) / 14.0

position = None
highest_pnl = 0
entry_price = 0
sl = 0
sizing = 6.20
lot_multiplier = 20
direction = None

for idx, row in df_us100_1m.iterrows():
    if position is None:
        if row['high'] > 30733.64:
            position = 'LONG'
            direction = 'LONG'
            entry_price = 30733.64
            sl = 30733.64 - 1.5 * 76.91
            print(f"[{idx}] TRIGGERED LONG at {entry_price:.2f}. Initial SL: {sl:.2f}")
        elif row['low'] < 30693.74:
            position = 'SHORT'
            direction = 'SHORT'
            entry_price = 30693.74
            sl = 30693.74 + 1.5 * 76.91
            print(f"[{idx}] TRIGGERED SHORT at {entry_price:.2f}. Initial SL: {sl:.2f}")
    else:
        # Check trailing stop update (on the hour)
        if idx.minute == 0 and idx.second == 0:
            # Re-calculate ATR at this top of the hour using 1h data
            current_atr = compute_atr_14(df_us100_1h, idx)
            # The close price of the previous hour is used
            bar_close = df_us100_1h[df_us100_1h.index < idx].iloc[-1]['close']
            dist = 1.5 * current_atr
            if direction == 'LONG':
                cand_sl = bar_close - dist
                if cand_sl > sl:
                    print(f"[{idx}] RATCHETED SL UP from {sl:.2f} to {cand_sl:.2f}")
                    sl = cand_sl
            else:
                cand_sl = bar_close + dist
                if cand_sl < sl:
                    print(f"[{idx}] RATCHETED SL DOWN from {sl:.2f} to {cand_sl:.2f}")
                    sl = cand_sl
                    
        if position == 'LONG':
            if row['low'] < sl:
                print(f"[{idx}] STOP LOSS HIT at {sl:.2f}")
                position = None
                break
            curr = (row['close'] - entry_price) * sizing * lot_multiplier
            if curr > highest_pnl: highest_pnl = curr
        else:
            if row['high'] > sl:
                print(f"[{idx}] STOP LOSS HIT at {sl:.2f}")
                position = None
                break
            curr = (entry_price - row['close']) * sizing * lot_multiplier
            if curr > highest_pnl: highest_pnl = curr

if position:
    last = df_us100_1m.iloc[-1]
    if position == 'LONG':
        curr = (last['close'] - entry_price) * sizing * lot_multiplier
    else:
        curr = (entry_price - last['close']) * sizing * lot_multiplier
    print(f"[CURRENT] FLOATING {position}. PNL: ${curr:.2f}, Peak: ${highest_pnl:.2f}")
else:
    print("Flat.")

