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
                    trades.append({'R': r_multiple})
                    state = 'SEARCHING'
                    continue
                else:
                    sl = max(sl, current_bar['Close'] - (1.5 * atr))
            elif active_direction == 'SELL':
                if current_bar['High'] >= sl:
                    r_multiple = (entry_price - sl) / initial_risk
                    trades.append({'R': r_multiple})
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
r_array = [t['R'] for t in all_trades]

# 1-Month Monte Carlo
SIMULATIONS = 10000
FAIL_THRESHOLD = -10.0
# 2580 trades over 24 months = 107.5 trades per month
TRADES_PER_MONTH = 108

failed = 0
for _ in range(SIMULATIONS):
    sampled = np.random.choice(r_array, size=TRADES_PER_MONTH, replace=True)
    cum = np.cumsum(sampled)
    peaks = np.maximum.accumulate(cum)
    dd = cum - peaks
    if np.min(dd) <= FAIL_THRESHOLD:
        failed += 1

print(f"1-Month Probability of Ruin (-10R): {(failed / SIMULATIONS)*100:.2f}%")

# Asset specific metrics for Kelly/Dynamic Sizing
def calc_metrics(trades, name):
    arr = [t['R'] for t in trades]
    win_rate = len([x for x in arr if x > 0]) / len(arr)
    avg_win = np.mean([x for x in arr if x > 0])
    avg_loss = np.abs(np.mean([x for x in arr if x < 0]))
    payoff_ratio = avg_win / avg_loss if avg_loss != 0 else 0
    kelly = win_rate - ((1 - win_rate) / payoff_ratio) if payoff_ratio != 0 else 0
    cum = np.cumsum(arr)
    peaks = np.maximum.accumulate(cum)
    max_dd = np.min(cum - peaks)
    print(f"{name} | Win Rate: {win_rate:.2%} | Payoff: {payoff_ratio:.2f} | Max DD: {max_dd:.2f}R | Half-Kelly: {kelly/2:.2%}")

calc_metrics(trades_nq, "US100")
calc_metrics(trades_gc, "Gold")
calc_metrics(trades_btc, "BTC")

