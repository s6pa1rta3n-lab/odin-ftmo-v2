# Candidate 16 Results — H1 NR7 Breakout Exclusive Dual + Structural Stop R=1.5

**Decision: REJECT**

**One sentence:** REJECT C16 as ≤60d vehicle: H1 NR7 breakout dual R=1.5 @0.75% (chassis=h1-nr7-breakout); HO -30,727 (~$-3,149/mo); fit -29,665; max DD 63.9%; 60d windows 50/951; binding: EDGE/DD: HO edge, extension, leave-out, −5% day, max DD 63.9%, fit, stop/worst-day/DD dollars. Pace: C16 $-3,149/mo vs C15 ~$1,291/mo.

**Measured:** 2026-10-07 11:48:56 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**Spec:** `/workspace/btc-strategies/ftmo-candidate-16.md`
**Chassis:** `h1-nr7-breakout`

## Locked rules (a priori)

| Step | Rule |
|---|---|
| Bars | Dukas M1 → H1 UTC (label/closed left, origin 2024-01-01) |
| NR7 | range[t] == min(range[t−6..t]); ties allowed |
| Pending | arm at NR7 close; expire after 6 subsequent H1 bars; max 1 pending |
| Break | first close > NR7 high → L; first close < NR7 low → S |
| Entry clock | First M1 at/after **break** H1 bar end; max 1; no SMA50 |
| Stop | Structural: long=NR7 low; short=NR7 high (ATR-free) |
| Target | 1.5 × stop_dist (R=1.5) |
| Risk | 0.75% equity / stop (also 0.50%, 1.00%); lots clamp ≤50 |
| Kill | Prague-day realized ≤ −3% day-start → no new entries |
| Cost | FTMO spread=15 × lots; commission 0; swap 0 |

## ASSUMPTIONS

| Item | Value |
|---|---|
| Account | $100,000 2-step (ASSUMPTION) |
| Challenge / Verification | +10% / +5% |
| Pace bar | ≤60 calendar days both steps |
| Daily / Max DD | 5% / 10% |
| NR7 / expire / R | **7-bar / 6-bar expire / R=1.5** a priori |
| Stop | Structural NR7 opposite side (not ATR) |
| Data | Merged Dukas M1 bid main+ext |

## Gate A — robustness @ 0.75% risk

| Gate | Pass? | Detail |
|---|---|---|
| 1 Holdout >0 | NO | HO $-30,726.64 |
| 2 Extension ≥ 0 | NO | Ext $-3,060.92 |
| 3 Leave-out two best HO Prague months > 0 | NO | removed ['2026-02', '2025-11']; left $-34,248.80 |
| 4 Worst Prague day ≥ −5%; 0 fail-days | NO | worst 2025-03-29 -5.23%; fail-days=1 |
| 5 Max realized DD ≤ 10% | NO | DD 63.87% |
| 6 Fit ≥ −$10k | NO | Fit $-29,664.67 |

**Gate A all pass?** NO

- Trades full L/S: 776/710; n=1486; WR 38.6% (574/912)
- Exit reasons: {'stop': 891, 'target': 570, 'gap-stop': 21, 'gap-target': 4}
- Pace @0.75%: **$-3,149.22/mo** over HO calendar (C16 $-3,149/mo vs C15 ~$1,291/mo)
- Meta: signals=1490 taken=1486 nr7_armed=1515 nr7_expired=25 skip_in_trade=0 skip_kill=2 skip_lots=0 skip_stop=2 lot_clamps=0 nr7_skipped_busy=2040 killed_days=5

### HO monthly P&L @0.75% (ET exit month)

| ET exit month | Trades | Net $ |
|---|---:|---:|
| 2025-11 | 32 | 1,109.84 |
| 2025-12 | 33 | -6,501.67 |
| 2026-01 | 35 | -3,032.03 |
| 2026-02 | 42 | 3,186.41 |
| 2026-03 | 45 | -829.52 |
| 2026-04 | 35 | -3,269.02 |
| 2026-05 | 54 | -10,466.35 |
| 2026-06 | 53 | -1,840.37 |
| 2026-07 | 49 | -5,809.06 |
| 2026-08 | 48 | -3,274.86 |

## Gate B — ≤60-day vehicle @ 0.75% risk

| Gate | Pass? | Detail |
|---|---|---|
| 7 ≥1 clean 60d window | YES | **50 / 951** windows |
| 8 Pace ≥$7.5k/mo OR Gate 7 | YES | HO pace $-3,149.22/mo |
| 9 Stop+worst day ≤$5k; DD≤10% | NO | mean stop $528.47; worst day $-3,704.35; DD 63.9% |

**Gate B all pass?** NO

- Final equity: $36,547.78 (net $-63,452.22)
- Binding constraint: **EDGE/DD: HO edge, extension, leave-out, −5% day, max DD 63.9%, fit, stop/worst-day/DD dollars**
- ≤60d BTC-only still **blocked** at FTMO 5%/10% after C16.

### 60-day pass windows (sample)

