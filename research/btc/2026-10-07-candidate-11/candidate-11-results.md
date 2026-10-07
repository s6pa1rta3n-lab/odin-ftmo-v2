# Candidate 11 Results — H1 Momentum Exclusive Dual + ATR Stop R=2

**Decision: REJECT**

**One sentence:** REJECT C11 as ≤60d vehicle: H1 mom dual R=2 @0.75%; HO -25,043 (~$-2,567/mo); fit -24,526; max DD 59.6%; 60d windows 222/949; binding: HO edge, extension, leave-out, max DD 59.6%, fit, stop/worst-day/DD dollars.

**Measured:** 2026-10-07 09:17:16 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**Spec:** `/workspace/btc-strategies/ftmo-candidate-11.md`

## Locked rules (a priori)

| Step | Rule |
|---|---|
| Bars | Dukas M1 → H1 UTC (label/closed left, origin 2024-01-01) |
| Regime+entry | Prior H1 close vs SMA50(H1); long if above+bullish candle; short if below+bearish |
| Entry clock | Next H1 open (first M1 at/after bar end); max 1 |
| Stop | 1.0 × H1 ATR(14) |
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
| R multiple | **2.0** a priori on H1 ATR (not daily 412.91 book) |
| Data | Merged Dukas M1 bid main+ext |

## Gate A — robustness @ 0.75% risk

| Gate | Pass? | Detail |
|---|---|---|
| 1 Holdout >0 | NO | HO $-25,043.28 |
| 2 Extension ≥ 0 | NO | Ext $-1,971.91 |
| 3 Leave-out two best HO months > 0 | NO | removed ['2026-02', '2026-01']; left $-44,964.57 |
| 4 Worst Prague day ≥ −5%; 0 fail-days | YES | worst 2025-03-29 -4.48%; fail-days=0 |
| 5 Max realized DD ≤ 10% | NO | DD 59.61% |
| 6 Fit ≥ −$10k | NO | Fit $-24,525.71 |

**Gate A all pass?** NO

- Trades full L/S: 1628/1528; n=3156; WR 33.8% (1068/2088)
- Exit reasons: {'stop': 2058, 'target': 1056, 'gap-stop': 30, 'gap-target': 12}
- Pace @0.75%: **$-2,566.72/mo** over HO calendar
- Meta: signals=12933 taken=3156 skip_in_trade=9284 skip_kill=492 skip_lots=0 killed_days=112

### HO monthly P&L @0.75% (ET exit month)

| ET exit month | Trades | Net $ |
|---|---:|---:|
| 2025-11 | 61 | 136.20 |
| 2025-12 | 103 | -8,918.58 |
| 2026-01 | 93 | 7,743.28 |
| 2026-02 | 85 | 12,178.01 |
| 2026-03 | 104 | -5,389.86 |
| 2026-04 | 95 | -16,107.00 |
| 2026-05 | 93 | -10,079.12 |
| 2026-06 | 89 | 2,226.19 |
| 2026-07 | 77 | -3,690.66 |
| 2026-08 | 91 | -3,490.78 |
| 2026-09 | 2 | 349.04 |

## Gate B — ≤60-day vehicle @ 0.75% risk

| Gate | Pass? | Detail |
|---|---|---|
| 7 ≥1 clean 60d window | YES | **222 / 949** windows |
| 8 Pace ≥$7.5k/mo OR Gate 7 | YES | HO pace $-2,566.72/mo |
| 9 Stop+worst day ≤$5k; DD≤10% | NO | mean stop $604.94; worst day $-3,862.93; DD 59.6% |

**Gate B all pass?** NO

- Final equity: $48,459.11 (net $-51,540.89)
- Binding constraint: **HO edge, extension, leave-out, max DD 59.6%, fit, stop/worst-day/DD dollars**

### 60-day pass windows (sample)

| Start | End | Start eq | Max mult | Min mult | Worst day |
|---|---|---:|---:|---:|---:|
| 2024-02-08 | 2024-04-07 | $81,664 | 1.247 | 0.912 | -3.15% |
| 2024-02-20 | 2024-04-19 | $80,180 | 1.270 | 0.929 | -3.14% |
| 2024-02-21 | 2024-04-20 | $77,663 | 1.311 | 0.959 | -3.08% |
| 2024-02-22 | 2024-04-21 | $76,955 | 1.323 | 0.968 | -3.08% |
| 2024-02-23 | 2024-04-22 | $74,587 | 1.366 | 0.999 | -3.08% |
| 2024-02-24 | 2024-04-23 | $75,680 | 1.346 | 0.984 | -3.08% |
| 2024-02-25 | 2024-04-24 | $74,945 | 1.359 | 0.994 | -3.08% |
| 2024-02-26 | 2024-04-25 | $76,471 | 1.332 | 0.974 | -3.08% |
| 2024-02-27 | 2024-04-26 | $77,788 | 1.309 | 1.015 | -3.08% |
| 2024-02-28 | 2024-04-27 | $80,658 | 1.263 | 1.015 | -3.08% |
| 2024-02-29 | 2024-04-28 | $83,582 | 1.219 | 1.015 | -3.10% |
| 2024-03-01 | 2024-04-29 | $83,582 | 1.219 | 1.015 | -3.10% |
| 2024-03-02 | 2024-04-30 | $83,582 | 1.219 | 1.015 | -3.10% |
| 2024-03-03 | 2024-05-01 | $83,582 | 1.219 | 1.015 | -3.10% |
| 2024-03-04 | 2024-05-02 | $83,582 | 1.219 | 1.015 | -3.10% |
| 2024-06-11 | 2024-08-09 | $79,719 | 1.178 | 0.958 | -3.10% |
| 2024-06-13 | 2024-08-11 | $81,286 | 1.161 | 0.940 | -3.10% |
| 2024-06-14 | 2024-08-12 | $80,600 | 1.171 | 0.948 | -3.10% |
| 2024-06-15 | 2024-08-13 | $80,521 | 1.172 | 0.949 | -3.10% |
| 2024-06-16 | 2024-08-14 | $80,521 | 1.172 | 0.949 | -3.10% |


