# FTMO Candidate 35 — US100 NR7 @1% + XAG Donchian soft (full C21B tiers)

Research-only. Locked a-priori joint — **not** a fishing grid.
Live C4 / drip / FREEZE / MetaAPI untouched. Do not package Gold. No deploy.

## Thesis

C31/C34 stack NR7 with index Keltner for pace but **0** HO ≤90d windows.
Best non-Gold sleeve that printed HO-era ≤90d windows: **C21B XAG Donchian soft**
(8 HO-era windows, DD 9.4%, leave-out fail alone). C29 halved XAG to 1.25% and **wiped** those windows.
Measure joint **US100 NR7@1% + XAG Donchian at full C21B soft tiers (2.50→1.25→0.75)**
so XAG keeps window-capable risk.

## Soft governor (shared book — locked)

1. One shared equity starting $100k; one peak DD across both sleeves.
2. Soft governor on **shared** dd: dd&lt;5% → full; 5–8% → mid; ≥8% → floor; never sticky-block.
3. Prague −3% day kill blocks new entries that Prague day for **both** sleeves.
4. Max **one position per sleeve** (two max simultaneous if both signal).

## Risk shares at full tier (a-priori)

| Sleeve | Full | Mid | Floor |
|---|---:|---:|---:|
| US100 NR7 | **1.00%** | **0.50%** | **0.25%** |
| XAG Donchian 20d (C21B) | **2.50%** | **1.25%** | **0.75%** |

**Do NOT** use C29 halved XAG (1.25/0.625/0.375).

## Books

| Book | Contents |
|---|---|
| **35A** | US100 NR7 soft alone (1.00→0.50→0.25) |
| **35B** | XAG Donchian soft alone (2.50→1.25→0.75) — expect ~C21B replay |
| **35C** | Joint OFF (US100 1% + XAG 2.50% always) |
| **35D** | Joint SOFT (verdict) |

## Chassis (exact reuse — no retune)

### Sleeve A — US100 NR7 @1.00%

- Exact `/workspace/strategy-explorer/us100-nr7-preregister-2026-10-07.md` / C31A
- Data usatechidxusd M1; costs spread1/comm0/contract1
- TIME day5; TP 2R; range stop

### Sleeve B — XAG 20d Donchian both TP1R TIME10

- Exact C19B/C21B chassis
- Soft tiers on **shared** peak: full **2.50%** / mid **1.25%** / floor **0.75%**
- Data xagusd M1; costs ASSUMPTION contract 5000 / spread 0.025 / commission $3/lot

## Periods / ACCEPT gates

Same as C31–C34. Leave-out + Ext matter. No retune after results.

## ASSUMPTIONS

| Item | Value |
|---|---|
| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** (ASSUMPTION — C19B/C21B parity) |
| US100 costs | spread 1 / comm 0 / contract 1 (catalogue) |
| Soft gov | dd&lt;5% full; 5–8% half; ≥8% floor; never sticky-block |
| Prague day kill | −3% both sleeves |
| Max positions | one per sleeve |
| Ext | UNAVAILABLE (feeds end 2026-09-01; no dukas-ext for these symbols) |
