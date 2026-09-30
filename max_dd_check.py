import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')
from daily_drawdown_check import df

# The df already has 'dynamic_pct' and 'R' from the previous run
df = df.sort_values('time')

# 1. Flat 1% Risk Max DD
df['cum_1pct'] = df['R'].cumsum()
df['peak_1pct'] = df['cum_1pct'].cummax()
df['dd_1pct'] = df['cum_1pct'] - df['peak_1pct']
max_dd_1pct = df['dd_1pct'].min()

# 2. Dynamic Matrix Max DD
df['cum_dyn'] = df['dynamic_pct'].cumsum()
df['peak_dyn'] = df['cum_dyn'].cummax()
df['dd_dyn'] = df['cum_dyn'] - df['peak_dyn']
max_dd_dyn = df['dd_dyn'].min()

# 3. Calculate max safe multiplier
# If max_dd_dyn is -X%, how much can we multiply it by to safely hit -9.5%?
safe_multiplier = 9.5 / abs(max_dd_dyn) if max_dd_dyn != 0 else 0

print(f"Flat 1% Max Drawdown: {max_dd_1pct:.2f}%")
print(f"Dynamic Matrix Max Drawdown: {max_dd_dyn:.2f}%")
print(f"Max Safe Multiplier (to stay under 10%): {safe_multiplier:.2f}x")

