import pandas as pd
import numpy as np
from data_loader import load_data, resample_data
from metrics_calculator import calculate_and_report_metrics

def run_breakout_backtest(df):
    print("Running London Breakout Backtest...")
    
    # Keep UTC since London open is easily defined in UTC
    df_utc = df.copy()
    
    # 5m timeframe
    df_5m = resample_data(df_utc, '5min')
    
    days = np.unique(df_5m.index.date)
    trades = []
    
    for day in days:
        day_data = df_5m[df_5m.index.date == day]
        
        # London Range: 07:00 to 10:00 UTC
        london_data = day_data.between_time('07:00', '09:55')
        if len(london_data) == 0:
            continue
            
        london_high = london_data['high'].max()
        london_low = london_data['low'].min()
        
        # Trade Session: 10:00 to 16:00 UTC
        trade_data = day_data.between_time('10:00', '16:00')
        
        state = 'WAITING_BREAKOUT'
        entry_price = 0.0
        position = 0
        stop_loss = 0.0
        sl_points = 0.0
        
        for row in trade_data.itertuples():
            if state == 'WAITING_BREAKOUT':
                if row.high > london_high:
                    state = 'WAITING_RETEST_LONG'
                elif row.low < london_low:
                    state = 'WAITING_RETEST_SHORT'
                    
            elif state == 'WAITING_RETEST_LONG':
                if row.low <= london_high:
                    entry_price = london_high
                    position = 1
                    stop_loss = london_low
                    sl_points = entry_price - stop_loss
                    state = 'IN_TRADE'
                    
            elif state == 'WAITING_RETEST_SHORT':
                if row.high >= london_low:
                    entry_price = london_low
                    position = -1
                    stop_loss = london_high
                    sl_points = stop_loss - entry_price
                    state = 'IN_TRADE'
                    
            elif state == 'IN_TRADE':
                dollars_per_point = 1000.0 / sl_points if sl_points > 0 else 0
                tp_points = sl_points * 1.5 # 1:1.5 R:R
                
                trade_pnl_pts = 0.0
                closed = False
                
                if position == 1:
                    if row.low <= stop_loss:
                        trade_pnl_pts = stop_loss - entry_price
                        closed = True
                    elif row.high >= entry_price + tp_points:
                        trade_pnl_pts = tp_points
                        closed = True
                elif position == -1:
                    if row.high >= stop_loss:
                        trade_pnl_pts = entry_price - stop_loss
                        closed = True
                    elif row.low <= entry_price - tp_points:
                        trade_pnl_pts = tp_points
                        closed = True
                        
                if closed:
                    trade_pnl_usd = trade_pnl_pts * dollars_per_point
                    trades.append({
                        'date': row.Index,
                        'type': 'LONG' if position == 1 else 'SHORT',
                        'pnl': trade_pnl_usd
                    })
                    break

    calculate_and_report_metrics(trades, start_balance=100000.0, risk_per_trade=1000.0, output_csv="breakout_trades.csv")

if __name__ == "__main__":
    df = load_data('/Users/solveetcoagula/Desktop/google_cloud/usatechidxusd-m1-bid-2026-08-01-2026-09-02.csv')
    run_breakout_backtest(df)
