# Candidate 7 Results — H4-BREAK Dual R=1 + SMA50 Regime + 0.75% Risk + Daily Kill

**Decision: REJECT**

**One sentence:** REJECT C7 as ≤60-day FTMO vehicle: HO $4,952.03 (~$507.54/mo); 60d pass windows 0/896; max DD 17.39%; worst day -1.82%.

**Measured:** 2026-10-07 09:01:30 EDT
**Live engines:** not modified. C4/drip/FREEZE untouched.
**Spec:** `/workspace/btc-strategies/ftmo-candidate-7.md`

## ASSUMPTIONS (labeled)

| Item | Value |
|---|---|
| Account | $100,000 2-step (ASSUMPTION) |
| Challenge / Verification | +10% / +5% |
| Pace bar | ≤60 calendar days both steps |
| Daily / Max DD | 5% / 10% |
| Risk per trade | 0.75% equity / stop_dist |
| Stop / Target | 1.0× H4 ATR(14) / R=1 |
| Cost model | FTMO spread=15 × lots; commission 0; swap 0 |
| Data | Merged Dukas M1 bid main+ext |

## Rules used

- H4 6-bar high/low break; exclusive dual via prior-day SMA50 regime
- Hard R=1 TP (no channel exit); stop = 1.0× ATR14 H4
- Size round(equity×0.0075/stop_dist, 2); max 1 position
- Prague-day realized kill at −3%; same-minute double touch → stop

## Run meta

- Signals: 1095; taken: 467; long/short: 260/207
- Wins/losses: 247/220
- Skips: regime=529 kill=0 lots=0 stop=0 in_trade=99
- Killed Prague days: 0
- Final equity: $112,278.08 (net $12,278.08)
- Mean planned stop $: $817.69

## Gate A — robustness

| Gate | Pass? | Detail |
|---|---|---|
| 1 Holdout net > 0 | YES | HO $4,952.03 |
| 2 Extension net ≥ 0 | YES | Ext $2,961.59 |
| 3 Leave-out two best HO months > 0 | NO | removed ['2025-11', '2026-01']; left $-1,198.57 |
| 4 Worst Prague day > −5%; 0 days ≤ −5% | YES | worst 2025-09-29 -1.82%; fail-days=0 |
| 5 Max realized DD ≤ 10% | NO | 17.39% |
| 6 Fit net ≥ −$10,000 | YES | Fit $4,364.45 |

**Gate A all pass?** NO

## Gate B — ≤60-day fast vehicle

| Gate | Pass? | Detail |
|---|---|---|
| 7 ≥1 clean 60d window (1.10 then 1.155, floor, no −5% day) | NO | 0 / 896 windows |
| 8 Pace ≥$7.5k/mo OR Gate 7 | NO | HO pace $507.54/mo |
| 9 Stop + worst day ≤ $5k; DD ≤10% | NO | stop~$817.69; worst day $-1,841.71; DD 17.39% |

**Gate B all pass?** NO

## 60-day pass windows (sample)

_None._

## HO monthly P&L (ET exit month)

| ET exit month | Trades | Net $ |
|---|---:|---:|
| 2025-11 | 11 | 3,859.14 |
| 2025-12 | 12 | 1,456.87 |
| 2026-01 | 13 | 2,291.46 |
| 2026-02 | 16 | -207.65 |
| 2026-03 | 14 | -207.61 |
| 2026-04 | 17 | -274.45 |
| 2026-05 | 12 | -219.59 |
| 2026-06 | 19 | -1,149.06 |
| 2026-07 | 12 | -1,900.57 |
| 2026-08 | 16 | 1,303.49 |

## Risk scale table (linear $ from 0.75% base run)

| Risk% | HO $/mo | Worst day $ | Mean stop $ | Est days both +$15k | Daily $ OK |
|---:|---:|---:|---:|---:|:---:|
| 0.25 | 169.18 | -613.90 | 272.56 | 2698.9 | Y |
| 0.50 | 338.36 | -1,227.81 | 545.12 | 1349.4 | Y |
| 0.75 | 507.54 | -1,841.71 | 817.69 | 899.6 | Y |
| 1.00 | 676.72 | -2,455.61 | 1,090.25 | 674.7 | Y |
| 1.50 | 1,015.08 | -3,683.42 | 1,635.37 | 449.8 | Y |

## Diagnostic ablation — 0.50% risk (not a new candidate)

- Trades: 467; final equity $108,346.53
- HO net: $3,348.81; max DD 11.91%
- Worst day: 2025-09-29 -1.21%
- 60d pass windows: 0 / 896

## Comparison vs C5 / C6

| | C5 @ 0.01 | C6 max DD-safe | C7 @ 0.75% |
|---|---:|---:|---:|
| HO $/mo | ~491 | ~2,973 | 507.54 |
| ≤60d both | NO | NO (~154d) | NO (0 windows) |
| Max DD | low @0.01 | scaled | 17.39% |
| Structure | daily SMA R=1 | scale C5 | H4 break dual R=1 |

## Decision

**REJECT** — C7 is research-only. Not deployable live from this folder.

### Best near-miss / why it fails Odin’s ≤60d bar

- **What worked partially:** Fit/HO/extension all net **positive** after spread costs; worst Prague day only **−1.82%** (daily DD path OK at 0.75%); 467 trades (~higher frequency than C5’s ~1/day).
- **What killed it:**
  1. **Pace still ~C5-slow:** HO ~**$508/mo** at 0.75% risk — R=1 TP cut the open-ended winners that made H4-BREAK-6 interesting; dollars/month never approached ~$7.5k.
  2. **Max realized DD 17.39%** (>10%) — leave-out also fails (HO depends on two best months).
  3. **0 / 896** clean ≤60d Challenge+Verification windows.
  4. Linear scale table: even **1.5% risk** ≈ **$1.0k/mo** / ~450 days for both steps; hitting $7.5k/mo would need ~**11% risk/trade** → illegal vs 5% daily.
- **vs H4-BREAK-6:** A priori DD “fixes” (dual+R=1+0.75%+1.0 ATR) removed the floating −6.9% day and worst-day% is fine, but also removed the profit engine — **no free lunch**.
- **Ablation 0.50%:** DD improves to 11.91% (still >10%), still **0** 60d passes, slower dollars.
- **Deployable as research-next?** **NO** for live/arm. Useful only as documented wall: H4-break + hard R=1 at DD-legal risk ≠ ≤60d vehicle.

## Live

Do not arm. Do not touch C4 / drip / FREEZE / MetaAPI / live VM.
