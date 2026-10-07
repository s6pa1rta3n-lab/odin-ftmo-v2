# Draft PR — research docs only

**Title:** `research: BTC Candidate 6 REJECT (C5 fast-scale vs ≤60d DD wall) — 2026-10-07`

**Base:** `main`  
**Head:** `research/btc-candidate-6-2026-10-07`  
**Repo:** `s6pa1rta3n-lab/odin-ftmo-v2`  
**Draft:** yes  
**Scope:** markdown + research runner under `research/btc/2026-10-07-candidate-6/` only — **no live engine / drip / C4 service changes**

---

## Summary

Research-only Candidate 6. **Decision: REJECT** as a fast FTMO vehicle (Challenge +10% then Verification +5% in ≤60 calendar days on ~$100k ASSUMPTION).

**Thesis:** Do not invent filters. Take C5 (only book clearing all 6 robustness gates), measure volume needed for ~$7.5k/mo HO-like pace, check 5% daily / 10% max DD.

## Wall (measured)

| Metric | Value |
|---|---|
| HO @ 0.01 | ~$4,790 over 297d ≈ **~$491/mo** |
| Vol for ~$7.5k/mo | **~0.153** |
| Worst day at that vol | **~−$12,616** (limit −$5,000) — **illegal** |
| One stop at that vol | **~$6,308** — **illegal** |
| Max DD-safe vol (worst-day) | **~0.0605** |
| Pace at max safe | **~$2,973/mo** |
| Est. days both steps @ max safe | **~154 days** (>60) |

Gate A (C5 robustness @ 0.01) still passes. Gate B (fast vehicle) fails.

## vs C5

C5 remains research ACCEPT on robustness. C6 answers Odin’s “pass a lot quicker” ask: **size alone cannot**; need a higher-$/month structure (or accept slower pass).

## Paths

- Pack: `research/btc/2026-10-07-candidate-6/`
- Spec / results / runner / STATUS in pack
- Box: `/workspace/btc-strategies/`

## Live

No deploy. C4 armed path / FREEZE / drip untouched.
