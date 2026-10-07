# Candidate 9 Results — C5 Entry + ATR Trail Runner

**Decision: CONDITIONAL**

**One sentence:** CONDITIONAL C9 as ≤60d vehicle: Gate A PASS @0.01 (HO +$6,444 ~$660/mo; fit −$830); @1% has 65/252 ≤60d windows but max DD **18.5%** (>10%); @0.5% DD 7.4% but **0/252** windows. Binding: **DD** (size for ≤60d illegal).

**Measured:** 2026-10-07 09:11:23 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**Spec:** `/workspace/btc-strategies/ftmo-candidate-9.md`

## Locked trail rule (a priori)

| Step | Rule |
|---|---|
| Entry | C5: SMA50 exclusive dual + slope E + ATR < P75(100d); 00:00 UTC; max 1 |
| Initial SL | entry ± 412.91 |
| Activation | first +1R favorable touch → SL = entry (BE) |
| Trail | after BE: ratchet SL from bar.close by prior-day ATR(14)×**k=1.0** |
| Hard TP | emergency only at +5R (2064.55); not thesis payoff |
| Cost | C4/C5 0.065%/side + swap est −30%/360 |

## ASSUMPTIONS (labeled)

| Item | Value |
|---|---|
| Account | $100,000 2-step (ASSUMPTION) |
| Challenge / Verification | +10% / +5% |
| Pace bar | ≤60 calendar days both steps |
| Daily / Max DD | 5% / 10% |
| Trail k | **1.0** a priori (not tuned) |
| Filters | C5 slope E + ATR < P75(100d) |
| Risk Gate B | 1.0% equity / initial stop (also 0.5%) |
| Daily kill | −3% realized Prague day |
| Data | Merged Dukas M1 bid main+ext |

## Gate A — robustness @ catalogue 0.01

| Gate | Pass? | Detail |
|---|---|---|
| 1 Holdout >0 & > buy-only | YES | HO $6,443.55; buy-only $-8,258.20 |
| 2 Extension ≥ 0 | YES | Ext $1,624.70 |
| 3 Leave-out two best HO months > 0 | YES | removed ['2026-01', '2025-12']; left $286.39 |
| 4 Worst ET day ≥ −$2k HO&ext | YES | HO ('2025-12-30', Decimal('-825.82')); ext ('2026-09-13', Decimal('-825.82')) |
| 5 Fit ≥ −$5k | YES | Fit $-830.07 |
| 6 HO months ≥50% green | YES | 7/11 (63.6%) |

**Gate A all pass?** YES

- Trades HO L/S: 55/109; WR 11.6%
- Avg win / avg loss raw: $2,064.55 / $-412.91
- Avg max favorable R: 1.51; activated 85/164
- Avg raw R on activated winners: 5.00R (19 trades)
- Exit reasons HO: {'emergency-tp': 19, 'be-stop': 66, 'init-stop': 79}
- Pace @0.01: **$660.41/mo** over 297 calendar days
- Filter skips fit/HO: 333/102 (slope≈177/63, vol≈156/39)

### HO monthly P&L @0.01 (ET exit month)

| ET exit month | Trades | Net full $ |
|---|---:|---:|
| 2025-11 | 1 | 2,063.39 |
| 2025-12 | 19 | 2,867.68 |
| 2026-01 | 12 | 3,289.48 |
| 2026-02 | 15 | 1,225.23 |
| 2026-03 | 25 | -3,738.57 |
| 2026-04 | 22 | 391.15 |
| 2026-05 | 18 | 2,457.09 |
| 2026-06 | 24 | -432.40 |
| 2026-07 | 11 | -2,487.54 |
| 2026-08 | 16 | 809.06 |
| 2026-09 | 1 | -1.02 |

## Gate B — ≤60-day vehicle @ 1.0% risk

| Gate | Pass? | Detail |
|---|---|---|
| 7 ≥1 clean 60d window | YES | **65 / 252** windows |
| 8 Pace ≥$7.5k/mo OR Gate 7 | YES | HO pace $1,769.75/mo |
| 9 Stop+worst day ≤$5k; DD≤10% | NO | mean stop $1,236.51; worst day $-2,484.81; DD 18.5% |
| 4b No −5% Prague days | YES | worst 2026-01-19 -2.3%; fail-days=0 |

**Gate B all pass?** NO

