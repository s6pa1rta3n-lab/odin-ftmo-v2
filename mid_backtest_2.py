import yfinance as yf
import pandas as pd
import numpy as np
import logging

logging.getLogger('yfinance').setLevel(logging.CRITICAL)

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
    if us_bars.empty or len(us_bars) < 2: continue
    vix_prev_day = date - pd.Timedelta(days=1)
    available_vix_dates = vix.index[vix.index.date <= vix_prev_day]
    if len(available_vix_dates) == 0: continue
    vix_val = float(vix.loc[available_vix_dates[-1], 'Close'].iloc[0]) if isinstance(vix.loc[available_vix_dates[-1], 'Close'], pd.Series) else float(vix.loc[available_vix_dates[-1], 'Close'])
    day_open = float(us_bars['Open'].iloc[0])
    
    def sim_day(buffer_pts, max_bullets):
        orb_h = day_open + buffer_pts
        orb_l = day_open - buffer_pts
        bullets_fired = 0
        pnl = 0.0
        position = 0
        entry_price = 0.0
        for idx, bar in us_bars.iterrows():
            if bullets_fired >= max_bullets and position == 0: break
            high = float(bar['High'])
            low = float(bar['Low'])
            if position == 1:
                if low <= entry_price - 40: pnl -= 40; position = 0
                elif high >= entry_price + 80: pnl += 80; position = 0; break
            elif position == -1:
                if high >= entry_price + 40: pnl -= 40; position = 0
                elif low <= entry_price - 80: pnl += 80; position = 0; break
            if position == 0 and bullets_fired < max_bullets:
                if high >= orb_h:
                    position = 1; entry_price = orb_h; bullets_fired += 1
                    if low <= entry_price - 40: pnl -= 40; position = 0
                elif low <= orb_l:
                    position = -1; entry_price = orb_l; bullets_fired += 1
                    if high >= entry_price + 40: pnl -= 40; position = 0
        return pnl

    bl_4 = sim_day(15, 4)
    bl_3 = sim_day(15, 3)
    bl_2 = sim_day(15, 2)
    bl_1 = sim_day(15, 1)
    
    results.append({
        'Date': date, 'BL4': bl_4, 'BL3': bl_3, 'BL2': bl_2, 'BL1': bl_1
    })

df = pd.DataFrame(results)
def analyze(col_name, label):
    cum = df[col_name].cumsum(); total = cum.iloc[-1]; dd = (cum.cummax() - cum).max()
    print(f"{label:<25} | Net: {total:>+6.0f} | DD: {-dd:>6.0f}")

analyze('BL4', 'Max 4 Trades per Day')
analyze('BL3', 'Max 3 Trades per Day')
analyze('BL2', 'Max 2 Trades per Day')
analyze('BL1', 'Max 1 Trade per Day')
