import yfinance as yf
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

def compute_atr_14(df):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    return true_range.rolling(14).mean()

def run_backtest(symbol):
    print(f"--- Running 1H Backtest for {symbol} (Last 720 days) ---")
    data = yf.download(symbol, period='720d', interval='1h', progress=False)
    
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)
        
    data = data.dropna()
    if len(data) == 0:
        print(f"No data for {symbol}.")
        return

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
    
    # Iterate through bars
    for i in range(2, len(data)):
        prev_mother = data.iloc[i-2]
        prev_bar = data.iloc[i-1]
        current_bar = data.iloc[i]
        
        atr = prev_bar['ATR']
        
        if state == 'IN_TRADE':
            if active_direction == 'BUY':
                if current_bar['Low'] <= sl:
                    # Stopped out at SL
                    r_multiple = (sl - entry_price) / initial_risk
                    trades.append(r_multiple)
                    state = 'SEARCHING'
                    continue
                else:
                    candidate_sl = current_bar['Close'] - (1.5 * atr)
                    sl = max(sl, candidate_sl)
                    
            elif active_direction == 'SELL':
                if current_bar['High'] >= sl:
                    # Stopped out at SL
                    r_multiple = (entry_price - sl) / initial_risk
                    trades.append(r_multiple)
                    state = 'SEARCHING'
                    continue
                else:
                    candidate_sl = current_bar['Close'] + (1.5 * atr)
                    sl = min(sl, candidate_sl)
                    
        elif state == 'PENDING':
            triggered = False
            # To be more realistic, check which one triggered first? 
            # In 1H bars we don't know intra-bar, we'll assume buy triggers if high breaks.
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
            # Check for inside bar on the PREVIOUS bar
            if prev_bar['High'] < prev_mother['High'] and prev_bar['Low'] > prev_mother['Low']:
                pending_buy_price = prev_bar['High']
                pending_sell_price = prev_bar['Low']
                pending_buy_sl = prev_bar['High'] - (1.5 * atr)
                pending_sell_sl = prev_bar['Low'] + (1.5 * atr)
                state = 'PENDING'

    if len(trades) > 0:
        trades_np = np.array(trades)
        wins = trades_np[trades_np > 0]
        losses = trades_np[trades_np <= 0]
        win_rate = len(wins) / len(trades)
        print(f"Total Trades: {len(trades)}")
        print(f"Win Rate: {win_rate:.2%}")
        print(f"Total Return (in R): {sum(trades):.2f} R")
        if len(wins) > 0 and len(losses) > 0:
            print(f"Avg Win: {np.mean(wins):.2f} R | Avg Loss: {np.mean(losses):.2f} R")
        print(f"Expectancy: {np.mean(trades):.2f} R per trade")
        
        # Calculate max drawdown in R
        cum_r = np.cumsum(trades_np)
        peak = np.maximum.accumulate(cum_r)
        drawdown = cum_r - peak
        print(f"Max Drawdown (in R): {np.min(drawdown):.2f} R\n")

run_backtest("NQ=F")
run_backtest("GC=F")
run_backtest("BTC-USD")
