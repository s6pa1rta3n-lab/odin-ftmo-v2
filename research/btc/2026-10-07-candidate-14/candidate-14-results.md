# Candidate 14 Results — H1 Z-Score Mean-Reversion Fade Exclusive Dual + ATR Stop R=1.5

**Decision: REJECT**

**One sentence:** REJECT C14 as ≤60d vehicle: H1 z-score MR fade dual R=1.5 @0.75% (chassis=h1-zscore-mr); HO -5,922 (~$-607/mo); fit -46,728; max DD 60.3%; 60d windows 1/950; binding: EDGE/DD: HO edge, extension, leave-out, −5% day, max DD 60.3%, fit, stop/worst-day/DD dollars.

**Measured:** 2026-10-07 11:43:00 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**Spec:** `/workspace/btc-strategies/ftmo-candidate-14.md`
**Chassis:** `h1-zscore-mr`

## Locked rules (a priori)

| Step | Rule |
|---|---|
| Bars | Dukas M1 → H1 UTC (label/closed left, origin 2024-01-01) |
| Z-score | z=(close−SMA48)/stdev48 (population ddof=0); same 48 closes |
| Entry | SHORT if z≥+2.0; LONG if z≤−2.0; no SMA50 regime filter |
| Entry clock | Next H1 open (first M1 at/after bar end); max 1 |
| Stop | 1.0 × H1 ATR(14) |
| Target | 1.5 × stop (R=1.5) |
| Risk | 0.75% equity / stop (also 0.50%, 1.00%) |
| Kill | Prague-day realized ≤ −3% day-start → no new entries |
| Cost | FTMO spread=15 × lots; commission 0; swap 0 |

## ASSUMPTIONS

| Item | Value |
|---|---|
| Account | $100,000 2-step (ASSUMPTION) |
| Challenge / Verification | +10% / +5% |
| Pace bar | ≤60 calendar days both steps |
| Daily / Max DD | 5% / 10% |
| Z lookback / thresh | **48 / 2.0** a priori |
| R multiple | **1.5** a priori on H1 ATR |
| Data | Merged Dukas M1 bid main+ext |

## Gate A — robustness @ 0.75% risk

| Gate | Pass? | Detail |
|---|---|---|
| 1 Holdout >0 | NO | HO $-5,922.29 |
| 2 Extension ≥ 0 | NO | Ext $-4,364.71 |
| 3 Leave-out two best HO Prague months > 0 | NO | removed ['2026-02', '2026-04']; left $-10,467.45 |
| 4 Worst Prague day ≥ −5%; 0 fail-days | NO | worst 2024-07-16 -6.53%; fail-days=1 |
| 5 Max realized DD ≤ 10% | NO | DD 60.27% |
| 6 Fit ≥ −$10k | NO | Fit $-46,727.60 |

**Gate A all pass?** NO

- Trades full L/S: 746/769; n=1515; WR 38.7% (587/928)
- Exit reasons: {'target': 579, 'stop': 920, 'gap-stop': 8, 'gap-target': 8}
- Pace @0.75%: **$-606.99/mo** over HO calendar
- Meta: signals=3523 taken=1515 skip_in_trade=1859 skip_kill=148 skip_lots=0 skip_z=33 killed_days=44

### HO monthly P&L @0.75% (ET exit month)

| ET exit month | Trades | Net $ |
|---|---:|---:|
| 2025-11 | 34 | -2,955.42 |
| 2025-12 | 38 | 1,253.51 |
| 2026-01 | 51 | -97.49 |
| 2026-02 | 33 | 3,362.26 |
| 2026-03 | 44 | -3,129.27 |
| 2026-04 | 34 | 1,182.91 |
| 2026-05 | 41 | -1,111.69 |
| 2026-06 | 49 | -3,139.09 |
| 2026-07 | 49 | -697.33 |
| 2026-08 | 48 | -223.90 |
| 2026-09 | 1 | -366.77 |

## Gate B — ≤60-day vehicle @ 0.75% risk

| Gate | Pass? | Detail |
|---|---|---|
| 7 ≥1 clean 60d window | YES | **1 / 950** windows |
| 8 Pace ≥$7.5k/mo OR Gate 7 | YES | HO pace $-606.99/mo |
| 9 Stop+worst day ≤$5k; DD≤10% | NO | mean stop $460.24; worst day $-5,368.90; DD 60.3% |

