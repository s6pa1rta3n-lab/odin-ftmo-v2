import requests
import math

def fetch_historical_klines(symbol='BTCUSDT', interval='1h', limit=1500):
    url = 'https://fapi.binance.com/fapi/v1/klines'
    params = {'symbol': symbol, 'interval': interval, 'limit': limit}
    r = requests.get(url, params=params)
    data = r.json()
    candles = []
    for d in data:
        candles.append({
            'time': d[0], 'open': float(d[1]), 'high': float(d[2]),
            'low': float(d[3]), 'close': float(d[4])
        })
    return candles

def compute_atr(candles, period=14):
    tr_list = [0]
    for i in range(1, len(candles)):
        c, pc = candles[i], candles[i-1]
        tr = max(c['high'] - c['low'], abs(c['high'] - pc['close']), abs(c['low'] - pc['close']))
        tr_list.append(tr)
    atr = [0]*len(candles)
    if len(candles) <= period: return atr
    atr[period] = sum(tr_list[1:period+1])/period
    for i in range(period+1, len(candles)):
        atr[i] = (atr[i-1] * (period - 1) + tr_list[i]) / period
    return atr

def compute_adx(candles, period=14):
    tr_list, pdm, ndm = [0], [0], [0]
    for i in range(1, len(candles)):
        c, pc = candles[i], candles[i-1]
        tr = max(c['high'] - c['low'], abs(c['high'] - pc['close']), abs(c['low'] - pc['close']))
        up = c['high'] - pc['high']
        dn = pc['low'] - c['low']
        pos = up if up > dn and up > 0 else 0
        neg = dn if dn > up and dn > 0 else 0
        tr_list.append(tr)
        pdm.append(pos)
        ndm.append(neg)
    
    adx, dx = [0]*len(candles), [0]*len(candles)
    if len(candles) <= period*2: return adx
    
    sm_tr = sum(tr_list[1:period+1])
    sm_pdm = sum(pdm[1:period+1])
    sm_ndm = sum(ndm[1:period+1])
    
    for i in range(period, len(candles)):
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
    for i in range(period*2, len(candles)):
        adx[i] = (adx[i-1] * (period - 1) + dx[i]) / period
    return adx

def compute_bb(candles, period=20, std=2):
    upper, lower, sma = [0]*len(candles), [0]*len(candles), [0]*len(candles)
    closes = [c['close'] for c in candles]
    for i in range(period-1, len(candles)):
        window = closes[i-period+1:i+1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        stdev = math.sqrt(variance)
        sma[i] = mean
        upper[i] = mean + (std * stdev)
        lower[i] = mean - (std * stdev)
    return upper, lower, sma

def compute_ema(candles, period=50):
    closes = [c['close'] for c in candles]
    emas = [0]*len(candles)
    if len(closes) < period: return emas
    ema = sum(closes[:period])/period
    emas[period-1] = ema
    multiplier = 2.0 / (period + 1)
    for i in range(period, len(closes)):
        ema = (closes[i] - ema) * multiplier + ema
        emas[i] = ema
    return emas

def run_backtest(candles, use_regime_filter=False, use_mean_reversion=False):
    atr = compute_atr(candles)
    ema = compute_ema(candles)
    adx = compute_adx(candles)
    upper, lower, sma = compute_bb(candles)
    
    equity = 100000.0
    win = 0
    loss = 0
    
    state = 'SEARCHING'
    trade = None
    
    for i in range(50, len(candles)-1):
        c = candles[i]
        next_c = candles[i+1]
        
        if state == 'SEARCHING':
            prev = candles[i-1]
            mother = candles[i-2]
            
            is_trending = adx[i-1] >= 25
            
            if (not use_regime_filter) or (use_regime_filter and is_trending):
                if prev['high'] < mother['high'] and prev['low'] > mother['low']:
                    trend = 'BUY' if prev['close'] > ema[i-1] else 'SELL'
                    entry_price = prev['high'] if trend == 'BUY' else prev['low']
                    
                    triggered = False
                    if trend == 'BUY' and next_c['high'] >= entry_price: triggered = True
                    elif trend == 'SELL' and next_c['low'] <= entry_price: triggered = True
                        
                    if triggered:
                        sl = entry_price - 1.5*atr[i-1] if trend == 'BUY' else entry_price + 1.5*atr[i-1]
                        points = abs(entry_price - sl)
                        if points > 0:
                            trade = {'type': trend, 'entry': entry_price, 'sl': sl, 'vol': (equity*0.01)/points, 'gear': 1}
                            state = 'IN_TRADE'
                            continue

            if use_mean_reversion and not is_trending:
                trend = None
                entry_price = next_c['open']
                if prev['close'] > upper[i-1]:
                    trend = 'SELL'
                    tp = sma[i-1]
                    sl = entry_price + 1.5*atr[i-1]
                elif prev['close'] < lower[i-1]:
                    trend = 'BUY'
                    tp = sma[i-1]
                    sl = entry_price - 1.5*atr[i-1]
                
                if trend:
                    points = abs(entry_price - sl)
                    if points > 0:
                        trade = {'type': trend, 'entry': entry_price, 'sl': sl, 'tp': tp, 'vol': (equity*0.01)/points, 'gear': 2}
                        state = 'IN_TRADE'
                    
        elif state == 'IN_TRADE':
            hit_exit = False
            exit_price = 0
            
            if trade['gear'] == 1:
                if trade['type'] == 'BUY' and c['low'] <= trade['sl']:
                    hit_exit, exit_price = True, trade['sl']
                elif trade['type'] == 'SELL' and c['high'] >= trade['sl']:
                    hit_exit, exit_price = True, trade['sl']
                    
                if not hit_exit:
                    if trade['type'] == 'BUY': trade['sl'] = max(trade['sl'], c['low'] - 1.5*atr[i])
                    else: trade['sl'] = min(trade['sl'], c['high'] + 1.5*atr[i])
            
            elif trade['gear'] == 2:
                if trade['type'] == 'BUY':
                    if c['low'] <= trade['sl']: hit_exit, exit_price = True, trade['sl']
                    elif c['high'] >= trade['tp']: hit_exit, exit_price = True, trade['tp']
                else:
                    if c['high'] >= trade['sl']: hit_exit, exit_price = True, trade['sl']
                    elif c['low'] <= trade['tp']: hit_exit, exit_price = True, trade['tp']

            if hit_exit:
                pnl = (exit_price - trade['entry']) * trade['vol'] if trade['type'] == 'BUY' else (trade['entry'] - exit_price) * trade['vol']
                equity += pnl
                if pnl > 0: win += 1
                else: loss += 1
                state = 'SEARCHING'
                
    return equity, win, loss

candles = fetch_historical_klines(limit=1500)
eq1, w1, l1 = run_backtest(candles, use_regime_filter=False, use_mean_reversion=False)
eq2, w2, l2 = run_backtest(candles, use_regime_filter=True, use_mean_reversion=False)
eq3, w3, l3 = run_backtest(candles, use_regime_filter=True, use_mean_reversion=True)

print("STANDARD GRIFF EDGE (No Filters):")
print(f"Equity: ${eq1:.2f} | Wins: {w1} | Losses: {l1}\n")
print("GRIFF EDGE + ADX FILTER (No Range Trading, Just Skip Chop):")
print(f"Equity: ${eq2:.2f} | Wins: {w2} | Losses: {l2}\n")
print("FULL REGIME ENGINE (Griff Breakout + Mean Reversion in Chop):")
print(f"Equity: ${eq3:.2f} | Wins: {w3} | Losses: {l3}\n")
