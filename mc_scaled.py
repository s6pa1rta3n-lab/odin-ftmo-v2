import pandas as pd
import numpy as np
from daily_drawdown_check import df

r_dyn = df['dynamic_pct'].values

SIMULATIONS = 10000
FAIL_THRESHOLD = -10.0

# Base Dynamic Matrix
failed_base = 0
for _ in range(SIMULATIONS):
    sampled = np.random.choice(r_dyn, size=len(r_dyn), replace=True)
    cum = np.cumsum(sampled)
    dd = cum - np.maximum.accumulate(cum)
    if np.min(dd) <= FAIL_THRESHOLD: failed_base += 1

# 1.4x Scaled Matrix
r_scaled = r_dyn * 1.4
failed_scaled = 0
max_dds = []
for _ in range(SIMULATIONS):
    sampled = np.random.choice(r_scaled, size=len(r_scaled), replace=True)
    cum = np.cumsum(sampled)
    dd = cum - np.maximum.accumulate(cum)
    max_dds.append(np.min(dd))
    if np.min(dd) <= FAIL_THRESHOLD: failed_scaled += 1

print(f"Base Dynamic RoR (-10%): {(failed_base/SIMULATIONS)*100:.2f}%")
print(f"1.4x Scaled RoR (-10%): {(failed_scaled/SIMULATIONS)*100:.2f}%")
print(f"1.4x Scaled Avg Max DD: {np.mean(max_dds):.2f}%")

