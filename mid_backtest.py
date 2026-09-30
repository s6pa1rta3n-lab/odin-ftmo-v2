import yfinance as yf
import pandas as pd
import numpy as np
import logging

logging.getLogger('yfinance').setLevel(logging.CRITICAL)

print("Downloading 720 days of 1-hour NQ=F and VIX data...")
nq = yf.download('NQ=F', period='720d', interval='1h', progress=False)
vix = yf.download('^VIX', period='720d', interval='1d', progress=False)

if isinstance(nq.columns, pd.MultiIndex): nq.columns = nq.columns.droplevel(1)
if isinstance(vix.columns, pd.MultiIndex): vix.columns = vix.columns.droplevel(1)

nq.index = pd.to_datetime(nq.index, utc=True)
vix.index = pd.to_datetime(vix.index, utc=True)

dates = np.unique(nq.index.date)
results = []

for date in dates:
    day_data = nq[nq.index.date == date]
    us_bars = day_data[(day_data.index.hour >= 13) & (day_data.index.hour < 21)]
    
    if us_bars.empty or len(us_bars) < 2:
        continue
        
    vix_prev_day = date - pd.Timedelta(days=1)
    available_vix_dates = vix.index[vix.index.date <= vix_prev_day]
    if len(available_vix_dates) == 0:
        continue
        
    vix_val = vix.loc[available_vix_dates[-1], 'Close']
    vix_val = float(vix_val.iloc[0]) if isinstance(vix_val, pd.Series) else float(vix_val)
    
    day_open = float(us_bars['Open'].iloc[0])
    
    def sim_day(buffer_pts, max_bullets, risk_mult):
        orb_h = day_open + buffer_pts
        orb_l = day_open - buffer_pts
        
        bullets_fired = 0
        pnl = 0.0
        position = 0
        entry_price = 0.0
        
        for idx, bar in us_bars.iterrows():
            if bullets_fired >= max_bullets and position == 0:
                break
                
            high = float(bar['High'])
            low = float(bar['Low'])
            
            if position == 1:
                if low <= entry_price - 40:
                    pnl -= 40 * risk_mult
                    position = 0
                elif high >= entry_price + 80:
                    pnl += 80 * risk_mult
                    position = 0
                    break
            elif position == -1:
                if high >= entry_price + 40:
                    pnl -= 40 * risk_mult
                    position = 0
                elif low <= entry_price - 80:
                    pnl += 80 * risk_mult
                    position = 0
                    break
                    
            if position == 0 and bullets_fired < max_bullets:
                if high >= orb_h:
                    position = 1
                    entry_price = orb_h
                    bullets_fired += 1
                    if low <= entry_price - 40:
                        pnl -= 40 * risk_mult
                        position = 0
                elif low <= orb_l:
                    position = -1
                    entry_price = orb_l
                    bullets_fired += 1
                    if high >= entry_price + 40:
                        pnl -= 40 * risk_mult
                        position = 0
                        
        return pnl

    baseline = sim_day(15, 4, 1.0)
    risk = 0.33 if vix_val < 15 else 1.0
    opt1 = sim_day(15, 4, risk)
    ammo = 1 if vix_val < 15 else 4
    opt2 = sim_day(15, ammo, 1.0)
    buff = 35 if vix_val < 15 else 15
    opt3 = sim_day(buff, 4, 1.0)
    
    results.append({
        'Date': date,
        'VIX': vix_val,
        'Baseline': baseline,
        'Opt1': opt1,
        'Opt2': opt2,
        'Opt3': opt3
    })

df = pd.DataFrame(results)

def analyze(col_name, label):
    cum = df[col_name].cumsum()
    total = cum.iloc[-1]
    
    roll_max = cum.cummax()
    dd = (roll_max - cum).max()
    
    win_days = len(df[df[col_name] > 0])
    loss_days = len(df[df[col_name] < 0])
    flat_days = len(df[df[col_name] == 0])
    
    print(f"\n--- {label} ---")
    print(f"Total Net Points:  {total:+.1f} pts")
    print(f"Max Drawdown:      -{dd:.1f} pts")
    print(f"Win/Loss/Flat Days: {win_days} / {loss_days} / {flat_days}")

print(f"\nAnalyzed {len(df)} US Trading Sessions.")
analyze('Baseline', 'BASELINE (Trade every day, max 4 losses/day)')
analyze('Opt1', '1. DYNAMIC RISK (Cut position size by 66% on VIX < 15)')
analyze('Opt2', '2. DYNAMIC AMMO (Only 1 trade allowed on VIX < 15)')
analyze('Opt3', '3. DYNAMIC RANGE (Widen ORB buffer to 35 pts on VIX < 15)')
