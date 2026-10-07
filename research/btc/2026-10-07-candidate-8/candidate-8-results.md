# Candidate 8 Results — Filtered SMA50 Dual R=2 (catalogue stop)

**Decision: REJECT**

**One sentence:** REJECT C8 as ≤60d vehicle: HO@0.01 $-6,769.75 (~$-694/mo); @1% risk pace ~$-1,033/mo; 60d windows 0/252; max DD 19.07%.

**Measured:** 2026-10-07 09:08:11 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**Spec:** `/workspace/btc-strategies/ftmo-candidate-8.md`

## ASSUMPTIONS (labeled)

| Item | Value |
|---|---|
| Account | $100,000 2-step (ASSUMPTION) |
| Challenge / Verification | +10% / +5% |
| Pace bar | ≤60 calendar days both steps |
| Daily / Max DD | 5% / 10% |
| Primary stop / target | 412.91 / 825.82 (R=2) |
| Filters | C5 slope E + ATR < P75(100d) |
| Risk per trade (Gate B) | 1.0% equity / stop |
| Daily kill | −3% realized Prague day |
| Cost model | C4/C5: 0.065%/side + swap est −30%/360 |
| Data | Merged Dukas M1 bid main+ext |

## vs C1 (a priori difference)

| | C1 | C8 primary |
|---|---|---|
| Stop | 825.82 | **412.91** |
| Target / R | 2477.46 / R=3 | **825.82 / R=2** |
| Filters | none | **slope + V75** |

## Gate A — robustness @ catalogue 0.01 (R=2)

| Gate | Pass? | Detail |
|---|---|---|
| 1 Holdout >0 & > buy-only | NO | HO $-6,769.75; buy-only $-8,258.20 |
| 2 Extension ≥ 0 | YES | Ext $1,624.48 |
| 3 Leave-out two best HO months > 0 | NO | removed ['2025-12', '2025-11']; left $-8,810.87 |
| 4 Worst ET day ≥ −$2k HO&ext | YES | HO ('2025-12-21', Decimal('-825.82')); ext ('2026-09-13', Decimal('-825.82')) |
| 5 Fit ≥ −$5k | NO | Fit $-10,252.76 |
| 6 HO months ≥50% green | NO | 4/11 (36.4%) |

**Gate A all pass?** NO

- Trades HO L/S: 59/107; WR 30.1%
- Pace @0.01: **$-693.84/mo** over 297 calendar days
- Filter skips fit/HO: 333/102 (slope≈177/63, vol≈156/39)

### HO monthly P&L @0.01 (ET exit month)

| ET exit month | Trades | Net full $ |
|---|---:|---:|
| 2025-11 | 1 | 824.65 |
| 2025-12 | 18 | 1,216.46 |
| 2026-01 | 12 | -1,252.56 |
| 2026-02 | 15 | -13.51 |
| 2026-03 | 23 | -4,563.17 |
| 2026-04 | 24 | -23.67 |
| 2026-05 | 20 | -846.30 |
| 2026-06 | 24 | -2,496.96 |
| 2026-07 | 11 | 402.86 |
| 2026-08 | 17 | 396.36 |
| 2026-09 | 1 | -413.93 |

## Gate B — ≤60-day vehicle @ 1.0% risk (R=2)

| Gate | Pass? | Detail |
|---|---|---|
| 7 ≥1 clean 60d window | NO | **0 / 252** windows |
| 8 Pace ≥$7.5k/mo OR Gate 7 | NO | HO pace $-1,032.94/mo |
| 9 Stop+worst day ≤$5k; DD≤10% | NO | mean stop $924.69; worst day $-1,656.54; DD 19.07% |
| 4b No −5% Prague days | YES | worst 2026-01-19 -1.66%; fail-days=0 |

**Gate B all pass?** NO

- Equity trades: 71 (L/S 3/68); wins/losses 20/51
- Final equity: $89,921.69 (net $-10,078.31)
- Fit/HO/Ext equity nets: $0.00 / $-10,078.31 / $0.00
- Killed Prague days: 0

### 60-day pass windows (sample)

_None._

### Risk scale table (linear $ from 1.0% base; DD% ~scale-invariant for fractional risk)

| Risk% | HO $/mo | Worst day $ | Mean stop $ | Est days both +$15k | Daily $ OK |
|---:|---:|---:|---:|---:|:---:|
| 0.50 | -516.47 | -828.27 | 462.34 | inf | Y |
| 0.75 | -774.71 | -1,242.40 | 693.51 | inf | Y |
| 1.00 | -1,032.94 | -1,656.54 | 924.69 | inf | Y |
| 1.25 | -1,291.18 | -2,070.67 | 1,155.86 | inf | Y |
| 1.50 | -1,549.41 | -2,484.81 | 1,387.03 | inf | Y |

## Diagnostic — R=3 (same filters/stop; not a new candidate)

- Catalogue 0.01: fit $-18,094.40; HO $-6,355.01 (~$-651/mo); ext $799.02
- Leave-out removed ['2026-07', '2025-11'] → $-9,647.09
- HO WR 22.6%; trades 159
- Equity @1%: HO pace ~$-1,073.53/mo; max DD 19.14%; 60d passes **0/252**; worst day 2026-01-19 -1.71%

## Comparison vs C5 / C7

| | C5 @0.01 R=1 | C7 @0.75% R=1 | C8 @0.01 R=2 | C8 @1% R=2 |
|---|---:|---:|---:|---:|
| HO $/mo | ~491 | ~508 | -694 | -1,033 |
| ≤60d windows | n/a (slow) | 0/896 | n/a | **0/252** |
| Max DD | low @0.01 | 17.39% | low @0.01 | 19.07% |
| Leave-out @0.01 | +$707 | fail | $-8,811 | — |

## Decision

**REJECT** — C8 is research-only. Not deployable live from this folder.

### Binding constraint

**Primary binding: EDGE (not DD first).** Raising R on the C5 SMA50 dual destroys expectancy:

| | C5 R=1 | C8 R=2 | C8 R=3 (diag) |
|---|---:|---:|---:|
| HO win rate | 53.5% | **30.1%** | 22.6% |
| Breakeven WR (R:1) | 50% | 33.3% | 25% |
| HO net @0.01 | +$4,790 | **−$6,770** | −$6,355 |
| Fit @0.01 | −$3,214 | −$10,253 | −$18,094 |

WR falls faster than R rises → negative EV. Same pattern without filters (nofilt R=2 HO ~−$6.1k). vs C1: filters + smaller stop do **not** rescue higher-R on this setup.

Secondary: at 1% risk, max DD **19.07%** (>10%) and **0/252** ≤60d windows — but those follow from negative edge, not from “need more size.”

**Binding: edge.** (DD/pace fail as consequence.)

## Live

Do not arm. Do not touch C4 / drip / FREEZE / MetaAPI / live VM.

## Research-next?

**YES** — need a structure where winners can run **without** requiring a far hard TP that collapses hit-rate on daily SMA50 dual (e.g. ATR trail / time-stop / different entry). Do **not** re-run SMA50 dual at R=2/R=3 as C9.
