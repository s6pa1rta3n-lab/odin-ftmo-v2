import yfinance as yf
import pandas as pd
import numpy as np
from datetime import timedelta

def compute_atr(df, period=14):
    high, low, close = df['High'].values, df['Low'].values, df['Close'].shift(1).values
    tr = np.maximum(high - low, np.maximum(np.abs(high - close), np.abs(low - close)))
    tr[0] = high[0] - low[0]
    atr = np.zeros(len(df))
    if len(df) <= period: return atr
    atr[period] = np.mean(tr[1:period+1])
    for i in range(period+1, len(df)): atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    return atr

def compute_ema(prices, period):
    ema = np.zeros(len(prices))
    if len(prices) < period: return ema
    ema[period-1] = np.mean(prices[:period])
    mult = 2.0 / (period + 1)
    for i in range(period, len(prices)): ema[i] = (prices[i] - ema[i-1]) * mult + ema[i-1]
    return ema

def compute_adx(df, period=14):
    adx = np.zeros(len(df))
    high, low, close = df['High'].values, df['Low'].values, df['Close'].shift(1).values
    tr_list, pdm, ndm = [0], [0], [0]
    for i in range(1, len(df)):
        tr = max(high[i] - low[i], abs(high[i] - close[i]), abs(low[i] - close[i]))
        up, dn = high[i] - high[i-1], low[i-1] - low[i]
        tr_list.append(tr)
        pdm.append(up if up > dn and up > 0 else 0)
        ndm.append(dn if dn > up and dn > 0 else 0)
    dx = [0]*len(df)
    if len(df) <= period*2: return adx
    sm_tr, sm_pdm, sm_ndm = sum(tr_list[1:period+1]), sum(pdm[1:period+1]), sum(ndm[1:period+1])
    for i in range(period, len(df)):
        if i > period:
            sm_tr = sm_tr - (sm_tr / period) + tr_list[i]
            sm_pdm = sm_pdm - (sm_pdm / period) + pdm[i]
            sm_ndm = sm_ndm - (sm_ndm / period) + ndm[i]
        pdi = 100 * (sm_pdm / sm_tr) if sm_tr > 0 else 0
        ndi = 100 * (sm_ndm / sm_tr) if sm_tr > 0 else 0
        summ = pdi + ndi
        dx[i] = 100 * (abs(pdi - ndi) / summ) if summ > 0 else 0
    adx[period*2 - 1] = sum(dx[period:period*2]) / period
    for i in range(period*2, len(df)): adx[i] = (adx[i-1] * (period - 1) + dx[i]) / period
    return adx

# Fetch Data
print("Fetching data...")
us100 = yf.download("NQ=F", interval="15m", period="60d", progress=False)
gold = yf.download("GC=F", interval="15m", period="60d", progress=False)
btc = yf.download("BTC-USD", interval="1h", period="60d", progress=False)

for df in [us100, gold, btc]:
    if isinstance(df.columns, pd.MultiIndex): df.columns = [c[0] for c in df.columns]
    if df.index.tz is None: df.index = df.index.tz_localize('UTC').tz_convert('US/Eastern')
    else: df.index = df.index.tz_convert('US/Eastern')
    df['ATR'] = compute_atr(df)

us100['EMA20'] = compute_ema(us100['Close'].values, 20)
btc['EMA50'] = compute_ema(btc['Close'].values, 50)
btc['ADX'] = compute_adx(btc)

# Track PNL by Day
daily_pnl = {}

def add_pnl(dt, pnl):
    d_str = dt.strftime('%Y-%m-%d')
    daily_pnl[d_str] = daily_pnl.get(d_str, 0) + pnl

# --- 1. US100 NY Pullback ---
equity_us100 = 100000.0
state = 'SEARCHING'
trade = None
for i in range(20, len(us100)):
    row, prev, dt = us100.iloc[i], us100.iloc[i-1], us100.index[i]
    t_str = dt.strftime('%H:%M')
    if state == 'SEARCHING':
        if "09:45" <= t_str <= "11:30":
            trend = 'BUY' if prev['Close'] > prev['EMA20'] else 'SELL'
            ep = row['EMA20']
            if (trend == 'BUY' and row['Low'] <= ep <= row['High']) or (trend == 'SELL' and row['Low'] <= ep <= row['High']):
                sl = ep - 1.5 * row['ATR'] if trend == 'BUY' else ep + 1.5 * row['ATR']
                tp = ep + 3.0 * row['ATR'] if trend == 'BUY' else ep - 3.0 * row['ATR']
                pts = abs(ep - sl)
                if pts > 0:
                    trade = {'type': trend, 'ep': ep, 'sl': sl, 'tp': tp, 'vol': (equity_us100*0.01)/pts}
                    state = 'IN_TRADE'
    elif state == 'IN_TRADE':
        hit, exp = False, 0
        if trade['type'] == 'BUY':
            if row['Low'] <= trade['sl']: hit, exp = True, trade['sl']
            elif row['High'] >= trade['tp']: hit, exp = True, trade['tp']
        else:
            if row['High'] >= trade['sl']: hit, exp = True, trade['sl']
            elif row['Low'] <= trade['tp']: hit, exp = True, trade['tp']
        if not hit and t_str >= "16:00": hit, exp = True, row['Close']
        if hit:
            pnl = (exp - trade['ep']) * trade['vol'] if trade['type'] == 'BUY' else (trade['ep'] - exp) * trade['vol']
            add_pnl(dt, pnl)
            state = 'SEARCHING'

