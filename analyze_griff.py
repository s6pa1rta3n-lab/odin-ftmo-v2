import pandas as pd
try:
    df = pd.read_csv('griff_trades.csv')
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['date'] = df['datetime'].dt.date
    daily_pnl = df.groupby('date')['pnl'].sum()
    
    print('GRIFF STRATEGY BACKTEST METRICS:')
    print(f'Total Trades: {len(df)}')
    print(f'Average PnL per Trade: ${df["pnl"].mean():.2f}')
    print(f'Average Daily PnL (active trading days): ${daily_pnl.mean():.2f}')
    print(f'Max Daily Profit: ${daily_pnl.max():.2f}')
    print(f'Max Daily Loss: ${daily_pnl.min():.2f}')
    
    wins = df[df['pnl'] > 0]
    losses = df[df['pnl'] <= 0]
    
    print(f'Average Win: ${wins["pnl"].mean():.2f}')
    print(f'Average Loss: ${losses["pnl"].mean():.2f}')
    print(f'Win Rate: {(len(wins)/len(df))*100:.1f}%')
except Exception as e:
    print('Error:', e)
