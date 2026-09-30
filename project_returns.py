import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')
from monte_carlo_1month import get_trades_for_symbol

trades_nq = get_trades_for_symbol("NQ=F")
trades_gc = get_trades_for_symbol("GC=F")
trades_btc = get_trades_for_symbol("BTC-USD")

r_nq = sum(t['R'] for t in trades_nq)
r_gc = sum(t['R'] for t in trades_gc)
r_btc = sum(t['R'] for t in trades_btc)

total_days = 720.0
# New dynamic sizing risks
risk_nq = 0.0065 # 0.65%
risk_gc = 0.0000 # 0.00% (Deprecated)
risk_btc = 0.0080 # 0.80%

pct_nq = r_nq * risk_nq
pct_gc = r_gc * risk_gc
pct_btc = r_btc * risk_btc

total_pct = pct_nq + pct_gc + pct_btc

# Calculate averages
daily = total_pct / total_days
monthly = daily * 30.44
quarterly = monthly * 3
yearly = daily * 365.25

acct = 100000.0

print(f"Total % Return in 720 days: {total_pct:.2%}")
print(f"--- EXPECTED PROJECTIONS ($100k Account) ---")
print(f"Daily:     {daily:.2%} -> ${acct * daily:,.2f}")
print(f"Monthly:   {monthly:.2%} -> ${acct * monthly:,.2f}")
print(f"Quarterly: {quarterly:.2%} -> ${acct * quarterly:,.2f}")
print(f"Yearly:    {yearly:.2%} -> ${acct * yearly:,.2f}")

