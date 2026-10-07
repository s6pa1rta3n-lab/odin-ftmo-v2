# Candidate 12 Results — Multi-Position C5 Stack (N=3, 2% Agg Cap)

**Decision: REJECT**

**One sentence:** REJECT C12 as ≤60d vehicle: 0 clean 60d windows on DD-legal configs ['A', 'B', 'C']. A pace=448/mo DD=9.1%; B pace=448/mo DD=9.1% 60d=0/850; C pace=491/mo DD=8.8%.

**STRUCTURAL FINDING:** BTC-only Challenge+Verification in ≤60 days at FTMO 5%/10% DD appears **structurally implausible** on measured C5–C12 + prior survey (robust edges too slow; HF no edge; size/stack hits DD wall).

**Measured:** 2026-10-07 09:20:58 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**Spec:** `/workspace/btc-strategies/ftmo-candidate-12.md`

## Locked thesis

| Item | Value |
|---|---|
| Signal | C5: SMA50 exclusive dual + slope E + ATR < P75(100d) |
| Entry | 00:00 UTC M1 open when signal fires |
| Exit | hard R=1 stop=target=**412.91** (NOT R=2/3, NOT trail) |
| Max concurrent | **3** same regime direction (a priori; never hedged) |
| Per-ticket risk | 0.5% equity (B/C) or flat 0.01 lots (A) |
| Aggregate open risk | sum remaining stop $ ≤ **2.0%** equity |
| Prague kill | no new ≤ −3%; flatten all ≤ −4% |
| Cost | C4/C5 0.065%/side + swap est −30%/360 |
| Account | $100,000 2-step (ASSUMPTION) |
| Pass bar | +10% then +15% in ≤60d without −5% day / −10% trough |


## Measurement notes (post-hoc, not re-tuned)

1. **Config B ≡ A near $100k:** 0.5% of $100k = $500; STOP=$412.91 → scale≈1.21×; lot grid rounds to **0.01**. Needs ~$124k equity before 0.02 lots. So B collapses to catalogue 0.01 on this path.
2. **Max concurrent observed = 2** (N=3 never filled): C5 R=1 usually resolves before the next filter-passing midnight; stacking rarely queues a 2nd ticket and never a 3rd on this sample.
3. **Stack did not help pace:** A/B HO **$448/mo** vs C (single) **$491/mo** — the extra stacked trade(s) slightly hurt holdout/extension (ext A/B **−$28** vs C **+$386**).
4. **Config C matches C5 @0.01** exactly on fit/HO/leave-out/ext nets — sanity check passed.
5. **0/850** clean ≤60d windows on all three DD-legal configs (DD 8.8–9.1%, worst day ≈−0.85%).

## Config table

| Cfg | Mode | HO net | HO $/mo | Fit | Leave-out | Ext | Worst day % | Max DD | 60d passes | DD-legal? | Trades HO | Max concurrent |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| A | max 3 × 0.01 lots + 2% agg | $4,373.55 | $448.25 | $-2,392.06 | $290.68 | $-28.15 | -0.84% | 9.1% | **0/850** | YES | 173 | 2 |
| B | max 3 × 0.5%/ticket + 2% agg | $4,373.55 | $448.25 | $-2,392.06 | $290.68 | $-28.15 | -0.84% | 9.1% | **0/850** | YES | 173 | 2 |
| C | max 1 × 0.5% (scaled C5 single) | $4,790.18 | $490.95 | $-3,213.88 | $707.31 | $385.76 | -0.85% | 8.8% | **0/850** | YES | 172 | 1 |

## Config A detail — max 3 × 0.01 lots + 2% agg

- Entries full-range: 460; max concurrent: 2
- Skips HO: filter=102 (slope≈63, vol≈39); n_full=0; agg=0; side_mismatch=0; kill=0; flatten_events=0
- HO WR 53.2%; L/S 61/112; avg lots 0.01
- Leave-out removed ['2026-04', '2025-12'] → $290.68
- Final equity (full): $101,953.33 (net $1,953.33)
- Days to +15k at HO pace: 1,018.62 d
- −5% Prague fail-days: 0

### HO monthly P&L

| ET exit month | Trades | Net $ |
|---|---:|---:|
| 2025-11 | 1 | 411.74 |
| 2025-12 | 20 | 1,628.55 |
| 2026-01 | 12 | -839.64 |
| 2026-02 | 15 | 399.41 |
| 2026-03 | 25 | -1,261.09 |
| 2026-04 | 24 | 2,454.33 |
| 2026-05 | 20 | -20.49 |
| 2026-06 | 24 | 806.34 |
| 2026-07 | 13 | -426.97 |
| 2026-08 | 18 | 809.50 |
| 2026-09 | 1 | 411.89 |

### 60-day pass windows (sample ≤20)

_None._

## Config B detail — max 3 × 0.5%/ticket + 2% agg

- Entries full-range: 460; max concurrent: 2
- Skips HO: filter=102 (slope≈63, vol≈39); n_full=0; agg=0; side_mismatch=0; kill=0; flatten_events=0
- HO WR 53.2%; L/S 61/112; avg lots 0.01
- Leave-out removed ['2026-04', '2025-12'] → $290.68
- Final equity (full): $101,953.33 (net $1,953.33)
- Days to +15k at HO pace: 1,018.62 d
- −5% Prague fail-days: 0

### HO monthly P&L

