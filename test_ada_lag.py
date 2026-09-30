import yfinance as yf
import pandas as pd
import numpy as np

# Fetch BTC and ADA 1H Data
btc = yf.download("BTC-USD", interval="1h", period="60d", progress=False)
ada = yf.download("ADA-USD", interval="1h", period="60d", progress=False)

if isinstance(btc.columns, pd.MultiIndex):
    btc.columns = [c[0] for c in btc.columns]
if isinstance(ada.columns, pd.MultiIndex):
    ada.columns = [c[0] for c in ada.columns]

# Align indexes
btc, ada = btc.align(ada, join='inner')

def compute_atr(df, period=14):
    high, low, close = df['High'].values, df['Low'].values, df['Close'].shift(1).values
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

def compute_ema(prices, period=50):
    ema = np.zeros(len(prices))
    if len(prices) < period: return ema
    ema[period-1] = np.mean(prices[:period])
    mult = 2.0 / (period + 1)
    for i in range(period, len(prices)):
        ema[i] = (prices[i] - ema[i-1]) * mult + ema[i-1]
    return ema

def compute_adx(df, period=14):
    adx = np.zeros(len(df))
    high, low, close = df['High'].values, df['Low'].values, df['Close'].shift(1).values
    tr_list, pdm, ndm = [0], [0], [0]
    for i in range(1, len(df)):
        tr = max(high[i] - low[i], abs(high[i] - close[i]), abs(low[i] - close[i]))
        up = high[i] - high[i-1]
        dn = low[i-1] - low[i]
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
    for i in range(period*2, len(df)):
        adx[i] = (adx[i-1] * (period - 1) + dx[i]) / period
    return adx

btc['ATR'] = compute_atr(btc, 14)
btc['EMA50'] = compute_ema(btc['Close'].values, 50)
btc['ADX'] = compute_adx(btc, 14)

ada['ATR'] = compute_atr(ada, 14)
ada['EMA50'] = compute_ema(ada['Close'].values, 50)
ada['ADX'] = compute_adx(ada, 14)

def run_strategy(asset_signals, asset_trade, name):
    equity = 100000.0
    wins, losses = 0, 0
    state = 'SEARCHING'
    trade = None
    peak = equity
    max_dd = 0.0
    
    for i in range(50, len(asset_signals)-1):
        sig_row = asset_signals.iloc[i]
        sig_prev = asset_signals.iloc[i-1]
        sig_mother = asset_signals.iloc[i-2]
        
        tr_row = asset_trade.iloc[i]
        tr_next = asset_trade.iloc[i+1]
        
        if state == 'SEARCHING':
            # Signal based on `asset_signals` (Can be BTC or ADA chart)
            if sig_prev['High'] < sig_mother['High'] and sig_prev['Low'] > sig_mother['Low']:
                if sig_row['ADX'] >= 25:
                    trend = 'BUY' if sig_prev['Close'] > sig_row['EMA50'] else 'SELL'
                    # Enter on `asset_trade` (Always ADA)
                    entry_price = tr_next['Open']
                    sl = entry_price - 1.5 * tr_row['ATR'] if trend == 'BUY' else entry_price + 1.5 * tr_row['ATR']
                    points = abs(entry_price - sl)
                    if points > 0:
                        trade = {'type': trend, 'entry': entry_price, 'sl': sl, 'vol': (equity*0.01)/points}
                        state = 'IN_TRADE'
                        
        elif state == 'IN_TRADE':
            hit_exit = False
            exit_price = 0
            if trade['type'] == 'BUY' and tr_next['Low'] <= trade['sl']:
                hit_exit, exit_price = True, trade['sl']
            elif trade['type'] == 'SELL' and tr_next['High'] >= trade['sl']:
                hit_exit, exit_price = True, trade['sl']
                
            if not hit_exit:
                if trade['type'] == 'BUY': trade['sl'] = max(trade['sl'], tr_next['Low'] - 1.5*tr_next['ATR'])
                else: trade['sl'] = min(trade['sl'], tr_next['High'] + 1.5*tr_next['ATR'])
            else:
                pnl = (exit_price - trade['entry']) * trade['vol'] if trade['type'] == 'BUY' else (trade['entry'] - exit_price) * trade['vol']
                equity += pnl
                if pnl > 0: wins += 1
                else: losses += 1
                if equity > peak: peak = equity
                dd = (peak - equity) / peak * 100
                if dd > max_dd: max_dd = dd
                state = 'SEARCHING'
                
    return equity, wins, losses, max_dd

# 1. Trade ADA using ADA's own chart signals
eq1, w1, l1, dd1 = run_strategy(ada, ada, "ADA Standalone")

# 2. Trade ADA using BTC's chart signals (Lead-Lag Arbitrage)
eq2, w2, l2, dd2 = run_strategy(btc, ada, "BTC Lead -> ADA Lag")

print("1. ADA STANDALONE (Traded using ADA's chart):")
print(f"Equity: ${eq1:.2f} | Wins: {w1} | Losses: {l1} | Max DD: {dd1:.2f}%")
print("")
print("2. LEAD-LAG ARBITRAGE (ADA traded using BTC's chart):")
print(f"Equity: ${eq2:.2f} | Wins: {w2} | Losses: {l2} | Max DD: {dd2:.2f}%")

# Statistical Lag Test: When BTC pumps > 1.5% in 1H, what does ADA do over the next 3 hours?
pump_returns = []
for i in range(1, len(btc)-3):
    btc_ret = (btc.iloc[i]['Close'] - btc.iloc[i]['Open']) / btc.iloc[i]['Open']
    if btc_ret > 0.015: # 1.5% pump
        ada_future_ret = (ada.iloc[i+3]['Close'] - ada.iloc[i]['Close']) / ada.iloc[i]['Close']
        pump_returns.append(ada_future_ret)

avg_lag = np.mean(pump_returns) * 100 if pump_returns else 0
win_rate = (sum(1 for x in pump_returns if x > 0) / len(pump_returns) * 100) if pump_returns else 0
print("")
print("3. STATISTICAL MOMENTUM LAG (Next 3 Hours):")
print(f"BTC 1.5%+ Pumps found: {len(pump_returns)}")
print(f"ADA Average Return (Next 3 Hrs): +{avg_lag:.2f}%")
print(f"Probability of ADA following BTC pump: {win_rate:.2f}%")
