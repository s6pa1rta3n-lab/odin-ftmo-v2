# Candidate 13 Results — London Opening Range Breakout (ORB)

**Decision: REJECT**

**One sentence:** REJECT C13 as ≤60d vehicle: London ORB dual R=1.5 @0.75% (chassis=london-orb); HO +4,295 (~$440/mo); fit +17,519; max DD 15.0%; 60d windows 15/951; binding: EDGE/DD: leave-out, max DD 15.0%, stop/worst-day/DD dollars.

**Measured:** 2026-10-07 11:40:23 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**Spec:** `/workspace/btc-strategies/ftmo-candidate-13.md`
**Chassis used:** `london-orb` (primary ORB)

## Locked rules (a priori)

| Step | Rule |
|---|---|
| OR | First London hour 07:00–07:59 UTC; ≥45 M1 bars |
| Break | M1 close beyond OR high/low after 08:00 UTC; first wins |
| Entry | Next M1 open after confirm; max 1; same UTC day |
| Stop | **Opposite side of OR** (not mid) — a priori |
| Target | 1.5 × stop_dist (R=1.5) |
| Risk | 0.75% equity / stop (also 0.50%, 1.00%) |
| Kill | Prague-day realized ≤ −3% day-start → no new entries |
| Cost | FTMO spread=15 × lots; commission 0; swap 0 (C7/C11 parity) |

## ASSUMPTIONS

| Item | Value |
|---|---|
| Account | $100,000 2-step (ASSUMPTION) |
| Challenge / Verification | +10% / +5% (1.10 / 1.155 window) |
| Pace bar | ≤60 calendar days both steps |
| Daily / Max DD | 5% / 10% |
| Stop rule | Opposite OR side always (not mid) |
| R multiple | **1.5** a priori |
| Data | Merged Dukas M1 bid main+ext |
| Cost | spread=15 (not C4 0.065%/side) |

## Gate A — robustness @ 0.75% risk

| Gate | Pass? | Detail |
|---|---|---|
| 1 Holdout >0 | YES | HO $4,295.48 |
| 2 Extension ≥ 0 | YES | Ext $5,019.64 |
| 3 Leave-out two best HO Prague months > 0 | NO | removed ['2026-05', '2026-08']; left $-9,105.58 |
| 4 Worst Prague day ≥ −5%; 0 fail-days | YES | worst 2026-02-11 -1.61%; fail-days=0 |
| 5 Max realized DD ≤ 10% | NO | DD 14.99% |
| 6 Fit ≥ −$10k | YES | Fit $17,518.99 |

**Gate A all pass?** NO

- Trades full L/S: 479/454; n=933; WR 43.4% (405/528)
- Exit reasons: {'stop': 513, 'target': 401, 'gap-target': 4, 'gap-stop': 15}
- Pace @0.75%: **$440.25/mo** over HO calendar
- OR days formed: 963; mean OR range on trades: $446.1
- Meta: signals=933 taken=933 skip_in_trade=0 skip_kill=0 skip_lots=0 skip_thin=11 skip_no_break=30 killed_days=0

### HO monthly P&L @0.75% (ET exit month)

| ET exit month | Trades | Net $ |
|---|---:|---:|
| 2025-11 | 19 | 2,302.58 |
| 2025-12 | 26 | -2,180.02 |
| 2026-01 | 30 | -7,565.96 |
| 2026-02 | 25 | -859.77 |
| 2026-03 | 31 | 218.08 |
| 2026-04 | 28 | 143.24 |
| 2026-05 | 22 | 7,712.42 |
| 2026-06 | 28 | 613.66 |
| 2026-07 | 30 | -1,906.45 |
| 2026-08 | 30 | 4,494.88 |
| 2026-09 | 1 | 1,322.83 |

## Gate B — ≤60-day vehicle @ 0.75% risk

| Gate | Pass? | Detail |
|---|---|---|
| 7 ≥1 clean 60d window | YES | **15 / 951** windows |
| 8 Pace ≥$7.5k/mo OR Gate 7 | YES | HO pace $440.25/mo |
| 9 Stop+worst day ≤$5k; DD≤10% | NO | mean stop $829.93; worst day $-1,942.24; DD 15.0% |

**Gate B all pass?** NO

- Final equity: $126,834.11 (net $26,834.11)
- Binding constraint: **EDGE/DD: leave-out, max DD 15.0%, stop/worst-day/DD dollars**
- DD-legal @0.75%? **NO**

### 60-day pass windows (sample)

