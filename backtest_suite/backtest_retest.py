import pandas as pd
import numpy as np
import pytz
from data_loader import load_data

def run_retest_backtest(df):
    print("Running Retest Backtest...")
    
    # Convert index to NY time for consistent US Open hours
    df_ny = df.copy()
    df_ny.index = df_ny.index.tz_convert('America/New_York')
    
    # We will iterate through each day
    days = np.unique(df_ny.index.date)
    
    trades = []
    pnl = 0.0
    
    # Parameters
    commission = 3.0
    slippage = 1.0 # 1 point
    
    for day in days:
        day_data = df_ny[df_ny.index.date == day]
        
        # ORB Range: 9:30 AM to 9:55 AM
        orb_data = day_data.between_time('09:30', '09:54')
        if len(orb_data) == 0:
            continue
            
        orb_high = orb_data['high'].max()
        orb_low = orb_data['low'].min()
        
        # Trade Session: 9:55 AM to 4:00 PM
        trade_data = day_data.between_time('09:55', '16:00')
        
        state = 'WAITING_BREAKOUT'
        entry_price = 0.0
        position = 0 # 1 for long, -1 for short
        
        for row in trade_data.itertuples():
            if state == 'WAITING_BREAKOUT':
                # Check if it breaks out
                if row.high > orb_high:
                    state = 'WAITING_RETEST_LONG'
                elif row.low < orb_low:
                    state = 'WAITING_RETEST_SHORT'
            
            elif state == 'WAITING_RETEST_LONG':
                if row.low <= orb_high:
                    # Retest occurred! Buy at ORB High
                    entry_price = orb_high
                    position = 1
                    state = 'IN_TRADE'
            
            elif state == 'WAITING_RETEST_SHORT':
                if row.high >= orb_low:
                    # Retest occurred! Short at ORB Low
                    entry_price = orb_low
                    position = -1
                    state = 'IN_TRADE'
            
            elif state == 'IN_TRADE':
                # Simple exit logic: 
                # Stop Loss = 20 points
                # Take Profit = 40 points
                sl_points = 20
                tp_points = 40
                
                if position == 1:
                    if row.low <= entry_price - sl_points:
                        trade_pnl = -sl_points - slippage - commission
                        trades.append({'date': day, 'type': 'LONG_SL', 'pnl': trade_pnl})
                        break
                    elif row.high >= entry_price + tp_points:
                        trade_pnl = tp_points - slippage - commission
                        trades.append({'date': day, 'type': 'LONG_TP', 'pnl': trade_pnl})
                        break
                elif position == -1:
                    if row.high >= entry_price + sl_points:
                        trade_pnl = -sl_points - slippage - commission
                        trades.append({'date': day, 'type': 'SHORT_SL', 'pnl': trade_pnl})
                        break
                    elif row.low <= entry_price - tp_points:
                        trade_pnl = tp_points - slippage - commission
                        trades.append({'date': day, 'type': 'SHORT_TP', 'pnl': trade_pnl})
                        break
        
        # End of day exit if still in trade
        if state == 'IN_TRADE':
            exit_price = trade_data.iloc[-1]['close']
            trade_pnl = (exit_price - entry_price) * position - slippage - commission
            trades.append({'date': day, 'type': 'EOD', 'pnl': trade_pnl})

    
    trades_df = pd.DataFrame(trades)
    if len(trades_df) > 0:
        trades_df.set_index('date', inplace=True)
        trades_df['cum_pnl'] = trades_df['pnl'].cumsum()
        print(f"Total Trades: {len(trades_df)}")
        print(f"Total PnL: {trades_df['pnl'].sum()}")
    else:
        print("No trades executed.")
        
    return trades_df

if __name__ == "__main__":
    df = load_data('/Users/solveetcoagula/Desktop/google_cloud/usatechidxusd-m1-bid-2026-08-01-2026-09-02.csv')
    res = run_retest_backtest(df)
    if res is not None:
        print(res.tail())
