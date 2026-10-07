# Candidate 15 Results — H4 Bollinger Squeeze Breakout Exclusive Dual + ATR Stop R=2

**Decision: REJECT**

**One sentence:** REJECT C15 as ≤60d vehicle: H4 BB squeeze breakout dual R=2 @0.75% (chassis=h4-bb-squeeze); HO +12,595 (~$1,291/mo); fit +523; max DD 7.4%; 60d windows 0/909; binding: EDGE: extension, 0 ≤60d windows, pace $1,291/mo.

**Measured:** 2026-10-07 11:45:35 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**Spec:** `/workspace/btc-strategies/ftmo-candidate-15.md`
**Chassis:** `h4-bb-squeeze`

## Locked rules (a priori)

| Step | Rule |
|---|---|
| Bars | Dukas M1 → H4 UTC (label/closed left, origin 2024-01-01) |
| BB | SMA20 ± 2×stdev20 (population ddof=0); bw=(upper−lower)/middle |
| Squeeze | bw[t] ≤ P10(bw[t−99..t]) — 100-bar inclusive window, no lookahead |
| Break | squeeze_flag[t−1]==True AND close[t]>upper[t] (L) or close[t]<lower[t] (S) |
| Entry clock | Next H4 open (first M1 at/after bar end); max 1; no SMA50 filter |
| Stop | 1.0 × H4 ATR(14) |
| Target | 2.0 × stop (R=2) |
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
| BB / P10 window | **20 / 2σ / 100-bar P10** a priori |
| R multiple | **2.0** a priori on H4 ATR |
| Data | Merged Dukas M1 bid main+ext |

## Gate A — robustness @ 0.75% risk

| Gate | Pass? | Detail |
|---|---|---|
| 1 Holdout >0 | YES | HO $12,594.53 |
| 2 Extension ≥ 0 | NO | Ext $-1,822.74 |
| 3 Leave-out two best HO Prague months > 0 | YES | removed ['2026-06', '2026-08']; left $3,005.28 |
| 4 Worst Prague day ≥ −5%; 0 fail-days | YES | worst 2026-09-28 -1.53%; fail-days=0 |
| 5 Max realized DD ≤ 10% | YES | DD 7.41% |
| 6 Fit ≥ −$10k | YES | Fit $522.55 |

**Gate A all pass?** NO

- Trades full L/S: 56/58; n=114; WR 38.6% (44/70)
- Exit reasons: {'stop': 67, 'target': 43, 'gap-stop': 3, 'gap-target': 1}
- Pace @0.75%: **$1,290.83/mo** over HO calendar
- Meta: signals=154 taken=114 skip_in_trade=40 skip_kill=0 skip_lots=0 skip_bb=105 squeeze_bars=745 killed_days=0

### HO monthly P&L @0.75% (ET exit month)

| ET exit month | Trades | Net $ |
|---|---:|---:|
| 2025-11 | 2 | 3,024.78 |
| 2025-12 | 6 | -116.84 |
| 2026-01 | 3 | 2,268.79 |
| 2026-02 | 2 | -1,748.92 |
| 2026-03 | 4 | 3,910.20 |
| 2026-04 | 4 | -1,681.10 |
| 2026-05 | 2 | 752.23 |
| 2026-06 | 3 | 4,842.21 |
| 2026-07 | 4 | -3,403.85 |
| 2026-08 | 6 | 4,747.04 |

## Gate B — ≤60-day vehicle @ 0.75% risk

| Gate | Pass? | Detail |
|---|---|---|
| 7 ≥1 clean 60d window | NO | **0 / 909** windows |
| 8 Pace ≥$7.5k/mo OR Gate 7 | NO | HO pace $1,290.83/mo |
| 9 Stop+worst day ≤$5k; DD≤10% | YES | mean stop $766.49; worst day $-1,732.48; DD 7.4% |

**Gate B all pass?** NO

- Final equity: $111,294.34 (net $11,294.34)
- Binding constraint: **EDGE: extension, 0 ≤60d windows, pace $1,291/mo**
- ≤60d BTC-only still **blocked** at FTMO 5%/10% after C15.

### 60-day pass windows (sample)

_None._

## Risk table (0.50% / 0.75% / 1.00%)

| Risk | HO $/mo | Fit | Leave-out | Ext | Worst day | Max DD | ≤60d | Legal | Decision@risk |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 0.50% | $845 | $418 | $2,029 | $-1,166 | -1.03% | 5.0% | 0/909 | YES | REJECT |
| 0.75% | $1,291 | $523 | $3,005 | $-1,823 | -1.53% | 7.4% | 0/909 | YES | REJECT |
| 1.00% | $1,736 | $465 | $3,835 | $-2,527 | -2.04% | 9.8% | 0/909 | YES | REJECT |

## vs C13 / C14

| Book | Chassis | Notes |
|---|---|---|
| C13 | London ORB R=1.5 @0.75% | REJECT — leave-out + DD 15% |
| C14 | H1 z-score MR fade R=1.5 @0.75% | REJECT — EDGE/DD; HO negative, DD 60.3% |
| **C15** | **H4 BB squeeze breakout R=2 @0.75%** | **REJECT** — HO $1,291/mo; DD 7.4%; 0/909 windows |

## Full-sample monthly P&L @0.75% (ET exit month)

| ET exit month | Trades | Net $ |
|---|---:|---:|
| 2024-02 | 2 | -1,563.78 |
| 2024-03 | 2 | -1,498.43 |
| 2024-04 | 6 | -102.59 |
| 2024-05 | 4 | -2,925.74 |
| 2024-06 | 6 | 6,350.10 |
| 2024-08 | 4 | 1,421.47 |
| 2024-09 | 3 | -70.73 |
| 2024-10 | 3 | -68.31 |
| 2024-11 | 2 | 738.92 |
| 2024-12 | 3 | -2,321.53 |
| 2025-01 | 4 | 1,426.93 |
| 2025-02 | 4 | -829.97 |
| 2025-03 | 7 | 1,396.42 |
| 2025-04 | 4 | 1,435.07 |
| 2025-05 | 2 | -1,565.81 |
| 2025-06 | 4 | -841.50 |
| 2025-07 | 1 | -768.27 |
| 2025-08 | 2 | -1,516.17 |
| 2025-09 | 6 | -2,275.95 |
| 2025-10 | 2 | 3,388.94 |
| 2025-11 | 4 | 3,738.25 |
| 2025-12 | 6 | -116.84 |
| 2026-01 | 3 | 2,268.79 |
| 2026-02 | 2 | -1,748.92 |
| 2026-03 | 4 | 3,910.20 |
| 2026-04 | 4 | -1,681.10 |
| 2026-05 | 2 | 752.23 |
| 2026-06 | 3 | 4,842.21 |
| 2026-07 | 4 | -3,403.85 |
| 2026-08 | 6 | 4,747.04 |
| 2026-09 | 5 | -1,822.74 |

## Research-next

DD-legal but pace too slow for ≤60d. Honest multi-month book only. ≤60d BTC-only still **blocked** after C15. Prefer C5/C10. Do not deploy C15.

## Live

Do not touch live VM, MetaAPI, C4, drip, FREEZE_NEW_BUYS, or arm anything.