| Start | End | Start eq | Max mult | Min mult | Worst day |
|---|---|---:|---:|---:|---:|
| 2024-11-26 | 2025-01-24 | $101,633 | 1.160 | 0.978 | -0.81% |
| 2024-11-28 | 2025-01-26 | $101,972 | 1.156 | 0.974 | -0.81% |
| 2024-11-29 | 2025-01-27 | $101,187 | 1.165 | 0.982 | -0.81% |
| 2024-12-01 | 2025-01-29 | $101,510 | 1.161 | 0.979 | -0.81% |
| 2024-12-03 | 2025-01-31 | $101,820 | 1.158 | 0.976 | -0.81% |
| 2024-12-06 | 2025-02-03 | $101,363 | 1.163 | 0.980 | -0.81% |
| 2024-12-07 | 2025-02-04 | $100,584 | 1.172 | 0.988 | -0.81% |
| 2024-12-08 | 2025-02-05 | $99,803 | 1.181 | 0.995 | -0.81% |
| 2024-12-09 | 2025-02-06 | $100,880 | 1.169 | 0.985 | -0.81% |
| 2024-12-10 | 2025-02-07 | $100,117 | 1.178 | 0.992 | -0.81% |
| 2024-12-11 | 2025-02-08 | $99,347 | 1.187 | 1.003 | -0.81% |
| 2024-12-12 | 2025-02-09 | $100,446 | 1.174 | 0.992 | -0.81% |
| 2024-12-13 | 2025-02-10 | $99,662 | 1.183 | 1.011 | -0.81% |
| 2024-12-14 | 2025-02-11 | $100,768 | 1.170 | 1.011 | -0.81% |
| 2024-12-15 | 2025-02-12 | $101,864 | 1.157 | 1.011 | -0.81% |

## Risk table (0.50% / 0.75% / 1.00%)

| Risk | HO net | HO $/mo | Fit | Leave-out | Ext | Max DD | Worst day % | 60d passes | Legal | Decision@risk |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 0.50% | $2,981 | $306 | $12,072 | $-5,675 | $3,189 | 10.2% | -1.08% | 0/951 | NO | REJECT |
| 0.75% | $4,295 | $440 | $17,519 | $-9,106 | $5,020 | 15.0% | -1.61% | 15/951 | NO | REJECT |
| 1.00% | $5,374 | $551 | $22,486 | $-12,899 | $7,002 | 19.7% | -2.13% | 45/951 | NO | REJECT |

## vs prior candidates

| Book | Chassis | $/mo (ref) | ≤60d @ legal-ish | Notes |
|---|---|---:|---|---|
| C5 | SMA50 daily + filters R=1 @0.01 | ~$450 | 0 | research ACCEPT; too slow |
| C7 | H4-BREAK dual R=1 | ~$508 | 0; DD 17% | REJECT |
| C11 | H1 mom dual R=2 @0.75% | negative | 0; DD ~60% | REJECT |
| C12 | C5 stack N=3 | ~$448 | 0/850 | REJECT + structural |
| **C13** | **London ORB R=1.5 @0.75%** | **$440** | **15/951** | **REJECT** |

## Full-sample monthly P&L @0.75% (ET exit month)

| ET exit month | Trades | Net $ |
|---|---:|---:|
| 2024-01 | 29 | -901.32 |
| 2024-02 | 25 | 508.86 |
| 2024-03 | 30 | 1,055.60 |
| 2024-04 | 29 | 5,582.47 |
| 2024-05 | 16 | -5,073.49 |
| 2024-06 | 27 | 3,119.93 |
| 2024-07 | 28 | 409.26 |
| 2024-08 | 31 | -5,815.36 |
| 2024-09 | 30 | -1,411.31 |
| 2024-10 | 31 | 3,056.56 |
| 2024-11 | 30 | 978.64 |
| 2024-12 | 30 | 9,037.91 |
| 2025-01 | 30 | 3,207.26 |
| 2025-02 | 24 | -2,184.98 |
| 2025-03 | 30 | 3,177.97 |
| 2025-04 | 28 | -1,467.12 |
| 2025-05 | 29 | 1,973.80 |
| 2025-06 | 28 | -1,552.98 |
| 2025-07 | 29 | 4,192.48 |
| 2025-08 | 31 | 4,608.50 |
| 2025-09 | 29 | -4,762.22 |
| 2025-10 | 27 | 1,768.56 |
| 2025-11 | 26 | 312.55 |
| 2025-12 | 26 | -2,180.02 |
| 2026-01 | 30 | -7,565.96 |
| 2026-02 | 25 | -859.77 |
| 2026-03 | 31 | 218.08 |
| 2026-04 | 28 | 143.24 |
| 2026-05 | 22 | 7,712.42 |
| 2026-06 | 28 | 613.66 |
| 2026-07 | 30 | -1,906.45 |
| 2026-08 | 30 | 4,494.88 |
| 2026-09 | 30 | 2,850.17 |
| 2026-10 | 6 | 3,492.30 |

## Research-next

London ORB chassis failed Gate A (edge and/or DD) at locked risk. Together with C5–C12, BTC-only Challenge+Verification in ≤60 days at FTMO 5%/10% DD remains **blocked** — robust edges too slow; session/HF books lack edge or blow DD. Prefer C5/C10 multi-month robustness or diversify beyond BTC-only. Do not deploy C13.

## Live

Do not touch live VM, MetaAPI, C4, drip, FREEZE_NEW_BUYS, or arm anything.
