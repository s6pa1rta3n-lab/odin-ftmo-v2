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

df_btc_1m = get_ftmo_data('BTCUSD', '1m', 1000)
df_btc_1h = get_ftmo_data('BTCUSD', '1h', 50)
df_btc_1m = df_btc_1m[df_btc_1m.index >= pd.to_datetime('2026-09-22 22:00:00')]

def compute_atr_14(df_1h, until_time):
    df_sliced = df_1h[df_1h.index < until_time].copy()
    if len(df_sliced) < 15: return 544.67
    trs = []
    for i in range(1, len(df_sliced)):
        h = df_sliced.iloc[i]['high']
        l = df_sliced.iloc[i]['low']
        pc = df_sliced.iloc[i-1]['close']
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    return sum(trs[-14:]) / 14.0

position = None
highest_pnl = 0
entry_price = 0
sl = 0
sizing = 1.08
lot_multiplier = 1
direction = None

for idx, row in df_btc_1m.iterrows():
    if position is None:
        if row['high'] > 86289.00:
            position = 'LONG'
            direction = 'LONG'
            entry_price = 86289.00
            sl = 86289.00 - 1.5 * 544.67
            print(f"[{idx}] TRIGGERED LONG at {entry_price:.2f}. Initial SL: {sl:.2f}")
        elif row['low'] < 86129.52:
            position = 'SHORT'
            direction = 'SHORT'
            entry_price = 86129.52
            sl = 86129.52 + 1.5 * 544.67
            print(f"[{idx}] TRIGGERED SHORT at {entry_price:.2f}. Initial SL: {sl:.2f}")
    else:
        if idx.minute == 0 and idx.second == 0:
            current_atr = compute_atr_14(df_btc_1h, idx)
            bar_close = df_btc_1h[df_btc_1h.index < idx].iloc[-1]['close']
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
    last = df_btc_1m.iloc[-1]
    if position == 'LONG':
        curr = (last['close'] - entry_price) * sizing * lot_multiplier
    else:
        curr = (entry_price - last['close']) * sizing * lot_multiplier
    print(f"[CURRENT] FLOATING {position}. PNL: ${curr:.2f}, Peak: ${highest_pnl:.2f}")
else:
    print("Flat.")

