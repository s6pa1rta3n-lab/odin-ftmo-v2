# FTMO Candidate 37 — XAG soft PRIMARY + US100 NR7 @0.25% fixed satellite

Research-only. Locked a-priori joint — **not** a fishing grid and **not** a post-hoc C35 risk retune.
Live C4 / drip / FREEZE / MetaAPI untouched. Do not package Gold. No deploy.

## Thesis

C35 showed XAG soft alone keeps **8 HO ≤90d windows** but leave-out fails; joint with US100 NR7
at equal soft scaling (**US100 1% full**) wiped HO windows to **0** while adding pace.

Locked a-priori **XAG-primary** book: keep XAG at full C21B soft tiers; add US100 NR7 only as a
**tiny fixed satellite** so shared DD / competing risk does not erase XAG’s HO windows.

This is a **different locked thesis** (primary + satellite), documented a-priori before this run —
not a silent restore of US100 to 1% nor a C35 retune.

## Soft governor (shared book — locked)

1. One shared equity starting $100k; one peak DD across both sleeves.
2. Soft governor on **shared** dd resizes **XAG only**: dd&lt;5% → full; 5–8% → mid; ≥8% → floor; never sticky-block.
3. US100 risk is **fixed 0.25%** at all dd tiers (does **not** soft-scale).
4. Prague −3% day kill blocks new entries that Prague day for **both** sleeves.
5. Max **one position per sleeve** (two max simultaneous if both signal).

## Risk shares (a-priori)

| Sleeve | Role | Full | Mid | Floor |
|---|---|---:|---:|---:|
| XAG Donchian 20d (C21B) | **PRIMARY** | **2.50%** | **1.25%** | **0.75%** (soft) |
| US100 NR7 | **SATELLITE** | **0.25%** | **0.25%** | **0.25%** (fixed) |

**Do NOT** silently restore US100 to 1.00%. **Do NOT** use C29 halved XAG.

## Books

| Book | Contents |
|---|---|
| **37A** | XAG Donchian soft alone (2.50→1.25→0.75) — replay control; expect ~C21B/35B |
| **37B** | US100 NR7 @ **fixed 0.25%** alone |
| **37C** | Joint XAG soft primary + US100 0.25% fixed satellite (**verdict**) |

## Chassis (exact reuse — no retune)

### Sleeve B (PRIMARY) — XAG 20d Donchian both TP1R TIME10

- Exact C21B / C35B
- Soft on shared peak: full **2.50%** / mid **1.25%** / floor **0.75%**
- Data xagusd M1; costs ASSUMPTION contract 5000 / spread 0.025 / commission $3/lot

### Sleeve A (SATELLITE) — US100 NR7

- Exact Explorer/C31/C35 NR7 mechanics
- Risk **fixed 0.25%** always
- Data usatechidxusd M1; costs spread1/comm0/contract1
- TIME day5; TP 2R; range stop

## ACCEPT gates

- max DD ≤10%; worst Prague day &gt; −5%; HO&gt;0; leave-out remaining HO&gt;0; Ext≥0 or N/A
- ≥1 ≤90d Challenge+Ver with **start in HO or Ext**
- CONDITIONAL if legal DD + HO-era windows but leave-out/Ext weak (like C21)
- REJECT if HO windows still 0 or DD illegal

**Success criterion vs C35:** HO≤90d count on **37C &gt; 0** (windows survive) AND ideally leave-out improves vs 37A — report clearly either way. No further retune.

## ASSUMPTIONS

| Item | Value |
|---|---|
| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** (ASSUMPTION — C19B/C21B parity) |
| US100 costs | spread 1 / comm 0 / contract 1 (catalogue) |
| Soft gov | dd&lt;5% full; 5–8% mid; ≥8% floor — **XAG only**; never sticky-block |
| US100 satellite | **fixed 0.25%** — never soft-scales |
| Prague day kill | −3% both sleeves |
| Max positions | one per sleeve |
| Ext | UNAVAILABLE (feeds end 2026-09-01; no dukas-ext for these symbols) |
