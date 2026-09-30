import pandas as pd
import numpy as np
from data_loader import load_data, resample_data
from metrics_calculator import calculate_and_report_metrics

def run_griff_backtest(df):
    print("Running Griff 1H Inside Bar ATR Backtest...")
    
    df_ny = df.copy()
    df_ny.index = df_ny.index.tz_convert('America/New_York')
    
    # Resample to 1H
    df_1h = resample_data(df_ny, '1h')
    
    # Calculate 14-period ATR
    df_1h['prev_close'] = df_1h['close'].shift(1)
    df_1h['tr1'] = df_1h['high'] - df_1h['low']
    df_1h['tr2'] = (df_1h['high'] - df_1h['prev_close']).abs()
    df_1h['tr3'] = (df_1h['low'] - df_1h['prev_close']).abs()
    df_1h['tr'] = df_1h[['tr1', 'tr2', 'tr3']].max(axis=1)
    df_1h['atr_14'] = df_1h['tr'].rolling(14).mean()
    
    # Identify Inside Bars
    df_1h['prev_high'] = df_1h['high'].shift(1)
    df_1h['prev_low'] = df_1h['low'].shift(1)
    df_1h['inside_bar'] = (df_1h['high'] < df_1h['prev_high']) & (df_1h['low'] > df_1h['prev_low'])
    
    trades = []
    
    state = 'SEARCHING'
    entry_price = 0.0
    position = 0
    atr_at_entry = 0.0
    stop_loss = 0.0
    sl_points = 0.0
    
    for i in range(15, len(df_1h)):
        row = df_1h.iloc[i]
        prev_row = df_1h.iloc[i-1]
        
        if state == 'SEARCHING':
            if prev_row['inside_bar']:
                # Breakout of the inside bar
                atr_val = prev_row['atr_14']
                if pd.isna(atr_val) or atr_val == 0:
                    continue
                    
                if row['high'] > prev_row['high']:
                    position = 1
                    entry_price = prev_row['high']
                    atr_at_entry = atr_val
                    stop_loss = entry_price - (atr_at_entry * 1.5)
                    sl_points = entry_price - stop_loss
                    state = 'IN_TRADE'
                elif row['low'] < prev_row['low']:
                    position = -1
                    entry_price = prev_row['low']
                    atr_at_entry = atr_val
                    stop_loss = entry_price + (atr_at_entry * 1.5)
                    sl_points = stop_loss - entry_price
                    state = 'IN_TRADE'
                    
        elif state == 'IN_TRADE':
            trade_pnl_pts = 0.0
            closed = False
            
            # Simple fixed points logic using point equivalent of $
            # Sizing: 1% risk = $1000. 
            # Lots * ContractSize * sl_points = 1000 => $ per point = 1000 / sl_points
            dollars_per_point = 1000.0 / sl_points if sl_points > 0 else 0
            
            if position == 1:
                if row['low'] <= stop_loss:
                    trade_pnl_pts = stop_loss - entry_price
                    closed = True
                else:
                    # Trail stop logic: previous close - 1.5 ATR
                    new_sl = row['close'] - (row['atr_14'] * 1.5)
                    if new_sl > stop_loss:
                        stop_loss = new_sl
            elif position == -1:
                if row['high'] >= stop_loss:
                    trade_pnl_pts = entry_price - stop_loss
                    closed = True
                else:
                    new_sl = row['close'] + (row['atr_14'] * 1.5)
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

    calculate_and_report_metrics(trades, start_balance=100000.0, risk_per_trade=1000.0, output_csv="griff_trades.csv")

if __name__ == "__main__":
    df = load_data('/Users/solveetcoagula/Desktop/google_cloud/usatechidxusd-m1-bid-2026-08-01-2026-09-02.csv')
    run_griff_backtest(df)
