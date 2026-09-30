import yfinance as yf
import pandas as pd
import numpy as np

# Fetch BTC, ETH, and SOL 1H Data
btc = yf.download("BTC-USD", interval="1h", period="60d", progress=False)
eth = yf.download("ETH-USD", interval="1h", period="60d", progress=False)
sol = yf.download("SOL-USD", interval="1h", period="60d", progress=False)

if isinstance(btc.columns, pd.MultiIndex): btc.columns = [c[0] for c in btc.columns]
if isinstance(eth.columns, pd.MultiIndex): eth.columns = [c[0] for c in eth.columns]
if isinstance(sol.columns, pd.MultiIndex): sol.columns = [c[0] for c in sol.columns]

btc, eth = btc.align(eth, join='inner')
btc, sol = btc.align(sol, join='inner')

def compute_atr(df, period=14):
    high, low, close = df['High'].values, df['Low'].values, df['Close'].shift(1).values
    tr = np.maximum(high - low, np.maximum(np.abs(high - close), np.abs(low - close)))
    tr[0] = high[0] - low[0]
    atr = np.zeros(len(df))
    if len(df) <= period: return atr
    atr[period] = np.mean(tr[1:period+1])
    for i in range(period+1, len(df)): atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
    return atr

def compute_ema(prices, period=50):
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

btc['ATR'], btc['EMA50'], btc['ADX'] = compute_atr(btc), compute_ema(btc['Close'].values), compute_adx(btc)
eth['ATR'], eth['EMA50'] = compute_atr(eth), compute_ema(eth['Close'].values)
sol['ATR'], sol['EMA50'] = compute_atr(sol), compute_ema(sol['Close'].values)

def run_lead_lag(lead_df, lag_df):
    equity = 100000.0
    wins, losses = 0, 0
    state = 'SEARCHING'
    trade = None
    peak, max_dd = equity, 0.0
    
    for i in range(50, len(lead_df)-1):
        sig_row, sig_prev, sig_mother = lead_df.iloc[i], lead_df.iloc[i-1], lead_df.iloc[i-2]
        tr_row, tr_next = lag_df.iloc[i], lag_df.iloc[i+1]
        
        if state == 'SEARCHING':
            if sig_prev['High'] < sig_mother['High'] and sig_prev['Low'] > sig_mother['Low']:
                if sig_row['ADX'] >= 25:
                    trend = 'BUY' if sig_prev['Close'] > sig_row['EMA50'] else 'SELL'
                    entry_price = tr_next['Open']
                    sl = entry_price - 1.5 * tr_row['ATR'] if trend == 'BUY' else entry_price + 1.5 * tr_row['ATR']
                    points = abs(entry_price - sl)
                    if points > 0:
                        trade = {'type': trend, 'entry': entry_price, 'sl': sl, 'vol': (equity*0.01)/points}
                        state = 'IN_TRADE'
                        
        elif state == 'IN_TRADE':
            hit_exit = False
            exit_price = 0
            if trade['type'] == 'BUY' and tr_next['Low'] <= trade['sl']: hit_exit, exit_price = True, trade['sl']
            elif trade['type'] == 'SELL' and tr_next['High'] >= trade['sl']: hit_exit, exit_price = True, trade['sl']
                
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

def get_lag_stats(lag_df):
    pump_returns = []
    for i in range(1, len(btc)-3):
        if (btc.iloc[i]['Close'] - btc.iloc[i]['Open']) / btc.iloc[i]['Open'] > 0.015:
            pump_returns.append((lag_df.iloc[i+3]['Close'] - lag_df.iloc[i]['Close']) / lag_df.iloc[i]['Close'])
    return np.mean(pump_returns)*100, (sum(1 for x in pump_returns if x > 0) / len(pump_returns)*100)

eth_eq, eth_w, eth_l, eth_dd = run_lead_lag(btc, eth)
sol_eq, sol_w, sol_l, sol_dd = run_lead_lag(btc, sol)

eth_avg, eth_prob = get_lag_stats(eth)
sol_avg, sol_prob = get_lag_stats(sol)

print("--- ETHEREUM (ETH) LEAD-LAG ---")
print(f"Equity: ${eth_eq:.2f} | Wins: {eth_w} | Losses: {eth_l} | Max DD: {eth_dd:.2f}%")
print(f"Stat Lag Return: +{eth_avg:.2f}% | Follow Probability: {eth_prob:.2f}%")
print("")
print("--- SOLANA (SOL) LEAD-LAG ---")
print(f"Equity: ${sol_eq:.2f} | Wins: {sol_w} | Losses: {sol_l} | Max DD: {sol_dd:.2f}%")
print(f"Stat Lag Return: +{sol_avg:.2f}% | Follow Probability: {sol_prob:.2f}%")
