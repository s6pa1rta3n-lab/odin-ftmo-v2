# Candidate 10 Results — C5 Entry + R-Multiple Trail (1.0×R)

**Decision: CONDITIONAL**

**One sentence:** CONDITIONAL C10 as ≤60d vehicle: R-trail **engaged** (87 trail-stops); HO @0.01 +$4,394 (~$450/mo); fit +$2,979; @1% 0/252 windows DD 14.7%; @0.5% DD OK but 0 windows. Binding: **PACE+DD**. Recommend **C11 different entry chassis** — SMA50 dual exit milking exhausted.

**Measured:** 2026-10-07 09:14:26 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**Spec:** `/workspace/btc-strategies/ftmo-candidate-10.md`

## Locked R-trail rule (a priori)

| Step | Rule |
|---|---|
| Entry | C5: SMA50 exclusive dual + slope E + ATR < P75(100d); 00:00 UTC; max 1 |
| Initial SL | entry ± 412.91 |
| Activation | first +1R favorable touch → SL = entry (BE) |
| Trail | after BE: **1.0×R (412.91)** behind favorable extreme (long: HH−412.91; short: LL+412.91); never widen. NOT ATR. |
| Hard TP | emergency only at +5R (2064.55); not thesis payoff |
| Cost | C4/C5 0.065%/side + swap est −30%/360 |

## ASSUMPTIONS (labeled)

| Item | Value |
|---|---|
| Account | $100,000 2-step (ASSUMPTION) |
| Challenge / Verification | +10% / +5% |
| Pace bar | ≤60 calendar days both steps |
| Daily / Max DD | 5% / 10% |
| Trail distance | **1.0×R = 412.91** a priori (not tuned); R-multiple, not ATR |
| Filters | C5 slope E + ATR < P75(100d) |
| Risk Gate B | 1.0% equity / initial stop (also 0.5%) |
| Daily kill | −3% realized Prague day |
| Data | Merged Dukas M1 bid main+ext |

## Gate A — robustness @ catalogue 0.01

| Gate | Pass? | Detail |
|---|---|---|
| 1 Holdout >0 & > buy-only | YES | HO $4,393.60; buy-only $-8,258.20 |
| 2 Extension ≥ 0 | YES | Ext $3,143.16 |
| 3 Leave-out two best HO months > 0 | YES | removed ['2026-04', '2025-11']; left $8.72 |
| 4 Worst ET day ≥ −$2k HO&ext | YES | HO ('2025-12-30', Decimal('-825.82')); ext ('2026-09-13', Decimal('-825.82')) |
| 5 Fit ≥ −$5k | YES | Fit $2,979.49 |
| 6 HO months ≥50% green | YES | 7/11 (63.6%) |

**Gate A all pass?** YES

- Trades HO L/S: 61/111; WR 53.5%
- Avg win / avg loss raw: $408.60 / $-412.91
- Avg max favorable R: 1.24; activated 92/172
- Avg raw R on activated winners: 0.99R (92 trades)
- Exit reasons HO: {'emergency-tp': 2, 'trail-stop': 87, 'init-stop': 80, 'gap-stop': 3}
- Pace @0.01: **$450.31/mo** over 297 calendar days
- Filter skips fit/HO: 333/102 (slope≈177/63, vol≈156/39)

### HO monthly P&L @0.01 (ET exit month)

| ET exit month | Trades | Net full $ |
|---|---:|---:|
| 2025-11 | 1 | 2,063.39 |
| 2025-12 | 20 | 1,219.40 |
| 2026-01 | 12 | 349.26 |
| 2026-02 | 15 | -45.76 |
| 2026-03 | 25 | -2,641.82 |
| 2026-04 | 24 | 2,321.49 |
| 2026-05 | 20 | -404.07 |
| 2026-06 | 24 | 1,258.78 |
| 2026-07 | 12 | -100.36 |
| 2026-08 | 18 | 120.31 |
| 2026-09 | 1 | 252.97 |