| ET exit month | Trades | Net $ |
|---|---:|---:|
| 2025-11 | 1 | 411.74 |
| 2025-12 | 20 | 1,628.55 |
| 2026-01 | 12 | -839.64 |
| 2026-02 | 15 | 399.41 |
| 2026-03 | 25 | -1,261.09 |
| 2026-04 | 24 | 2,454.33 |
| 2026-05 | 20 | -20.49 |
| 2026-06 | 24 | 806.34 |
| 2026-07 | 13 | -426.97 |
| 2026-08 | 18 | 809.50 |
| 2026-09 | 1 | 411.89 |

### 60-day pass windows (sample ≤20)

_None._

## Config C detail — max 1 × 0.5% (scaled C5 single)

- Entries full-range: 454; max concurrent: 1
- Skips HO: filter=102 (slope≈63, vol≈39); n_full=1; agg=0; side_mismatch=0; kill=0; flatten_events=0
- HO WR 53.5%; L/S 61/111; avg lots 0.01
- Leave-out removed ['2026-04', '2025-12'] → $707.31
- Final equity (full): $101,962.06 (net $1,962.06)
- Days to +15k at HO pace: 930.03 d
- −5% Prague fail-days: 0

### HO monthly P&L

| ET exit month | Trades | Net $ |
|---|---:|---:|
| 2025-11 | 1 | 411.74 |
| 2025-12 | 20 | 1,628.55 |
| 2026-01 | 12 | -839.64 |
| 2026-02 | 15 | 399.41 |
| 2026-03 | 25 | -1,261.09 |
| 2026-04 | 24 | 2,454.33 |
| 2026-05 | 20 | -20.49 |
| 2026-06 | 24 | 806.34 |
| 2026-07 | 12 | -10.34 |
| 2026-08 | 18 | 809.50 |
| 2026-09 | 1 | 411.89 |

### 60-day pass windows (sample ≤20)

_None._

## Comparison vs C5 / C6 / C10

| | C5 @0.01 | C6 @legal ~0.06 | C10 @0.5% | C12-A | C12-B | C12-C |
|---|---:|---:|---:|---:|---:|---:|
| HO $/mo | ~491 | ~scaled | ~450 | **448.25** | **448.25** | **490.95** |
| ≤60d windows | 0 (slow) | 0 (DD wall) | 0/252 | **0/850** | **0/850** | **0/850** |
| Max DD | low | illegal at pace | 5.6%@0.5% | **9.1%** | **9.1%** | **8.8%** |

## Decision

**REJECT** — C12 is research-only. Not deployable live from this folder.

### Binding constraint

PACE+DD — stack cannot buy ≤60d at legal risk

### Structural implausibility (explicit)

**BTC-only Challenge + Verification in ≤60 days at FTMO 5% daily / 10% max DD appears structurally implausible** on the measured sample and rule set:

- **C5** research ACCEPT @0.01 (~$480–490/mo) — robust but ~2y for both steps
- **C6** C5 scale → REJECT (pace needs ~0.15 lots; DD wall; legal ~0.06 → ~5mo)
- **C7** H4 breakout R=1 → REJECT (DD ~17%, slow)
- **C8** hard R=2 on SMA50 → REJECT (edge flipped negative)
- **C9** ATR trail → CONDITIONAL (pace+DD; trail never left BE)
- **C10** R-trail → CONDITIONAL (0/252 windows @ legal; DD 14.7%@1%)
- **C11** H1 mom R=2 → REJECT (negative edge, DD 59.6%)
- **C12** multi-stack N=3 + 2% agg on C5 → **REJECT** (A 0/850, B 0/850, C 0/850 at DD-legal configs)

Prior survey: HF/breakout books either no edge or stop sizes blow DD.

### Honest slower path (not fake hope)

1. **C5 @ legal size (0.01–0.05)** — robustness book; expect many months, not ≤60d.
2. **C10 @ 0.5%** — best fit of SMA50 family; still 0 ≤60d windows; robustness only.
3. **Longer horizon** — target Challenge alone in ~4–6 months at legal risk, or accept that BTC-only 2-step ≤60d is not in the measured edge set.
4. **Do not** raise live risk / stack live C4 / deploy C5–C12 without separate approval.

## Research-next

Park BTC-only ≤60d hunt. Options for Ops/Odin: (a) run C5/C10 robustness at legal size on paper/challenge with honest multi-month timeline; (b) diversify beyond BTC-only for pace; (c) revisit only if new a-priori edge thesis (not more SMA50 milking).

## Assumptions / limitations

1. Real Dukas M1 bid only; missing midnights skipped.
2. N=3 and 2% agg locked a priori (not fit-tuned).
3. Remaining stop $ = full STOP×lots/0.01 while open (hard R=1; no trail).
4. Same-direction stack only; opposite regime while open → skip.
5. Flatten at ≤−4% closes remaining at next signal bar open (research approx).
6. 60d windows use Prague-day equity path on full fit→ext continuum.
7. No live engine changes.

## User summary (≤15 lines)

1. **REJECT** — multi-position C5 stack N=3 + 2% agg cap.
2. Config A (3×0.01): HO $448.25/mo; DD 9.1%; 60d **0/850**.
3. Config B (3×0.5%, 2% agg): HO $448.25/mo; DD 9.1%; 60d **0/850**.
4. Config C (1×0.5%): HO $490.95/mo; DD 8.8%; 60d **0/850**.
5. Binding: PACE+DD — stack cannot buy ≤60d at legal risk.
6. **Structural:** BTC-only ≤60d Challenge+Verification @ FTMO 5%/10% appears implausible on C5–C12 + survey.
7. Honest path: C5/C10 at legal size over longer horizon — not fake hope.
8. Live engines untouched.