# --- 2. GOLD Asian Range Breakout ---
equity_gold = 100000.0
state = 'SEARCHING'
trade = None
ah, al = 0, 0
for i in range(30, len(gold)):
    row, prev, dt = gold.iloc[i], gold.iloc[i-1], gold.index[i]
    t_str = dt.strftime('%H:%M')
    if t_str == "03:00":
        win = gold.iloc[i-28:i]
        ah, al = win['High'].max(), win['Low'].min()
    if state == 'SEARCHING' and ah > 0:
        if "03:15" <= t_str <= "10:00":
            if row['High'] >= ah and prev['High'] < ah:
                ep, trend = ah, 'BUY'
            elif row['Low'] <= al and prev['Low'] > al:
                ep, trend = al, 'SELL'
            else: continue
            sl = ep - 1.5 * row['ATR'] if trend == 'BUY' else ep + 1.5 * row['ATR']
            tp = ep + 3.0 * row['ATR'] if trend == 'BUY' else ep - 3.0 * row['ATR']
            pts = abs(ep - sl)
            if pts > 0:
                trade = {'type': trend, 'ep': ep, 'sl': sl, 'tp': tp, 'vol': (equity_gold*0.01)/pts}
                state = 'IN_TRADE'
                ah = 0
    elif state == 'IN_TRADE':
        hit, exp = False, 0
        if trade['type'] == 'BUY':
            if row['Low'] <= trade['sl']: hit, exp = True, trade['sl']
            elif row['High'] >= trade['tp']: hit, exp = True, trade['tp']
        else:
            if row['High'] >= trade['sl']: hit, exp = True, trade['sl']
            elif row['Low'] <= trade['tp']: hit, exp = True, trade['tp']
        if not hit and t_str >= "16:00": hit, exp = True, row['Close']
        if hit:
            pnl = (exp - trade['ep']) * trade['vol'] if trade['type'] == 'BUY' else (trade['ep'] - exp) * trade['vol']
            add_pnl(dt, pnl)
            state = 'SEARCHING'

# --- 3. BTC 1H Breakout ---
equity_btc = 100000.0
state = 'SEARCHING'
trade = None
for i in range(50, len(btc)-1):
    row, prev, mother, dt = btc.iloc[i], btc.iloc[i-1], btc.iloc[i-2], btc.index[i]
    nxt = btc.iloc[i+1]
    if state == 'SEARCHING':
        if prev['High'] < mother['High'] and prev['Low'] > mother['Low']:
            if row['ADX'] >= 25:
                trend = 'BUY' if prev['Close'] > row['EMA50'] else 'SELL'
                ep = prev['High'] if trend == 'BUY' else prev['Low']
                trig = False
                if trend == 'BUY' and nxt['High'] >= ep: trig = True
                elif trend == 'SELL' and nxt['Low'] <= ep: trig = True
                if trig:
                    sl = ep - 1.5*row['ATR'] if trend == 'BUY' else ep + 1.5*row['ATR']
                    pts = abs(ep - sl)
                    if pts > 0:
                        trade = {'type': trend, 'ep': ep, 'sl': sl, 'vol': (equity_btc*0.01)/pts}
                        state = 'IN_TRADE'
    elif state == 'IN_TRADE':
        hit, exp = False, 0
        if trade['type'] == 'BUY' and nxt['Low'] <= trade['sl']: hit, exp = True, trade['sl']
        elif trade['type'] == 'SELL' and nxt['High'] >= trade['sl']: hit, exp = True, trade['sl']
        if not hit:
            if trade['type'] == 'BUY': trade['sl'] = max(trade['sl'], nxt['Low'] - 1.5*nxt['ATR'])
            else: trade['sl'] = min(trade['sl'], nxt['High'] + 1.5*nxt['ATR'])
        else:
            pnl = (exp - trade['ep']) * trade['vol'] if trade['type'] == 'BUY' else (trade['ep'] - exp) * trade['vol']
            add_pnl(nxt.name, pnl)
            state = 'SEARCHING'

# --- Combine Portfolios ---
dates = sorted(daily_pnl.keys())
running_eq = 100000.0
peak = 100000.0
max_dd = 0.0
total_pnl = 0

for d in dates:
    pnl = daily_pnl[d]
    running_eq += pnl
    total_pnl += pnl
    if running_eq > peak: peak = running_eq
    dd = (peak - running_eq) / peak * 100
    if dd > max_dd: max_dd = dd

wins = sum(1 for v in daily_pnl.values() if v > 0)
losses = sum(1 for v in daily_pnl.values() if v <= 0)

print("=== COMBINED PORTFOLIO PERFORMANCE (60 DAYS) ===")
print(f"Total Net Profit: ${total_pnl:,.2f} (+{(total_pnl/100000)*100:.2f}%)")
print(f"Combined Max Drawdown: {max_dd:.2f}%")
print(f"Profitable Days: {wins} | Losing Days: {losses}")
