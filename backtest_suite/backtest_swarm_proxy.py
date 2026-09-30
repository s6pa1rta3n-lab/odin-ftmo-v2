import pandas as pd
import numpy as np
import pytz
from data_loader import load_data, resample_data

def run_swarm_proxy_backtest(df):
    print("Running Swarm Proxy (Asymmetric Swing) Backtest...")
    
    # Resample to Daily
    df_daily = resample_data(df, timeframe='1D')
    if len(df_daily) < 20:
        print("Not enough daily data for proxy.")
        return pd.DataFrame()
        
    df_daily['highest_20'] = df_daily['high'].rolling(20).max().shift(1)
    df_daily['lowest_20'] = df_daily['low'].rolling(20).min().shift(1)
    df_daily['ma_20'] = df_daily['close'].rolling(20).mean().shift(1)
    
    trades = []
    
    # Micro lot size adjustment (swing trades are 0.01 lots vs day trades at 9.5 lots)
    # The PnL should be scaled down. 1 point on US100 at 0.01 lot = $0.20
    # Wait, contract sizes differ. We'll just calculate points and scale it later if needed.
    # For now, let's keep it in points PnL.
    
    state = 'FLAT'
    entry_price = 0.0
    position = 0
    entry_date = None
    
    for row in df_daily.itertuples():
        if pd.isna(row.highest_20):
            continue
            
        if state == 'FLAT':
            if row.high > row.highest_20:
                position = 1
                entry_price = row.highest_20
                entry_date = row.Index.date()
                state = 'IN_TRADE'
            elif row.low < row.lowest_20:
                position = -1
                entry_price = row.lowest_20
                entry_date = row.Index.date()
                state = 'IN_TRADE'
                
        elif state == 'IN_TRADE':
            # Stop loss is the 20 SMA
            if position == 1:
                if row.low <= row.ma_20:
                    trade_pnl = (row.ma_20 - entry_price)
                    trades.append({'date': row.Index.date(), 'type': 'LONG_EXIT', 'pnl': trade_pnl})
                    state = 'FLAT'
            elif position == -1:
                if row.high >= row.ma_20:
                    trade_pnl = (entry_price - row.ma_20)
                    trades.append({'date': row.Index.date(), 'type': 'SHORT_EXIT', 'pnl': trade_pnl})
                    state = 'FLAT'
                    
    # Scale PnL to represent a smaller position size relative to day trades.
    # Let's say swing trades are 1/10th the risk
    trades_df = pd.DataFrame(trades)
    if len(trades_df) > 0:
        trades_df.set_index('date', inplace=True)
        trades_df['pnl'] = trades_df['pnl'] * 0.1 
        trades_df['cum_pnl'] = trades_df['pnl'].cumsum()
        print(f"Total Trades: {len(trades_df)}")
        print(f"Total PnL: {trades_df['pnl'].sum()}")
    else:
        print("No trades executed.")
        
    return trades_df

if __name__ == "__main__":
    df = load_data('/Users/solveetcoagula/Desktop/google_cloud/usatechidxusd-m1-bid-2026-08-01-2026-09-02.csv')
    res = run_swarm_proxy_backtest(df)
    if res is not None:
        print(res.tail())
