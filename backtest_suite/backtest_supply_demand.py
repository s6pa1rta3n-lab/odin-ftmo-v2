import pandas as pd
import numpy as np
from data_loader import load_data, resample_data
from metrics_calculator import calculate_and_report_metrics

def run_supply_demand_backtest(df):
    print("Running Supply/Demand Backtest...")
    
    df_ny = df.copy()
    df_ny.index = df_ny.index.tz_convert('America/New_York')
    
    # 5m timeframe
    df_5m = resample_data(df_ny, '5min')
    df_5m['ema_200'] = df_5m['close'].ewm(span=200, adjust=False).mean()
    
    trades = []
    
    state = 'SEARCHING'
    position = 0
    entry_price = 0.0
    stop_loss = 0.0
    sl_points = 0.0
    
    zone_top = 0.0
    zone_bottom = 0.0
    
    for i in range(10, len(df_5m)):
        row = df_5m.iloc[i]
        
        if state == 'SEARCHING':
            # Simple momentum thrust to create "demand"
            if row['close'] > df_5m.iloc[i-3]['high'] + 20 and row['close'] > row['ema_200']:
                zone_top = df_5m.iloc[i-3]['high']
                zone_bottom = df_5m.iloc[i-3]['low']
                state = 'WAITING_DEMAND_PULLBACK'
                
            # Momentum drop to create "supply"
            elif row['close'] < df_5m.iloc[i-3]['low'] - 20 and row['close'] < row['ema_200']:
                zone_bottom = df_5m.iloc[i-3]['low']
                zone_top = df_5m.iloc[i-3]['high']
                state = 'WAITING_SUPPLY_PULLBACK'
                
        elif state == 'WAITING_DEMAND_PULLBACK':
            if row['low'] <= zone_top:
                position = 1
                entry_price = zone_top
                stop_loss = zone_bottom - 5.0
                sl_points = entry_price - stop_loss
                state = 'IN_TRADE'
            elif row['close'] > zone_top + 100:
                state = 'SEARCHING'
                
        elif state == 'WAITING_SUPPLY_PULLBACK':
            if row['high'] >= zone_bottom:
                position = -1
                entry_price = zone_bottom
                stop_loss = zone_top + 5.0
                sl_points = stop_loss - entry_price
                state = 'IN_TRADE'
            elif row['close'] < zone_bottom - 100:
                state = 'SEARCHING'
                
        elif state == 'IN_TRADE':
            dollars_per_point = 1000.0 / sl_points if sl_points > 0 else 0
            
            trade_pnl_pts = 0.0
            closed = False
            
            if position == 1:
                if row['low'] <= stop_loss:
                    trade_pnl_pts = stop_loss - entry_price
                    closed = True
                else:
                    new_sl = row['close'] - sl_points # Trail 1R
                    if new_sl > stop_loss:
                        stop_loss = new_sl
            elif position == -1:
                if row['high'] >= stop_loss:
                    trade_pnl_pts = entry_price - stop_loss
                    closed = True
                else:
                    new_sl = row['close'] + sl_points
                    if new_sl < stop_loss:
                        stop_loss = new_sl
                        
            if closed:
                trade_pnl_usd = trade_pnl_pts * dollars_per_point
                trades.append({
                    'date': row.name,
                    'type': 'LONG' if position == 1 else 'SHORT',
                    'pnl': trade_pnl_usd
                })
                state = 'SEARCHING'

    calculate_and_report_metrics(trades, start_balance=100000.0, risk_per_trade=1000.0, output_csv="supply_demand_trades.csv")

if __name__ == "__main__":
    df = load_data('/Users/solveetcoagula/Desktop/google_cloud/usatechidxusd-m1-bid-2026-08-01-2026-09-02.csv')
    run_supply_demand_backtest(df)
