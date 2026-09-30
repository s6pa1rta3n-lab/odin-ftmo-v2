import yfinance as yf
import pandas as pd
import numpy as np

def compute_atr(df, period=14):
    high = df['High'].values
    low = df['Low'].values
    close = df['Close'].shift(1).values
    
    tr1 = high - low
    tr2 = np.abs(high - close)
    tr3 = np.abs(low - close)
    
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    tr[0] = tr1[0] # handle nan
    
    atr = np.zeros(len(df))
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

# Fetch 15-minute data
data = yf.download("NQ=F", interval="15m", period="60d", progress=False)
if isinstance(data.columns, pd.MultiIndex):
    data.columns = [c[0] for c in data.columns]

# Ensure timezone is US/Eastern
if data.index.tz is None:
    data.index = data.index.tz_localize('UTC').tz_convert('US/Eastern')
else:
    data.index = data.index.tz_convert('US/Eastern')

data['ATR'] = compute_atr(data)
data['EMA20'] = compute_ema(data['Close'].values, 20)

equity = 100000.0
wins = 0
losses = 0
max_drawdown = 0.0
peak_equity = equity

state = 'SEARCHING'
trade = None

results = []

for i in range(20, len(data)):
    row = data.iloc[i]
    prev = data.iloc[i-1]
    
    dt = data.index[i]
    time_str = dt.strftime('%H:%M')
    
    if state == 'SEARCHING':
        # Time Filter: Only look for setups between 9:45 AM and 11:30 AM EST
        if "09:45" <= time_str <= "11:30":
            # Establish Trend from previous candle
            trend = 'BUY' if prev['Close'] > prev['EMA20'] else 'SELL'
            
            # Did price pull back to EMA20 on current candle?
            triggered = False
            entry_price = row['EMA20']
            
            if trend == 'BUY' and row['Low'] <= entry_price <= row['High']:
                triggered = True
            elif trend == 'SELL' and row['Low'] <= entry_price <= row['High']:
                triggered = True
                
            if triggered:
                sl = entry_price - 1.5 * row['ATR'] if trend == 'BUY' else entry_price + 1.5 * row['ATR']
                tp = entry_price + 3.0 * row['ATR'] if trend == 'BUY' else entry_price - 3.0 * row['ATR'] # 1:2 RR
                
                points = abs(entry_price - sl)
                if points > 0:
                    vol = (equity * 0.01) / points
                    trade = {'type': trend, 'entry': entry_price, 'sl': sl, 'tp': tp, 'vol': vol, 'entry_time': time_str}
                    state = 'IN_TRADE'
                    
    elif state == 'IN_TRADE':
        hit_exit = False
        exit_price = 0
        
        # Check SL/TP
        if trade['type'] == 'BUY':
            if row['Low'] <= trade['sl']:
                hit_exit, exit_price = True, trade['sl']
            elif row['High'] >= trade['tp']:
                hit_exit, exit_price = True, trade['tp']
        else:
            if row['High'] >= trade['sl']:
                hit_exit, exit_price = True, trade['sl']
            elif row['Low'] <= trade['tp']:
                hit_exit, exit_price = True, trade['tp']
                
        # Time-based exit: Close at 16:00 (4 PM EST) if still open
        if not hit_exit and time_str >= "16:00":
            hit_exit = True
            exit_price = row['Close']
            
        if hit_exit:
            pnl = (exit_price - trade['entry']) * trade['vol'] if trade['type'] == 'BUY' else (trade['entry'] - exit_price) * trade['vol']
            equity += pnl
            if pnl > 0: wins += 1
            else: losses += 1
            
            if equity > peak_equity: peak_equity = equity
            dd = (peak_equity - equity) / peak_equity * 100
            if dd > max_drawdown: max_drawdown = dd
            
            results.append(pnl)
            state = 'SEARCHING'
            # Prevent taking another trade on the same day by artificially skipping?
            # We'll just let it search again, but usually it's late enough.

print(f"--- NY SESSION PULLBACK (US100 15m) ---")
print(f"Ending Equity: ${equity:.2f}")
print(f"Net Profit: ${equity - 100000:.2f}")
print(f"Wins: {wins} | Losses: {losses} | Win Rate: {wins/(wins+losses)*100 if wins+losses>0 else 0:.1f}%")
print(f"Max Drawdown: {max_drawdown:.2f}%")
