import yfinance as yf
import pandas as pd
import pytz

def analyze_trade(ticker, entry_time_utc, high, low, atr, sizing):
    print(f"\nAnalyzing {ticker} setup from {entry_time_utc}...")
    df = yf.download(ticker, period='1d', interval='1m', progress=False)
    
    # Flatten MultiIndex columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    if df.index.tz is None:
        df.index = df.index.tz_localize('America/New_York').tz_convert('UTC')
    else:
        df.index = df.index.tz_convert('UTC')
        
    start_time = pd.Timestamp(entry_time_utc).tz_localize('UTC')
    df_future = df[df.index >= start_time]
    
    if df_future.empty:
        print("No data available yet.")
        return
        
    position = None
    entry_price = 0
    sl = 0
    highest_pnl = 0
    
    sl_dist = 1.5 * atr
    
    # FTMO uses $20 per point for US100.
    # NQ=F uses standard Nasdaq 100 points, let's treat the sizing multiplier here.
    # The 'sizing' output by Griff for US100 is in lots (contract size 20).
    # Oh wait, my script does `pnl_points * sizing`. The 'sizing' logged by Griff is lots.
    # Griff US100 tick value is $20. So 1 lot = $20 per point. 
    # Let's adjust multiplier if it's NQ=F.
    multiplier = 20 if ticker == 'NQ=F' else 1
    
    for idx, row in df_future.iterrows():
        r_high = float(row['High'])
        r_low = float(row['Low'])
        r_close = float(row['Close'])
        
        if position is None:
            if r_high > high:
                position = 'LONG'
                entry_price = high
                sl = entry_price - sl_dist
                print(f"[{idx}] TRIGGERED LONG at {entry_price:.2f}. Initial SL: {sl:.2f}")
            elif r_low < low:
                position = 'SHORT'
                entry_price = low
                sl = entry_price + sl_dist
                print(f"[{idx}] TRIGGERED SHORT at {entry_price:.2f}. Initial SL: {sl:.2f}")
        else:
            if position == 'LONG':
                if r_low < sl:
                    exit_price = sl
                    pnl_points = exit_price - entry_price
                    pnl_dollars = pnl_points * sizing * multiplier
                    print(f"[{idx}] STOP LOSS HIT at {exit_price:.2f}. PNL: ${pnl_dollars:.2f}")
                    return
                curr_pnl_pts = r_close - entry_price
                curr_pnl = curr_pnl_pts * sizing * multiplier
                if curr_pnl > highest_pnl: highest_pnl = curr_pnl
            elif position == 'SHORT':
                if r_high > sl:
                    exit_price = sl
                    pnl_points = entry_price - exit_price
                    pnl_dollars = pnl_points * sizing * multiplier
                    print(f"[{idx}] STOP LOSS HIT at {exit_price:.2f}. PNL: ${pnl_dollars:.2f}")
                    return
                curr_pnl_pts = entry_price - r_close
                curr_pnl = curr_pnl_pts * sizing * multiplier
                if curr_pnl > highest_pnl: highest_pnl = curr_pnl
                
    if position:
        last_row = df_future.iloc[-1]
        r_close = float(last_row['Close'])
        if position == 'LONG':
            floating_pnl_pts = r_close - entry_price
        else:
            floating_pnl_pts = entry_price - r_close
            
        floating_pnl = floating_pnl_pts * sizing * multiplier
        print(f"[CURRENT] FLOATING {position} at {r_close:.2f}. Floating PNL: ${floating_pnl:.2f}. Peak PNL was: ${highest_pnl:.2f}")
    else:
        print("Never triggered.")

# US100 Setup at 21:00 UTC
analyze_trade('NQ=F', '2026-09-22 21:00:00', 30733.64, 30693.74, 76.91, 6.20)

# BTCUSD Setup at 22:00 UTC
analyze_trade('BTC-USD', '2026-09-22 22:00:00', 86289.00, 86129.52, 544.67, 1.08)

