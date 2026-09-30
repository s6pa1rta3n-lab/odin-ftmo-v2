import pandas as pd
import numpy as np
import pytz
from data_loader import load_data

def run_vwap_backtest(df):
    print("Running VWAP (TWAP Proxy) Backtest...")
    
    df_ny = df.copy()
    df_ny.index = df_ny.index.tz_convert('America/New_York')
    
    days = np.unique(df_ny.index.date)
    trades = []
    
    commission = 3.0
    slippage = 1.0 
    
    for day in days:
        day_data = df_ny[df_ny.index.date == day]
        # Only trade during US Session
        session = day_data.between_time('09:30', '15:50').copy()
        if len(session) < 30:
            continue
            
        session['typical'] = (session['high'] + session['low'] + session['close']) / 3.0
        session['twap'] = session['typical'].expanding().mean()
        session['std'] = session['typical'].expanding().std()
        
        session['upper_band'] = session['twap'] + (2.0 * session['std'])
        session['lower_band'] = session['twap'] - (2.0 * session['std'])
        
        state = 'FLAT'
        entry_price = 0.0
        position = 0
        
        for row in session.itertuples():
            if pd.isna(row.twap) or pd.isna(row.std):
                continue
                
            if state == 'FLAT':
                # Reversal from bands
                if row.high >= row.upper_band:
                    position = -1
                    entry_price = row.upper_band
                    state = 'IN_TRADE'
                elif row.low <= row.lower_band:
                    position = 1
                    entry_price = row.lower_band
                    state = 'IN_TRADE'
                    
            elif state == 'IN_TRADE':
                # Exit at TWAP (Mean reversion target) or fixed stop loss
                sl_points = 30
                if position == 1:
                    if row.high >= row.twap:
                        trade_pnl = (row.twap - entry_price) - slippage - commission
                        trades.append({'date': day, 'type': 'LONG_TP', 'pnl': trade_pnl})
                        state = 'FLAT'
                    elif row.low <= entry_price - sl_points:
                        trade_pnl = -sl_points - slippage - commission
                        trades.append({'date': day, 'type': 'LONG_SL', 'pnl': trade_pnl})
                        state = 'FLAT'
                elif position == -1:
                    if row.low <= row.twap:
                        trade_pnl = (entry_price - row.twap) - slippage - commission
                        trades.append({'date': day, 'type': 'SHORT_TP', 'pnl': trade_pnl})
                        state = 'FLAT'
                    elif row.high >= entry_price + sl_points:
                        trade_pnl = -sl_points - slippage - commission
                        trades.append({'date': day, 'type': 'SHORT_SL', 'pnl': trade_pnl})
                        state = 'FLAT'
                        
        if state == 'IN_TRADE':
            exit_price = session.iloc[-1]['close']
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
    res = run_vwap_backtest(df)
    if res is not None:
        print(res.tail())
