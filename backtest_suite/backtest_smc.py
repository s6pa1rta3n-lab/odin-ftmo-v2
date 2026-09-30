import pandas as pd
import numpy as np
from data_loader import load_data, resample_data
from metrics_calculator import calculate_and_report_metrics

def run_smc_backtest(df):
    print("Running SMC / FVG Backtest...")
    
    df_ny = df.copy()
    df_ny.index = df_ny.index.tz_convert('America/New_York')
    
    # Resample to 15m for FVG
    df_15m = resample_data(df_ny, '15min')
    
    trades = []
    
    state = 'SEARCHING'
    fvg_top = 0.0
    fvg_bottom = 0.0
    position = 0
    entry_price = 0.0
    stop_loss = 0.0
    sl_points = 0.0
    
    for i in range(3, len(df_15m)):
        row = df_15m.iloc[i]
        c3 = df_15m.iloc[i-1]
        c2 = df_15m.iloc[i-2]
        c1 = df_15m.iloc[i-3]
        
        if state == 'SEARCHING':
            # Bullish FVG: C1 high < C3 low
            if c1['high'] < c3['low'] and c2['close'] > c2['open']:
                fvg_bottom = c1['high']
                fvg_top = c3['low']
                state = 'WAITING_RETRACEMENT_LONG'
                
            # Bearish FVG: C1 low > C3 high
            elif c1['low'] > c3['high'] and c2['close'] < c2['open']:
                fvg_top = c1['low']
                fvg_bottom = c3['high']
                state = 'WAITING_RETRACEMENT_SHORT'
                
        elif state == 'WAITING_RETRACEMENT_LONG':
            if row['low'] <= fvg_top:
                position = 1
                entry_price = fvg_top
                stop_loss = fvg_bottom - 5.0 # buffer
                sl_points = entry_price - stop_loss
                state = 'IN_TRADE'
            # Invalidate if price goes way above without retracing
            elif row['close'] > fvg_top + 50:
                state = 'SEARCHING'
                
        elif state == 'WAITING_RETRACEMENT_SHORT':
            if row['high'] >= fvg_bottom:
                position = -1
                entry_price = fvg_bottom
                stop_loss = fvg_top + 5.0
                sl_points = stop_loss - entry_price
                state = 'IN_TRADE'
            elif row['close'] < fvg_bottom - 50:
                state = 'SEARCHING'
                
        elif state == 'IN_TRADE':
            # Risk 1% = $1000
            dollars_per_point = 1000.0 / sl_points if sl_points > 0 else 0
            tp_points = sl_points * 2.5 # 1:2.5 R:R
            
            trade_pnl_pts = 0.0
            closed = False
            
            if position == 1:
                if row['low'] <= stop_loss:
                    trade_pnl_pts = stop_loss - entry_price
                    closed = True
                elif row['high'] >= entry_price + tp_points:
                    trade_pnl_pts = tp_points
                    closed = True
            elif position == -1:
                if row['high'] >= stop_loss:
                    trade_pnl_pts = entry_price - stop_loss
                    closed = True
                elif row['low'] <= entry_price - tp_points:
                    trade_pnl_pts = tp_points
                    closed = True
                    
            if closed:
                trade_pnl_usd = trade_pnl_pts * dollars_per_point
                trades.append({
                    'date': row.name,
                    'type': 'LONG' if position == 1 else 'SHORT',
                    'pnl': trade_pnl_usd
                })
                state = 'SEARCHING'

    calculate_and_report_metrics(trades, start_balance=100000.0, risk_per_trade=1000.0, output_csv="smc_trades.csv")

if __name__ == "__main__":
    df = load_data('/Users/solveetcoagula/Desktop/google_cloud/usatechidxusd-m1-bid-2026-08-01-2026-09-02.csv')
    run_smc_backtest(df)
