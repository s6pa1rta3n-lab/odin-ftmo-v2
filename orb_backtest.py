import yfinance as yf
import pandas as pd
import numpy as np

print("Downloading last 60 days of 5-minute NQ=F data...")
data = yf.download("NQ=F", period="60d", interval="5m", progress=False)
data.index = pd.to_datetime(data.index, utc=True)

dates = np.unique(data.index.date)

results_30 = []
results_60 = []

for date in dates:
    day_data = data[data.index.date == date]
    us_session = day_data[(day_data.index.hour >= 13) & (day_data.index.hour < 21)]
    if us_session.empty: continue
    
    # 30-Min ORB (13:30 to 14:00 UTC)
    orb_30 = day_data[(day_data.index.hour == 13) & (day_data.index.minute >= 30)]
    if orb_30.empty: continue
    high_30 = orb_30['High'].max()
    low_30 = orb_30['Low'].min()
    
    # 60-Min ORB (13:30 to 14:30 UTC)
    orb_60 = day_data[((day_data.index.hour == 13) & (day_data.index.minute >= 30)) | ((day_data.index.hour == 14) & (day_data.index.minute < 30))]
    if orb_60.empty: continue
    high_60 = orb_60['High'].max()
    low_60 = orb_60['Low'].min()
    
    # Trade execution (after ORB window)
    post_30 = day_data[(day_data.index.hour >= 14)]
    post_60 = day_data[(day_data.index.hour > 14) | ((day_data.index.hour == 14) & (day_data.index.minute >= 30))]
    
    def simulate(post_data, high, low):
        if post_data.empty: return 0
        for idx, row in post_data.iterrows():
            if row['High'] > high:
                # Triggered long
                return (post_data['High'].max() - high)
            if row['Low'] < low:
                # Triggered short
                return (low - post_data['Low'].min())
        return 0
        
    pts_30 = simulate(post_30, float(high_30), float(low_30))
    pts_60 = simulate(post_60, float(high_60), float(low_60))
    
    results_30.append(pts_30)
    results_60.append(pts_60)

print(f"--- RECENT 60-DAY BACKTEST (5m candles) ---")
print(f"30-Min ORB (10:00 AM) Average Max Excursion: {np.mean(results_30):.2f} pts")
print(f"60-Min ORB (10:30 AM) Average Max Excursion: {np.mean(results_60):.2f} pts")