### Caveat on 60d windows

Of **222** formal Gate-7 passes, **0** start near a fresh $100k Challenge equity; **30** start at ≥$95k. The rest are local rallies from already-drawn equity (~$75–85k) on a losing path — **not** a viable Challenge start. Gate A edge/DD failures dominate; do not read 222 as a pass-rate for FTMO.

## Risk table (0.50% / 0.75% / 1.00%)

| Risk | HO net | HO $/mo | Fit | Ext | Max DD | Worst day % | 60d passes | Final eq | Decision@risk |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0.50% | $-18,587 | $-1,905 | $-10,274 | $-2,832 | 44.3% | -3.36% | 82/949 | $68,307 | REJECT |
| 0.75% | $-25,043 | $-2,567 | $-24,526 | $-1,972 | 59.6% | -4.48% | 222/949 | $48,459 | REJECT |
| 1.00% | $-29,812 | $-3,056 | $-32,156 | $-80 | 65.8% | -5.99% | 266/949 | $37,952 | REJECT |

## vs C5 / C10

| Book | Chassis | $/mo (ref) | ≤60d windows @ legal-ish | Notes |
|---|---|---:|---|---|
| C5 | SMA50 daily + filters R=1 @0.01 | ~$450 | 0 at legal size | research ACCEPT; too slow |
| C10 | C5 + R-trail @1% | ~$745 | 0/252 | CONDITIONAL; DD 14.7% |
| **C11** | **H1 mom dual R=2 @0.75%** | **$-2,567** | **222/949** | **REJECT** |

## Full-sample monthly P&L @0.75% (ET exit month)

| ET exit month | Trades | Net $ |
|---|---:|---:|
| 2024-01 | 95 | -9,617.48 |
| 2024-02 | 100 | -6,800.02 |
| 2024-03 | 90 | 12,255.55 |
| 2024-04 | 93 | -4,403.02 |
| 2024-05 | 81 | -8,161.83 |
| 2024-06 | 81 | -3,303.29 |
| 2024-07 | 97 | 6,282.86 |
| 2024-08 | 86 | 2,572.53 |
| 2024-09 | 112 | 5,818.71 |
| 2024-10 | 108 | 9,390.44 |
| 2024-11 | 108 | 2,156.66 |
| 2024-12 | 107 | -11,355.54 |
| 2025-01 | 94 | 1,598.80 |
| 2025-02 | 79 | 4,177.55 |
| 2025-03 | 103 | -20,423.31 |
| 2025-04 | 110 | -14,659.15 |
| 2025-05 | 111 | 4,573.90 |
| 2025-06 | 106 | 10,437.69 |
| 2025-07 | 88 | -796.57 |
| 2025-08 | 109 | -1,270.25 |
| 2025-09 | 104 | -11,558.22 |
| 2025-10 | 80 | 10,696.56 |
| 2025-11 | 85 | -2,002.07 |
| 2025-12 | 103 | -8,918.58 |
| 2026-01 | 93 | 7,743.28 |
| 2026-02 | 85 | 12,178.01 |
| 2026-03 | 104 | -5,389.86 |
| 2026-04 | 95 | -16,107.00 |
| 2026-05 | 93 | -10,079.12 |
| 2026-06 | 89 | 2,226.19 |
| 2026-07 | 77 | -3,690.66 |
| 2026-08 | 91 | -3,490.78 |
| 2026-09 | 78 | -2,316.74 |
| 2026-10 | 21 | 693.88 |

## Research-next

**Binding:** negative expectancy after costs (WR 33.8% @ R=2 ≈ breakeven before spread; HO −$2.6k/mo; max DD 59.6%).

H1 momentum exclusive dual is a dead chassis for ≤60d. Do not stack multi-position on C11 losers.

**One last chassis class worth trying:** multi-position **capped aggregate risk** on a *known-positive* slow edge (C5-family / similar), e.g. up to N concurrent independent ideas with Σ risk ≤ ~1%/day and hard portfolio Prague kill — aiming to raise $/mo without the C6 per-trade size wall.

**If that also prints 0 ≤60d windows at legal 5%/10% DD:** treat **BTC-only ≤60d Challenge+Verification as structurally implausible** on this Dukas sample + rule set (robust books too slow; HF books no edge or illegal DD; size hits the wall).

Do not revive SMA50 dual-exit milking, raw TSMOM-20, or raw H4-BREAK-6 without hard stops.


## Live

Do not touch live VM, MetaAPI, C4, drip, FREEZE_NEW_BUYS, or arm anything.
