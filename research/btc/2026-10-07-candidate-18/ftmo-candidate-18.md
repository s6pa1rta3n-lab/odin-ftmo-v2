# FTMO Candidate 18 — ETHUSD denser-pace hunt

Research-only multi-crypto book under BTC Strategies lane.
Two locked a-priori ETH books. Not a fishing grid. No deploy.

## Book 18A — ETH H4 BB squeeze (BTC C15 port)

- H4 Bollinger(20, 2σ); squeeze = bw ≤ P10 of prior 100 bw
- Break: prior bar in squeeze AND close outside band
- Stop 1×ATR14; target R=2; max 1 pos
- Risk 0.75% (also 0.50%, 1.00%); Prague −3% day kill
- Cost: C15 HF analog — spread 1.50 × units, commission 0, contract_size 10

## Book 18B — ETH 20-day Donchian dual @ 2.60%

- Daily UTC bars from M1; 20-day channel (prior bars only)
- Both sides; entry next open; stop 2×ATR; target 3R; TIME day-10
- Risk **2.60%**; Prague day DD/worst-day rules
- Cost: Gold daily formula with ETH contract_size 10, spread 1.50, commission 0

## Periods

| Slice | Range |
|---|---|
| Fit | 2024-01-01 → 2025-11-07 |
| HO | 2025-11-08 → 2026-09-01 |
| Ext | 2026-09-02 → data end (UNAVAILABLE on this feed) |

## Gates

- ACCEPT: ≥1 legal ≤90d both-stages window + Ext≥0 + leave-out OK
- CONDITIONAL: legal DD + HO pace ≥$3,000/mo (label Ext)

