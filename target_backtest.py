import yfinance as yf
import pandas as pd
import numpy as np

logging = __import__('logging')
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

nq = yf.download('NQ=F', period='720d', interval='1h', progress=False)
vix = yf.download('^VIX', period='720d', interval='1d', progress=False)

nq.index = pd.to_datetime(nq.index, utc=True)
vix.index = pd.to_datetime(vix.index, utc=True)

dates = np.unique(nq.index.date)
win_excursions = []

for date in dates:
    day_data = nq[nq.index.date == date]
    us = day_data[(day_data.index.hour >= 13) & (day_data.index.hour < 21)]
    
    if us.empty: continue
        
    vix_prev_day = date - pd.Timedelta(days=1)
    available_vix_dates = vix.index[vix.index.date <= vix_prev_day]
    if len(available_vix_dates) == 0: continue
    
    vix_val = vix.loc[available_vix_dates[-1], 'Close']
    if isinstance(vix_val, pd.Series): vix_val = float(vix_val.iloc[0])
    else: vix_val = float(vix_val)
        
    us_open = float(us['Open'].iloc[0])
    us_high = float(us['High'].max())
    us_low = float(us['Low'].min())
    
    us_win = (us_high > us_open + 80) or (us_low < us_open - 80)
    
    if us_win and vix_val >= 15:
        max_up = us_high - us_open
        max_down = us_open - us_low
        excursion = max(max_up, max_down)
        win_excursions.append(excursion)

print(f"Total Trend Days Analyzed (VIX >= 15): {len(win_excursions)}")
print(f"Average Max Excursion on Trend Days: {np.mean(win_excursions):.2f} points")
print(f"Median Max Excursion on Trend Days: {np.median(win_excursions):.2f} points")
print(f"Max Excursion: {np.max(win_excursions):.2f} points")

# Let's see how many days exceed an 80-point 1% target versus letting it run
capped_80 = [80 for x in win_excursions]
print(f"\nTotal Points if Capped at 80 pts (1% target equivalent): {sum(capped_80)}")
print(f"Total Points if Let Run (catching massive trends): {sum(win_excursions)}")
