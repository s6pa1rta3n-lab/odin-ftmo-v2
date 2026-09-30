import yfinance as yf
import pandas as pd
import numpy as np

data = yf.download("EURUSD=X", interval="15m", period="60d", progress=False)
if isinstance(data.columns, pd.MultiIndex):
    data.columns = [c[0] for c in data.columns]
if data.index.tz is None:
    data.index = data.index.tz_localize('UTC').tz_convert('US/Eastern')
else:
    data.index = data.index.tz_convert('US/Eastern')

def compute_atr(df, period=14):
    high = df['High'].values
    low = df['Low'].values
    close = df['Close'].shift(1).values
    tr1 = high - low
    tr2 = np.abs(high - close)
    tr3 = np.abs(low - close)
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    tr[0] = tr1[0]
    atr = np.zeros(len(df))
    if len(df) <= period: return atr
    atr[period] = np.mean(tr[1:period+1])
    for i in range(period+1, len(df)):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    return atr

data['ATR'] = compute_atr(data, 14)

equity = 100000.0
wins, losses = 0, 0
peak_equity = equity
max_dd = 0.0

state = 'SEARCHING'
trade = None
asian_high = 0
asian_low = 0

for i in range(50, len(data)):
    row = data.iloc[i]
    dt = data.index[i]
    time_str = dt.strftime('%H:%M')
    
    # Define Asian Range (20:00 to 02:00 EST)
    if time_str == "02:00":
        # Look back to get high/low of the last 24 candles (6 hours)
        window = data.iloc[i-24:i]
        asian_high = window['High'].max()
        asian_low = window['Low'].min()
        
    if state == 'SEARCHING' and asian_high > 0:
        # London Session Fakeout (Judas Swing) - 03:00 to 08:00 EST
        if "03:00" <= time_str <= "10:00":
            # If price sweeps the Asian High and rejects (closes below it), we short.
            if data.iloc[i-1]['High'] > asian_high and row['Close'] < asian_high:
                sl = row['Close'] + 1.5 * row['ATR']
                tp = row['Close'] - 1.5 * row['ATR'] # 1:1 RR for high win rate
                points = abs(row['Close'] - sl)
                trade = {'type': 'SELL', 'entry': row['Close'], 'sl': sl, 'tp': tp, 'vol': (equity*0.01)/points}
                state = 'IN_TRADE'
                asian_high = 0 # Prevent multiple triggers
                
            # If price sweeps Asian Low and rejects (closes above), we long.
            elif data.iloc[i-1]['Low'] < asian_low and row['Close'] > asian_low:
                sl = row['Close'] - 1.5 * row['ATR']
                tp = row['Close'] + 1.5 * row['ATR']
                points = abs(row['Close'] - sl)
                trade = {'type': 'BUY', 'entry': row['Close'], 'sl': sl, 'tp': tp, 'vol': (equity*0.01)/points}
                state = 'IN_TRADE'
                asian_low = 0
                
    elif state == 'IN_TRADE':
        hit_exit = False
        exit_price = 0
        if trade['type'] == 'BUY':
            if row['Low'] <= trade['sl']: hit_exit, exit_price = True, trade['sl']
            elif row['High'] >= trade['tp']: hit_exit, exit_price = True, trade['tp']
        else:
            if row['High'] >= trade['sl']: hit_exit, exit_price = True, trade['sl']
            elif row['Low'] <= trade['tp']: hit_exit, exit_price = True, trade['tp']
            
        if not hit_exit and time_str >= "16:00":
            hit_exit, exit_price = True, row['Close']
            
        if hit_exit:
            pnl = (exit_price - trade['entry']) * trade['vol'] if trade['type'] == 'BUY' else (trade['entry'] - exit_price) * trade['vol']
            equity += pnl
            if pnl > 0: wins += 1
            else: losses += 1
            if equity > peak_equity: peak_equity = equity
            dd = (peak_equity - equity) / peak_equity * 100
            if dd > max_dd: max_dd = dd
            state = 'SEARCHING'

print(f"EURUSD 15m - ASIAN RANGE FAKEOUT (1:1 R/R):")
print(f"Equity: ${equity:.2f} | Wins: {wins} | Losses: {losses} | Max DD: {max_dd:.2f}%")
