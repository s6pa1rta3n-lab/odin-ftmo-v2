## Candidate 14 — H1 Z-Score Mean-Reversion Fade Exclusive Dual (research)

**Decision: REJECT**

H1 z-score MR fade (|z|≥2 on SMA48/stdev48) exclusive dual + 1.0×H1 ATR stop + R=1.5 TP + 0.75% equity risk + −3% Prague-day kill.
Cost model: FTMO spread=15 (HF parity with C7/C11/C13). Not C4/C5 %. **No SMA50** regime filter.
Chassis measured: `h1-zscore-mr`. Complement to C11 H1 momentum (fade, not follow).

### Headline
- HO net: $-5,922.29 (~$-607/mo)
- Fit / Leave-out / Ext: $-46,727.60 / $-10,467.45 / $-4,364.71
- Max DD: 60.27%
- Worst Prague day: -6.53%
- ≤60d clean windows @0.75%: **1/950**
- Binding: EDGE/DD: HO edge, extension, leave-out, −5% day, max DD 60.3%, fit, stop/worst-day/DD dollars
- ≤60d BTC-only still **blocked** at FTMO 5%/10% after C14.

### Risk table
| Risk | HO $/mo | Fit | Leave-out | Ext | Worst day | Max DD | ≤60d | Legal |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0.50% | $-503 | $-36,299 | $-8,825 | $-3,133 | -4.37% | 47.2% | 0/950 | NO |
| 0.75% | $-607 | $-46,728 | $-10,467 | $-4,365 | -6.53% | 60.3% | 1/950 | NO |
| 1.00% | $-748 | $-58,216 | $-11,841 | $-4,470 | -8.72% | 72.9% | 47/950 | NO |

### Research-next
H1 z-score mean-reversion chassis failed on edge at locked risk (complement to C11 mom also failed). Together with C5–C13, BTC-only Challenge+Verification in ≤60 days at FTMO 5%/10% DD remains **blocked** — robust edges too slow; H1 mom/MR and session/HF books lack edge or blow DD. Prefer C5/C10 multi-month robustness or diversify beyond BTC-only. Do not deploy C14.

### Live
Research only — C4 / drip / FREEZE / MetaAPI / live VM untouched.

Files under `research/btc/2026-10-07-candidate-14/`.
