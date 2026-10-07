## Candidate 10 — C5 Entry + R-Multiple Trail (1.0×R) — CONDITIONAL (PACE+DD)

**Decision: CONDITIONAL** (binding: **PACE + DD**)

### Thesis (locked a priori)
Keep C5 entry (SMA50 exclusive dual + slope E + ATR&lt;P75), initial stop **412.91**, BE at **+1R**, then trail by **1.0×R (412.91) behind favorable extreme** (long: HH−412.91; short: LL+412.91; never widen). Emergency hard TP only at **+5R**. Explicitly **not** ATR trail (C9) and **not** hard R=2/R=3 (C8).

Cost model: **C4/C5** 0.065%/side + swap est.

### Measured (Dukas M1 merged; 2026-10-07 EDT)

| Metric | @0.01 | @0.5% risk | @1.0% risk |
|---|---:|---:|---:|
| HO net / pace | **+$4,394** / ~$450/mo | ~$450/mo | ~$745/mo |
| Fit / leave-out / ext | **+$2,979** / +$9 / +$3,143 | — | — |
| HO WR | 53.5% | — | — |
| Exit mix HO | 87 trail-stop / 80 init / 2 emergency+5R | — | — |
| ≤60d pass windows | n/a | **0 / 252** | **0 / 252** |
| Max DD | low | **5.6%** | **14.7%** |

Gate A (robustness @0.01): **PASS** (all 6; fit best of C5/C9/C10).  
Gate B (≤60d @1%): **FAIL** — 0 windows; DD &gt; 10%; DD-legal 0.5% also 0 windows.

### Trail note
R-trail **did engage** (87 trail-stops vs C9’s 0). Avg win ≈ 1R — trail clips runners that C9’s BE-or-+5R captured as emergency +5R. Better fit/robustness; worse ≤60d pace spikes.

### vs C5 / C9
- C5 R=1: +$4.8k HO, WR 53.5%, slow — C10 similar $/mo, **much better fit** (+$3.0k vs −$3.2k)
- C9 ATR trail: +$6.4k HO, 65/252@1% but DD 18.5%; trail never left BE — C10 trail works but **0** ≤60d windows

### Research-next
**Recommend C11 different entry chassis.** SMA50 dual exit milking exhausted (C8 hard R, C9 ATR trail, C10 R-trail). Do **not** re-run hard R=2/R=3 or more trail-k variants on this entry.

### Live
Research only. **Do not deploy / arm.** C4 / drip / FREEZE / MetaAPI untouched.

### Files
`research/btc/2026-10-07-candidate-10/`