## Gate B — ≤60-day vehicle @ 1.0% risk (R-trail)

| Gate | Pass? | Detail |
|---|---|---|
| 7 ≥1 clean 60d window | NO | **0 / 252** windows |
| 8 Pace ≥$7.5k/mo OR Gate 7 | NO | HO pace $744.54/mo |
| 9 Stop+worst day ≤$5k; DD≤10% | NO | mean stop $1,105.33; worst day $-2,070.68; DD 14.7% |
| 4b No −5% Prague days | YES | worst 2026-01-19 -2.0%; fail-days=0 |

**Gate B all pass?** NO

- Equity trades: 195 (L/S 84/111)
- Wins/losses: 104/91
- Final equity: $116,693.86 (net $16,693.86)
- HO/Ext equity nets: $7,264.38 / $9,429.48
- Killed Prague days: 0

### 60-day pass windows (sample)

_None._

### 0.5% risk path

- HO pace $450.31/mo; max DD 5.6%; 60d passes **0/252**; final $107,536.76

## Diagnostic — R-trail without C5 filters (not a new candidate)

- Catalogue 0.01 HO: $2,511.44 (~$257.40/mo); WR 53.3%; n=261; activated 140
- Reasons: {'trail-stop': 132, 'init-stop': 120, 'gap-stop': 7, 'emergency-tp': 2}

## Comparison vs C5 / C9

| | C5 @0.01 R=1 | C9 @0.01 ATR-trail | C10 @0.01 R-trail | C10 @1% R-trail |
|---|---:|---:|---:|---:|
| HO $/mo | ~491 | ~660 | **450.31** | **744.54** |
| HO net | +$4,790 | +$6,444 | **$4,393.60** | $7,264.38 |
| HO WR | 53.5% | 11.6% | **53.5%** | — |
| Fit @0.01 | −$3,214 | −$830 | **$2,979.49** | — |
| Leave-out | +$707 | +$286 | **$8.72** | — |
| ≤60d @1% | n/a (slow) | 65/252 (DD 18.5%) | n/a | **0/252** |
| Max DD | low @0.01 | 18.5%@1% | low @0.01 | **14.7%** |

## Decision

**CONDITIONAL** — C10 is research-only. Not deployable live from this folder.

### Binding constraint

**Primary binding: PACE + DD (Gate B).** R-trail **did engage** (87 trail-stop exits on HO vs C9’s 0), but:

| Risk | HO $/mo | Max DD | ≤60d windows |
|---:|---:|---:|---:|
| 0.01 lot | ~$450 | low | n/a |
| 0.5% equity | ~$450 | **5.6%** ✓ | **0/252** |
| 1.0% equity | ~$745 | **14.7%** ✗ | **0/252** |

No DD-legal size clears ≤60d. @1% still has **0** windows (C9 had 65/252 because emergency +5R winners created equity spikes C10’s tight trail cuts off). Fit improved sharply (+$2,979 vs C5 −$3.2k / C9 −$830) — R-trail is the best *robustness* exit on this chassis, still not a fast-pass vehicle.

**Trail mechanics note:** Fixed 1.0×R behind extreme left BE and produced **87 trail-stops** + only **2** emergency +5R. Avg win raw ≈ $409 ≈ 1R (trail clips runners near +1R after BE). Contrast C9: 0 trail-stops, 19× +5R, WR 11.6%.

- Est. calendar days to +$15k @1% pace: **613** (bar ≤60) — and that pace is DD-illegal.

## Live

Do not arm. Do not touch C4 / drip / FREEZE / MetaAPI / live VM.

## Research-next?

**YES — recommend different entry chassis as C11.** R-trail on SMA50 dual still DD-bound or too slow for ≤60d at legal risk. Do **not** keep milking SMA50 dual exits (no more trail k / BE variants). Do not re-run hard R=2/R=3.