| Start | End | Start eq | Max mult | Min mult | Worst day |
|---|---|---:|---:|---:|---:|
| 2024-06-17 | 2024-08-15 | $73,111 | 1.159 | 0.984 | -1.61% |
| 2024-06-18 | 2024-08-16 | $71,932 | 1.178 | 1.003 | -2.31% |
| 2024-06-19 | 2024-08-17 | $72,736 | 1.165 | 0.992 | -2.31% |
| 2024-06-20 | 2024-08-18 | $72,177 | 1.174 | 1.003 | -2.31% |
| 2024-06-21 | 2024-08-19 | $72,402 | 1.174 | 1.011 | -2.31% |
| 2024-06-22 | 2024-08-20 | $74,002 | 1.174 | 0.992 | -2.31% |
| 2024-06-23 | 2024-08-21 | $74,002 | 1.174 | 0.992 | -2.31% |
| 2024-06-24 | 2024-08-22 | $73,430 | 1.183 | 1.003 | -2.31% |
| 2024-06-25 | 2024-08-23 | $74,231 | 1.170 | 0.993 | -2.31% |
| 2024-06-26 | 2024-08-24 | $74,231 | 1.170 | 0.993 | -2.31% |
| 2024-06-27 | 2024-08-25 | $74,231 | 1.170 | 0.993 | -2.31% |
| 2024-06-28 | 2024-08-26 | $74,231 | 1.170 | 0.993 | -2.31% |
| 2024-06-29 | 2024-08-27 | $74,231 | 1.185 | 0.993 | -2.31% |
| 2024-06-30 | 2024-08-28 | $74,231 | 1.185 | 0.993 | -2.31% |
| 2024-07-01 | 2024-08-29 | $74,231 | 1.185 | 0.993 | -2.31% |
| 2024-07-02 | 2024-08-30 | $74,231 | 1.185 | 0.993 | -2.31% |
| 2024-07-03 | 2024-08-31 | $74,231 | 1.185 | 0.993 | -2.31% |
| 2024-07-04 | 2024-09-01 | $74,231 | 1.185 | 0.993 | -2.31% |
| 2024-07-05 | 2024-09-02 | $74,469 | 1.181 | 0.992 | -2.31% |
| 2024-07-06 | 2024-09-03 | $74,709 | 1.177 | 0.992 | -2.31% |

## Risk table (0.50% / 0.75% / 1.00%)

| Risk | HO $/mo | Fit | Leave-out | Ext | Worst day | Max DD | ≤60d | Legal | Decision@risk |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 0.50% | $-2,575 | $-20,115 | $-27,934 | $-2,851 | -3.49% | 48.5% | 0/951 | NO | REJECT |
| 0.75% | $-3,149 | $-29,665 | $-34,249 | $-3,061 | -5.23% | 63.9% | 50/951 | NO | REJECT |
| 1.00% | $-3,439 | $-39,152 | $-37,450 | $-2,804 | -6.98% | 75.9% | 93/951 | NO | REJECT |

## vs C15 (pace target)

| Book | Chassis | Notes |
|---|---|---|
| C15 | H4 BB squeeze R=2 @0.75% | REJECT near-miss — HO ~$1,291/mo; DD 7.4%; Ext fail; 0/909 |
| **C16** | **H1 NR7 breakout R=1.5 @0.75%** | **REJECT** — HO $-3,149/mo; DD 63.9%; 50/951 windows; C16 $-3,149/mo vs C15 ~$1,291/mo |

## Full-sample monthly P&L @0.75% (ET exit month)

| ET exit month | Trades | Net $ |
|---|---:|---:|
| 2024-01 | 56 | -8,966.42 |
| 2024-02 | 44 | -1,461.03 |
| 2024-03 | 52 | -5,625.99 |
| 2024-04 | 41 | -7,508.24 |
| 2024-05 | 49 | -2,124.06 |
| 2024-06 | 31 | -83.14 |
| 2024-07 | 48 | 8,664.68 |
| 2024-08 | 42 | 3,942.92 |
| 2024-09 | 52 | 1,685.38 |
| 2024-10 | 53 | -6,957.62 |
| 2024-11 | 40 | -2,183.70 |
| 2024-12 | 50 | -2,484.52 |
| 2025-01 | 48 | 1,633.08 |
| 2025-02 | 34 | -2,859.83 |
| 2025-03 | 45 | -9,351.62 |
| 2025-04 | 47 | -4,280.97 |
| 2025-05 | 50 | 5,054.45 |
| 2025-06 | 47 | 7,163.27 |
| 2025-07 | 17 | -178.90 |
| 2025-08 | 52 | -2,237.98 |
| 2025-09 | 49 | -2,183.12 |
| 2025-10 | 52 | 1,052.51 |
| 2025-11 | 40 | 736.00 |
| 2025-12 | 33 | -6,501.67 |
| 2026-01 | 35 | -3,032.03 |
| 2026-02 | 42 | 3,186.41 |
| 2026-03 | 45 | -829.52 |
| 2026-04 | 35 | -3,269.02 |
| 2026-05 | 54 | -10,466.35 |
| 2026-06 | 53 | -1,840.37 |
| 2026-07 | 49 | -5,809.06 |
| 2026-08 | 48 | -3,274.86 |
| 2026-09 | 42 | -2,626.81 |
| 2026-10 | 11 | -434.11 |

## Research-next

H1 NR7 breakout chassis failed on edge at locked risk. C16 HO pace $-3,149/mo vs C15 ~$1,291/mo (-2.44×). Together with C5–C15, BTC-only Challenge+Verification in ≤60 days at FTMO 5%/10% DD remains **blocked** — robust edges too slow; HF books lack edge or blow DD. Prefer C5/C10 multi-month robustness or diversify beyond BTC-only. Do not deploy C16.

## Live

Do not touch live VM, MetaAPI, C4, drip, FREEZE_NEW_BUYS, or arm anything.
