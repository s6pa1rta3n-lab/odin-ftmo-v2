# FTMO Candidate 29 — Locked residual stack: C15 BTC H4 BB squeeze + C21B XAG Donchian soft

Research-only. Locked a-priori joint residual stack — **not** a fishing grid.
Live C4 / drip / FREEZE / MetaAPI untouched. Do not package Gold. No deploy.

## Thesis (from C17)

BTC alone has **0 ≤90d Challenge+Ver windows**. Best BTC DD-legal sleeve C15@0.75% ~$1291/mo DD 7.4% Ext red. Residual gap ≥~$3709/mo in ~2.6% shared DD headroom. Best non-Gold HO-window sleeve we own: **C21B XAG Donchian soft** (~$847/mo DD 9.4%, 8 HO-era ≤90d, leave-out fail alone). Measure whether **shared-equity joint** of locked C15 BTC + C21B XAG soft clears ACCEPT.

**Do NOT retune signal rules.** Reuse exact C15 and C21B chassis; only lock a-priori risk shares + shared soft gov.

## Soft governor (shared book — locked)

1. One shared equity starting $100k; one peak DD across both sleeves.
2. Soft governor on **shared** dd: dd&lt;5% → full; 5–8% → mid; ≥8% → floor; never sticky-block.
3. Prague −3% day kill blocks new entries that Prague day for **both** sleeves.
4. Max **one position per sleeve** (two max simultaneous if both signal).

## Risk shares at full tier (a-priori)

| Sleeve | Full | Mid | Floor |
|---|---:|---:|---:|
| BTC H4 BB squeeze (C15) | **0.40%** | **0.20%** | **0.10%** |
| XAG Donchian 20d (C21B) | **1.25%** | **0.625%** | **0.375%** |

## Books (diagnostics + verdict)

| Book | Contents |
|---|---|
| **29A** | BTC-only at joint BTC risks (0.40 soft) — baseline |
| **29B** | XAG-only at joint XAG risks (1.25 soft) — baseline |
| **29C** | Joint shared equity as above — **verdict book** |

## Chassis (exact reuse — no retune)

### Sleeve A — BTC H4 BB squeeze (exact C15)

- Spec: `ftmo-candidate-15.md` + `run_candidate_15.py`
- H4 Bollinger(20, 2σ) squeeze (bw ≤ P10 of prior 100); break = prior bar in squeeze + close outside band
- Stop 1.0×ATR14 H4; target R=2; entry first M1 open at/after H4 end; same-minute double-touch → stop
- Costs: spread **15**, commission **0**, contract **1**
- Data: BTC dukas M1 main + dukas-ext

### Sleeve B — XAG 20d Donchian both TP1R TIME10 (exact C19B/C21B)

- Daily 20d dual Donchian; stop 2×ATR; TP 1R; TIME day-10
- Costs ASSUMPTION: contract **5000**, spread **0.025**, commission **$3/lot**
- Data: `xagusd-m1-bid-2024-01-01-2026-09-02.csv`

## Periods

| Slice | Range |
|---|---|
| Fit | 2024-01-01 → 2025-11-07 |
| HO | 2025-11-08 → 2026-09-01 |
| Ext | 2026-09-02 → data end (BTC: dukas-ext; XAG: N/A if feed ends) |

## Gates

- **ACCEPT**: max DD ≤10%, worst Prague day &gt; −5% (0 days ≤−5%), HO net &gt;0, leave-out remaining HO &gt;0, Ext≥0 or N/A, AND ≥1 ≤90d Challenge+Ver window with start in HO or Ext.
- **CONDITIONAL**: legal DD + HO/Ext-era windows but leave-out/Ext weak.
- **REJECT** otherwise. No retune after results.
