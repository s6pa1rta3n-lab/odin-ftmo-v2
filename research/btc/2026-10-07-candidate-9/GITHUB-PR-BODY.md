## Candidate 9 — C5 Entry + ATR Trail Runner — CONDITIONAL (DD wall)

**Decision: CONDITIONAL** (binding: **DD**)

### Thesis (locked a priori)
Keep C5 entry (SMA50 exclusive dual + slope E + ATR&lt;P75), initial stop **412.91**, replace hard TP with trail runner: **BE at +1R**, then trail by prior-day **ATR(14)×k=1.0**; emergency hard TP only at **+5R**. Explicitly **not** hard R=2/R=3 (C8 REJECT).

Cost model: **C4/C5** 0.065%/side + swap est.

### Measured (Dukas M1 merged; 2026-10-07 EDT)

| Metric | @0.01 | @0.5% risk | @1.0% risk |
|---|---:|---:|---:|
| HO net / pace | **+$6,444** / ~$660/mo | ~$660/mo | ~$1,770/mo |
| Fit / leave-out / ext | −$830 / +$286 / +$1,625 | — | — |
| HO WR | 11.6% (19× +5R) | — | — |
| ≤60d pass windows | n/a | **0 / 252** | **65 / 252** |
| Max DD | low | **7.4%** | **18.5%** |

Gate A (robustness @0.01): **PASS** (all 6).  
Gate B (≤60d @1%): **FAIL** — windows exist but DD &gt; 10%; DD-legal 0.5% has 0 windows.

### Trail note
BTC ATR(14) ≫ 412 stop → after BE, ATR trail **never ratcheted** (0 trail-stop exits). Realized path ≈ BE-or-+5R.

### vs C5 / C8
- C5 R=1: +$4.8k HO, WR 53.5%, slow — C9 faster $/mo and better fit, still not ≤60d-legal
- C8 hard R=2: −$6.8k HO — C9 avoids that edge destruction

### Live
Research only. **Do not deploy / arm.** C4 / drip / FREEZE / MetaAPI untouched.

### Files
`research/btc/2026-10-07-candidate-9/`
