import pandas as pd
import numpy as np
import yfinance as yf
import warnings
warnings.filterwarnings('ignore')

def compute_atr_14(df):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    return true_range.rolling(14).mean()

def get_trades_for_symbol(symbol):
    data = yf.download(symbol, period='720d', interval='1h', progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)
    data = data.dropna()
    data['ATR'] = compute_atr_14(data)
    data = data.dropna()
    state = 'SEARCHING'
    active_direction = None
    entry_price = 0.0
    sl = 0.0
    initial_risk = 0.0
    pending_buy_price = None
    pending_sell_price = None
    pending_buy_sl = None
    pending_sell_sl = None
    trades = []
    
    for i in range(2, len(data)):
        prev_mother = data.iloc[i-2]
        prev_bar = data.iloc[i-1]
        current_bar = data.iloc[i]
        bar_time = data.index[i]
        atr = prev_bar['ATR']
        
        if state == 'IN_TRADE':
            if active_direction == 'BUY':
                if current_bar['Low'] <= sl:
                    r_multiple = (sl - entry_price) / initial_risk
                    trades.append({'time': bar_time, 'symbol': symbol, 'R': r_multiple})
                    state = 'SEARCHING'
                    continue
                else:
                    sl = max(sl, current_bar['Close'] - (1.5 * atr))
            elif active_direction == 'SELL':
                if current_bar['High'] >= sl:
                    r_multiple = (entry_price - sl) / initial_risk
                    trades.append({'time': bar_time, 'symbol': symbol, 'R': r_multiple})
                    state = 'SEARCHING'
                    continue
                else:
                    sl = min(sl, current_bar['Close'] + (1.5 * atr))
                    
        elif state == 'PENDING':
            triggered = False
            if current_bar['High'] > pending_buy_price:
                active_direction = 'BUY'
                entry_price = pending_buy_price
                sl = pending_buy_sl
                initial_risk = entry_price - sl
                state = 'IN_TRADE'
                triggered = True
            elif current_bar['Low'] < pending_sell_price:
                active_direction = 'SELL'
                entry_price = pending_sell_price
                sl = pending_sell_sl
                initial_risk = sl - entry_price
                state = 'IN_TRADE'
                triggered = True
            if not triggered:
                state = 'SEARCHING'
                
        if state == 'SEARCHING':
            if prev_bar['High'] < prev_mother['High'] and prev_bar['Low'] > prev_mother['Low']:
                pending_buy_price = prev_bar['High']
                pending_sell_price = prev_bar['Low']
                pending_buy_sl = prev_bar['High'] - (1.5 * atr)
                pending_sell_sl = prev_bar['Low'] + (1.5 * atr)
                state = 'PENDING'
    return trades

trades_nq = get_trades_for_symbol("NQ=F")
trades_gc = get_trades_for_symbol("GC=F")
trades_btc = get_trades_for_symbol("BTC-USD")

all_trades = trades_nq + trades_gc + trades_btc
df = pd.DataFrame(all_trades)
df['date'] = pd.to_datetime(df["time"], utc=True).dt.date

daily_r = df.groupby('date')['R'].sum()
worst_day_1pct = daily_r.min()
days_below_5R = len(daily_r[daily_r <= -5.0])

def apply_dynamic_risk(row):
    if row['symbol'] == 'NQ=F': return row['R'] * 0.65
    if row['symbol'] == 'GC=F': return row['R'] * 0.00
    if row['symbol'] == 'BTC-USD': return row['R'] * 0.80
    return row['R']

df['dynamic_pct'] = df.apply(apply_dynamic_risk, axis=1)
daily_dyn = df.groupby('date')['dynamic_pct'].sum()
worst_day_dyn = daily_dyn.min()
days_below_5pct_dyn = len(daily_dyn[daily_dyn <= -5.0])

print(f"--- 1.0% FLAT RISK REGIME ---")
print(f"Worst Calendar Day Loss: {worst_day_1pct:.2f} R (-{abs(worst_day_1pct):.2f}%)")
print(f"Number of Days breaching -5.0% limit: {days_below_5R}")

print(f"\n--- NEW DYNAMIC SIZING MATRIX ---")
print(f"Worst Calendar Day Loss: {worst_day_dyn:.2f}%")
print(f"Number of Days breaching -5.0% limit: {days_below_5pct_dyn}")

