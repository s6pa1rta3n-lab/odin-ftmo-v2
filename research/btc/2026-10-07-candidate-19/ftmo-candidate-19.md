# FTMO Candidate 19 — XAGUSD denser-pace hunt

Research-only multi-asset book under BTC Strategies lane.
Two locked a-priori XAG books. Not a fishing grid. No deploy. Do not package Gold.

## Book 19A — XAG H4 BB squeeze (BTC C15 / ETH C18A port)

- H4 Bollinger(20, 2σ); squeeze = bw ≤ P10 of prior 100 bw
- Break: prior bar in squeeze AND close outside band
- Stop 1×ATR14; target R=2; max 1 pos
- Risk 0.75% (also 0.50%, 1.00%); Prague −3% day kill
- Cost: XAG ASSUMPTION — spread 0.025 × units, commission $3/lot, contract_size 5000

## Book 19B — XAG 20-day Donchian dual @ 2.50% TP1R

- Daily UTC bars from M1; 20-day channel (prior bars only)
- Both sides; entry next open; stop 2×ATR; target **1R**; TIME day-10
- Risk **2.50%**; Prague day DD/worst-day rules
- Cost: metals formula — XAG contract_size 5000, spread 0.025, commission $3/lot (ASSUMPTIONS)

## Periods

| Slice | Range |
|---|---|
| Fit | 2024-01-01 → 2025-11-07 |
| HO | 2025-11-08 → 2026-09-01 |
| Ext | 2026-09-02 → data end (UNAVAILABLE on this feed) |

## Gates

- ACCEPT: ≥1 legal ≤90d both-stages window + Ext≥0 + leave-out OK
- CONDITIONAL: legal DD + HO pace ≥$3,000/mo (label Ext)

