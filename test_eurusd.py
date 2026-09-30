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

def compute_bb(prices, period=20, std=2):
    upper = np.zeros(len(prices))
    lower = np.zeros(len(prices))
    sma = np.zeros(len(prices))
    for i in range(period-1, len(prices)):
        window = prices[i-period+1:i+1]
        mean = np.mean(window)
        stdev = np.std(window)
        sma[i] = mean
        upper[i] = mean + (std * stdev)
        lower[i] = mean - (std * stdev)
    return upper, lower, sma

def compute_adx(df, period=14):
    # Simplified ADX logic for backtest proxy
    adx = np.zeros(len(df))
    high = df['High'].values
    low = df['Low'].values
    close = df['Close'].shift(1).values
    
    tr_list, pdm, ndm = [0], [0], [0]
    for i in range(1, len(df)):
        tr = max(high[i] - low[i], abs(high[i] - close[i]), abs(low[i] - close[i]))
        up = high[i] - high[i-1]
        dn = low[i-1] - low[i]
        pos = up if up > dn and up > 0 else 0
        neg = dn if dn > up and dn > 0 else 0
        tr_list.append(tr)
        pdm.append(pos)
        ndm.append(neg)
        
    dx = [0]*len(df)
    if len(df) <= period*2: return adx
    
    sm_tr = sum(tr_list[1:period+1])
    sm_pdm = sum(pdm[1:period+1])
    sm_ndm = sum(ndm[1:period+1])
    
    for i in range(period, len(df)):
        if i > period:
            sm_tr = sm_tr - (sm_tr / period) + tr_list[i]
            sm_pdm = sm_pdm - (sm_pdm / period) + pdm[i]
            sm_ndm = sm_ndm - (sm_ndm / period) + ndm[i]
        pdi = 100 * (sm_pdm / sm_tr) if sm_tr > 0 else 0
        ndi = 100 * (sm_ndm / sm_tr) if sm_tr > 0 else 0
        diff = abs(pdi - ndi)
        summ = pdi + ndi
        dx[i] = 100 * (diff / summ) if summ > 0 else 0
        
    adx[period*2 - 1] = sum(dx[period:period*2]) / period
    for i in range(period*2, len(df)):
        adx[i] = (adx[i-1] * (period - 1) + dx[i]) / period
    return adx

# Fetch 1H data for EURUSD
data = yf.download("EURUSD=X", interval="1h", period="60d", progress=False)
if isinstance(data.columns, pd.MultiIndex):
    data.columns = [c[0] for c in data.columns]

if data.index.tz is None:
    data.index = data.index.tz_localize('UTC')

data['ATR'] = compute_atr(data, 14)
data['EMA50'] = compute_ema(data['Close'].values, 50)
data['ADX'] = compute_adx(data, 14)
upper, lower, sma = compute_bb(data['Close'].values, 20, 2)
data['BB_UP'] = upper
data['BB_DN'] = lower
data['BB_MID'] = sma

# Strategy 1: Griff Breakout (Trend Following)
def run_breakout():
    equity = 100000.0
    wins, losses = 0, 0
    state = 'SEARCHING'
    trade = None
    peak_equity = equity
    max_dd = 0.0
    
    for i in range(50, len(data)-1):
        row = data.iloc[i]
        next_row = data.iloc[i+1]
        prev = data.iloc[i-1]
        mother = data.iloc[i-2]
        
        if state == 'SEARCHING':
            if prev['High'] < mother['High'] and prev['Low'] > mother['Low']: # Inside Bar
                if row['ADX'] >= 25: # ADX filter
                    trend = 'BUY' if prev['Close'] > row['EMA50'] else 'SELL'
                    entry_price = prev['High'] if trend == 'BUY' else prev['Low']
                    
                    triggered = False
                    if trend == 'BUY' and next_row['High'] >= entry_price: triggered = True
                    elif trend == 'SELL' and next_row['Low'] <= entry_price: triggered = True
                        
                    if triggered:
                        sl = entry_price - 1.5*row['ATR'] if trend == 'BUY' else entry_price + 1.5*row['ATR']
                        points = abs(entry_price - sl)
                        if points > 0:
                            trade = {'type': trend, 'entry': entry_price, 'sl': sl, 'vol': (equity*0.01)/points}
                            state = 'IN_TRADE'
        
        elif state == 'IN_TRADE':
            hit_exit = False
            exit_price = 0
            if trade['type'] == 'BUY' and next_row['Low'] <= trade['sl']:
                hit_exit, exit_price = True, trade['sl']
            elif trade['type'] == 'SELL' and next_row['High'] >= trade['sl']:
                hit_exit, exit_price = True, trade['sl']
                
            if not hit_exit:
                if trade['type'] == 'BUY': trade['sl'] = max(trade['sl'], next_row['Low'] - 1.5*next_row['ATR'])
                else: trade['sl'] = min(trade['sl'], next_row['High'] + 1.5*next_row['ATR'])
            else:
                pnl = (exit_price - trade['entry']) * trade['vol'] if trade['type'] == 'BUY' else (trade['entry'] - exit_price) * trade['vol']
                equity += pnl
                if pnl > 0: wins += 1
                else: losses += 1
                if equity > peak_equity: peak_equity = equity
                dd = (peak_equity - equity) / peak_equity * 100
                if dd > max_dd: max_dd = dd
                state = 'SEARCHING'
    return equity, wins, losses, max_dd

