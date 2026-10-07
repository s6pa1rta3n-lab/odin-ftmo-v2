## Candidate 8 — Filtered SMA50 Dual R=2 — REJECT as ≤60d vehicle

**Decision: REJECT** (binding: **edge**)

### Thesis
C7 showed more trades + hard R=1 still ~$0.5k/mo (winners capped). C8 keeps C5’s SMA50 exclusive dual + slope + ATR&lt;P75, keeps catalogue **stop=412.91**, raises **target to R=2** (diag R=3). vs C1: smaller stop + filters (C1 was stop=825.82 R=3, no filters, leave-out fail).

Cost model: **C4/C5** 0.065%/side + swap est (not FTMO spread=15).

### Measured (Dukas M1 merged; 2026-10-07)

| Metric | R=2 primary | R=3 diagnostic |
|---|---:|---:|
| HO @0.01 | **−$6,770** (~−$694/mo) | −$6,355 |
| HO win rate | **30.1%** (need &gt;33% for R=2) | 22.6% |
| Extension @0.01 | +$1,624 | +$799 |
| Fit @0.01 | −$10,253 | −$18,094 |
| Leave-out | −$8,811 **FAIL** | −$9,647 **FAIL** |
| @1% risk HO pace | ~−$1,033/mo | ~−$1,074/mo |
| ≤60d pass windows | **0 / 252** | **0 / 252** |
| Max DD @1% | 19.07% | 19.14% |
| Worst Prague day @1% | −1.66% | −1.71% |

### vs C5 / C7
- C5 R=1 @0.01: +$4,790 HO, WR 53.5%, leave-out +$707 — robust but too slow
- C7 H4 R=1: ~$508/mo, 0/896 windows, DD 17%
- C8: raising R collapses WR faster than payoff rises → **negative edge**; not a size problem

### Live
Research only. **Do not deploy / arm.** C4 / drip / FREEZE / MetaAPI untouched.

### Files
`research/btc/2026-10-07-candidate-8/`
