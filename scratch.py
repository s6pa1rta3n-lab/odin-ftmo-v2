import pandas as pd
df = pd.read_csv('griff_trades.csv')
df['date'] = pd.to_datetime(df['date'])
df['day'] = df['date'].dt.date

daily_start_equity = 100000.0
max_daily_dd_usd = 0.0
max_daily_dd_pct = 0.0
worst_day = None

for date, group in df.groupby('day'):
    min_equity_today = group['equity'].min()
    dd_usd = daily_start_equity - min_equity_today
    if dd_usd > 0:
        dd_pct = (dd_usd / daily_start_equity) * 100
        if dd_pct > max_daily_dd_pct:
            max_daily_dd_pct = dd_pct
            max_daily_dd_usd = dd_usd
            worst_day = date
            
    daily_start_equity = group['equity'].iloc[-1]

print(f"Max Daily DD (closed trades): ${max_daily_dd_usd:.2f} ({max_daily_dd_pct:.2f}%) on {worst_day}")