# Strategy 2: Mean Reversion (Fade Bollinger Bands when ADX < 25)
def run_mean_reversion():
    equity = 100000.0
    wins, losses = 0, 0
    state = 'SEARCHING'
    trade = None
    peak_equity = equity
    max_dd = 0.0
    
    for i in range(50, len(data)-1):
        row = data.iloc[i]
        next_row = data.iloc[i+1]
        prev = data.iloc[i-1]
        
        if state == 'SEARCHING':
            if row['ADX'] < 25: # Ranging Market
                trend = None
                if prev['Close'] > prev['BB_UP']:
                    trend = 'SELL'
                elif prev['Close'] < prev['BB_DN']:
                    trend = 'BUY'
                    
                if trend:
                    entry_price = next_row['Open']
                    sl = entry_price - 1.5*row['ATR'] if trend == 'BUY' else entry_price + 1.5*row['ATR']
                    tp = row['BB_MID'] # Target the middle SMA
                    points = abs(entry_price - sl)
                    if points > 0:
                        trade = {'type': trend, 'entry': entry_price, 'sl': sl, 'tp': tp, 'vol': (equity*0.01)/points}
                        state = 'IN_TRADE'
        
        elif state == 'IN_TRADE':
            hit_exit = False
            exit_price = 0
            if trade['type'] == 'BUY':
                if next_row['Low'] <= trade['sl']: hit_exit, exit_price = True, trade['sl']
                elif next_row['High'] >= trade['tp']: hit_exit, exit_price = True, trade['tp']
            else:
                if next_row['High'] >= trade['sl']: hit_exit, exit_price = True, trade['sl']
                elif next_row['Low'] <= trade['tp']: hit_exit, exit_price = True, trade['tp']
                
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

eq1, w1, l1, dd1 = run_breakout()
eq2, w2, l2, dd2 = run_mean_reversion()

print("EURUSD 1H - GRIFF BREAKOUT + ADX (Trend Following):")
print(f"Equity: ${eq1:.2f} | Wins: {w1} | Losses: {l1} | Max DD: {dd1:.2f}%")
print("")
print("EURUSD 1H - BOLLINGER MEAN REVERSION (ADX < 25):")
print(f"Equity: ${eq2:.2f} | Wins: {w2} | Losses: {l2} | Max DD: {dd2:.2f}%")

data15 = yf.download("EURUSD=X", interval="15m", period="60d", progress=False)
if isinstance(data15.columns, pd.MultiIndex):
    data15.columns = [c[0] for c in data15.columns]
if data15.index.tz is None:
    data15.index = data15.index.tz_localize('UTC').tz_convert('US/Eastern')
else:
    data15.index = data15.index.tz_convert('US/Eastern')
data15['ATR'] = compute_atr(data15, 14)
data15['EMA20'] = compute_ema(data15['Close'].values, 20)

def run_ny_pullback():
    equity = 100000.0
    wins, losses = 0, 0
    state = 'SEARCHING'
    trade = None
    peak_equity = equity
    max_dd = 0.0
    for i in range(20, len(data15)):
        row = data15.iloc[i]
        prev = data15.iloc[i-1]
        dt = data15.index[i]
        time_str = dt.strftime('%H:%M')
        if state == 'SEARCHING':
            if "08:00" <= time_str <= "11:30": # London/NY overlap for EURUSD
                trend = 'BUY' if prev['Close'] > prev['EMA20'] else 'SELL'
                triggered = False
                entry_price = row['EMA20']
                if trend == 'BUY' and row['Low'] <= entry_price <= row['High']: triggered = True
                elif trend == 'SELL' and row['Low'] <= entry_price <= row['High']: triggered = True
                if triggered:
                    sl = entry_price - 1.5 * row['ATR'] if trend == 'BUY' else entry_price + 1.5 * row['ATR']
                    tp = entry_price + 3.0 * row['ATR'] if trend == 'BUY' else entry_price - 3.0 * row['ATR']
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

eq3, w3, l3, dd3 = run_ny_pullback()
print("EURUSD 15m - NY/LONDON PULLBACK:")
print(f"Equity: ${eq3:.2f} | Wins: {w3} | Losses: {l3} | Max DD: {dd3:.2f}%")
