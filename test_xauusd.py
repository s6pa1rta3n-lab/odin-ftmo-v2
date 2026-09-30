import yfinance as yf
import pandas as pd
import numpy as np

# Fetch Gold Data
data = yf.download("GC=F", interval="15m", period="60d", progress=False) # GC=F is Gold Futures, very close to XAUUSD
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

def compute_ema(prices, period=20):
    ema = np.zeros(len(prices))
    if len(prices) < period: return ema
    ema[period-1] = np.mean(prices[:period])
    multiplier = 2.0 / (period + 1)
    for i in range(period, len(prices)):
        ema[i] = (prices[i] - ema[i-1]) * multiplier + ema[i-1]
    return ema

data['ATR'] = compute_atr(data, 14)
data['EMA20'] = compute_ema(data['Close'].values, 20)

def run_ny_pullback():
    equity = 100000.0
    wins, losses = 0, 0
    state = 'SEARCHING'
    trade = None
    peak_equity = equity
    max_dd = 0.0
    for i in range(50, len(data)):
        row = data.iloc[i]
        prev = data.iloc[i-1]
        dt = data.index[i]
        time_str = dt.strftime('%H:%M')
        if state == 'SEARCHING':
            # Gold is highly active in NY Session
            if "08:30" <= time_str <= "11:30":
                trend = 'BUY' if prev['Close'] > prev['EMA20'] else 'SELL'
                triggered = False
                entry_price = row['EMA20']
                if trend == 'BUY' and row['Low'] <= entry_price <= row['High']: triggered = True
                elif trend == 'SELL' and row['Low'] <= entry_price <= row['High']: triggered = True
                
                if triggered:
                    # Gold needs slightly wider stop (2.0 ATR)
                    sl = entry_price - 2.0 * row['ATR'] if trend == 'BUY' else entry_price + 2.0 * row['ATR']
                    tp = entry_price + 4.0 * row['ATR'] if trend == 'BUY' else entry_price - 4.0 * row['ATR']
                    points = abs(entry_price - sl)
                    if points > 0:
                        trade = {'type': trend, 'entry': entry_price, 'sl': sl, 'tp': tp, 'vol': (equity*0.01)/points}
                        state = 'IN_TRADE'
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
    return equity, wins, losses, max_dd

def run_asian_breakout():
    equity = 100000.0
    wins, losses = 0, 0
    state = 'SEARCHING'
    trade = None
    peak_equity = equity
    max_dd = 0.0
    asian_high, asian_low = 0, 0
    
    for i in range(50, len(data)):
        row = data.iloc[i]
        dt = data.index[i]
        time_str = dt.strftime('%H:%M')
        
        # Asian Session (20:00 to 03:00 EST)
        if time_str == "03:00":
            window = data.iloc[i-28:i]
            asian_high = window['High'].max()
            asian_low = window['Low'].min()
            
        if state == 'SEARCHING' and asian_high > 0:
            # London/NY Breakout
            if "03:15" <= time_str <= "10:00":
                triggered = False
                trend = None
                entry_price = 0
                if row['High'] >= asian_high and data.iloc[i-1]['High'] < asian_high:
                    triggered = True
                    trend = 'BUY'
                    entry_price = asian_high
                elif row['Low'] <= asian_low and data.iloc[i-1]['Low'] > asian_low:
                    triggered = True
                    trend = 'SELL'
                    entry_price = asian_low
                    
                if triggered:
                    sl = entry_price - 1.5 * row['ATR'] if trend == 'BUY' else entry_price + 1.5 * row['ATR']
                    tp = entry_price + 3.0 * row['ATR'] if trend == 'BUY' else entry_price - 3.0 * row['ATR']
                    points = abs(entry_price - sl)
                    if points > 0:
                        trade = {'type': trend, 'entry': entry_price, 'sl': sl, 'tp': tp, 'vol': (equity*0.01)/points}
                        state = 'IN_TRADE'
                        asian_high = 0 # Prevent re-trigger
                        
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
    return equity, wins, losses, max_dd

eq1, w1, l1, dd1 = run_ny_pullback()
eq2, w2, l2, dd2 = run_asian_breakout()

print("GOLD (XAUUSD) 15m - NY SESSION PULLBACK (2.0 ATR SL):")
print(f"Equity: ${eq1:.2f} | Wins: {w1} | Losses: {l1} | Max DD: {dd1:.2f}%")
print("")
print("GOLD (XAUUSD) 15m - LONDON/NY ASIAN RANGE BREAKOUT:")
print(f"Equity: ${eq2:.2f} | Wins: {w2} | Losses: {l2} | Max DD: {dd2:.2f}%")