**Gate B all pass?** NO

- Final equity: $42,985.39 (net $-57,014.61)
- Binding constraint: **EDGE/DD: HO edge, extension, leave-out, −5% day, max DD 60.3%, fit, stop/worst-day/DD dollars**
- ≤60d BTC-only still **blocked** at FTMO 5%/10% after C14.

### 60-day pass windows (sample)

| Start | End | Start eq | Max mult | Min mult | Worst day |
|---|---|---:|---:|---:|---:|
| 2024-12-30 | 2025-02-27 | $51,258 | 1.166 | 1.011 | -3.73% |

## Risk table (0.50% / 0.75% / 1.00%)

| Risk | HO $/mo | Fit | Leave-out | Ext | Worst day | Max DD | ≤60d | Legal | Decision@risk |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 0.50% | $-503 | $-36,299 | $-8,825 | $-3,133 | -4.37% | 47.2% | 0/950 | NO | REJECT |
| 0.75% | $-607 | $-46,728 | $-10,467 | $-4,365 | -6.53% | 60.3% | 1/950 | NO | REJECT |
| 1.00% | $-748 | $-58,216 | $-11,841 | $-4,470 | -8.72% | 72.9% | 47/950 | NO | REJECT |

## vs C11 / C13

| Book | Chassis | Notes |
|---|---|---|
| C11 | H1 mom dual R=2 @0.75% | REJECT — negative HO, ~60% DD |
| C13 | London ORB R=1.5 @0.75% | REJECT — leave-out + DD 15% |
| **C14** | **H1 z-score MR fade R=1.5 @0.75%** | **REJECT** — HO $-607/mo; DD 60.3%; 1/950 windows |

## Full-sample monthly P&L @0.75% (ET exit month)

| ET exit month | Trades | Net $ |
|---|---:|---:|
| 2024-01 | 46 | -2,589.67 |
| 2024-02 | 48 | -599.70 |
| 2024-03 | 43 | -3,131.62 |
| 2024-04 | 44 | -7,109.17 |
| 2024-05 | 44 | 1,126.46 |
| 2024-06 | 45 | -3,192.43 |
| 2024-07 | 33 | -7,392.64 |
| 2024-08 | 51 | -9,591.21 |
| 2024-09 | 43 | -4,777.75 |
| 2024-10 | 65 | -9,969.34 |
| 2024-11 | 53 | 1,157.33 |
| 2024-12 | 59 | -1,196.30 |
| 2025-01 | 45 | 506.95 |
| 2025-02 | 44 | 2,964.30 |
| 2025-03 | 40 | -580.27 |
| 2025-04 | 40 | -596.18 |
| 2025-05 | 45 | -4,283.54 |
| 2025-06 | 48 | -891.97 |
| 2025-07 | 53 | 1,916.45 |
| 2025-08 | 44 | -163.69 |
| 2025-09 | 38 | 5,120.90 |
| 2025-10 | 51 | -3,115.88 |
| 2025-11 | 47 | -3,294.05 |
| 2025-12 | 38 | 1,253.51 |
| 2026-01 | 51 | -97.49 |
| 2026-02 | 33 | 3,362.26 |
| 2026-03 | 44 | -3,129.27 |
| 2026-04 | 34 | 1,182.91 |
| 2026-05 | 41 | -1,111.69 |
| 2026-06 | 49 | -3,139.09 |
| 2026-07 | 49 | -697.33 |
| 2026-08 | 48 | -223.90 |
| 2026-09 | 47 | -3,076.98 |
| 2026-10 | 12 | -1,654.50 |

## Research-next

H1 z-score mean-reversion chassis failed on edge at locked risk (complement to C11 mom also failed). Together with C5–C13, BTC-only Challenge+Verification in ≤60 days at FTMO 5%/10% DD remains **blocked** — robust edges too slow; H1 mom/MR and session/HF books lack edge or blow DD. Prefer C5/C10 multi-month robustness or diversify beyond BTC-only. Do not deploy C14.

## Live

Do not touch live VM, MetaAPI, C4, drip, FREEZE_NEW_BUYS, or arm anything.