- Equity trades: 186 (L/S 77/109)
- Wins/losses: 22/164
- Final equity: $122,141.36 (net $22,141.36)
- HO/Ext equity nets: $17,267.26 / $4,874.10
- Killed Prague days: 0

### 60-day pass windows (sample)

| start | end | start_eq | max_mult | min_mult | worst_day |
|---|---|---:|---:|---:|---:|
| 2025-12-01 | 2026-01-29 | 100000 | 1.189 | 1.041 | -2.28% |
| 2025-12-03 | 2026-01-31 | 104127 | 1.189 | 1.000 | -2.28% |
| 2025-12-04 | 2026-02-01 | 104127 | 1.189 | 1.000 | -2.28% |
| 2025-12-05 | 2026-02-02 | 104127 | 1.189 | 1.000 | -2.28% |
| 2025-12-06 | 2026-02-03 | 104127 | 1.189 | 1.000 | -2.28% |
| 2025-12-07 | 2026-02-04 | 104127 | 1.189 | 1.000 | -2.28% |
| 2025-12-08 | 2026-02-05 | 104127 | 1.189 | 1.000 | -2.28% |
| 2025-12-09 | 2026-02-06 | 104127 | 1.189 | 1.000 | -2.28% |
| 2025-12-10 | 2026-02-07 | 104123 | 1.189 | 1.000 | -2.28% |
| 2025-12-11 | 2026-02-08 | 104120 | 1.189 | 1.011 | -2.28% |

### 0.5% risk path

- HO pace $660.41/mo; max DD 7.4%; 60d passes **0/252**; final $108,068.25

## Diagnostic — trail without C5 filters (not a new candidate)

- Catalogue 0.01 HO: $8,399.37 (~$860.86/mo); WR 11.2%; n=250; activated 131
- Reasons: {'be-stop': 102, 'init-stop': 118, 'emergency-tp': 28, 'gap-stop': 2}

## Comparison vs C5 / C8

| | C5 @0.01 R=1 | C8 @0.01 R=2 | C9 @0.01 trail | C9 @1% trail |
|---|---:|---:|---:|---:|
| HO $/mo | ~491 | -694 | **660.41** | **1,769.75** |
| HO net | +$4,790 | −$6,770 | **$6,443.55** | $17,267.26 |
| HO WR | 53.5% | 30.1% | **11.6%** | — |
| Fit @0.01 | −$3,214 | −$10,253 | **$-830.07** | — |
| Leave-out | +$707 | −$8,811 | **$286.39** | — |
| ≤60d windows | n/a (slow) | 0/252 | n/a | **65/252** |
| Max DD | low @0.01 | 19.07%@1% | low @0.01 | **18.5%** |

## Decision

**CONDITIONAL** — C9 is research-only. Not deployable live from this folder.

### Binding constraint

**Primary binding: DD (not edge).** Trail + emergency +5R creates real positive expectancy and even ≤60d *equity* hits at 1% risk — but:

| Risk | HO $/mo | Max DD | ≤60d windows |
|---:|---:|---:|---:|
| 0.01 lot | ~$660 | low | n/a |
| 0.5% equity | ~$660 | **7.4%** ✓ | **0/252** |
| 1.0% equity | ~$1,770 | **18.5%** ✗ | **65/252** |

No DD-legal size clears ≤60d. Same wall family as C6 (need illegal size for pace).

**Trail mechanics note (a priori k=1.0):** BTC daily ATR(14) ≫ 412.91 stop, so after BE the ATR trail **never ratcheted above BE** on HO (0 trail-stop exits). Realized winners = **19 emergency +5R** hits; 66 returned to BE; 79 init-stops. Effectively “C5 entry → BE at +1R → hold for +5R or BE,” not a tight ATR runner.

- Est. calendar days to +$15k @1% pace: **258** (bar ≤60) — and that pace is DD-illegal.

## Live

Do not arm. Do not touch C4 / drip / FREEZE / MetaAPI / live VM.

## Research-next?

**YES** — C9 improves on C5/C8 (fit cleared; HO +$6.4k; hard R=2 avoided) but **cannot** be a ≤60d FTMO vehicle at legal DD.

Suggested next (pick **one** a priori):
1. **Different entry chassis** (higher trade frequency / stronger edge) — SMA50 dual pace ceiling keeps recurring; or
2. **R-multiple trail** (e.g. trail by 0.5R after BE) — because ATR×1.0 never left BE on BTC; still one locked k, not a grid search; or
3. Do **not** re-run SMA50 dual hard R=2/R=3 (C8).
