# FTMO Candidate 39 — MUTEX XAG Donchian soft primary + US100 NR7

Research-only. Locked a-priori **MUTEX** joint — **not** a fishing grid / not a C35 or C37 retune.
Live C4 / drip / FREEZE / MetaAPI untouched. Do not package Gold. No deploy.

## Thesis

C35 (dual-open equal soft) and C37 (dual-open XAG primary + 0.25% NR7 sat) both **wipe XAG’s 8 HO ≤90d windows to 0**.
Hypothesis: simultaneous second-sleeve PnL/DD path destroys windows.
Locked **mutex**: at most **one position account-wide**; XAG soft primary signals have priority; US100 NR7 only enters when flat.

## MUTEX rules (locked)

1. At most **one** open position account-wide (never dual-open).
2. XAG soft primary signals have priority.
3. US100 NR7 only enters when account is **flat** (no XAG and no US100 open).
4. Same bar / priority conflict: **take XAG**, ignore US100.
5. If US100 open and XAG signals: **do not** flatten US100 early; ignore XAG until flat (**no force-flat**).
6. Soft gov on shared peak scales **whichever sleeve is entering** (XAG 2.50 ladder; US100 1.00→0.50→0.25).
7. Prague −3% kill: no new entries that Prague day. Never sticky-block.

## Soft governor (shared book)

| Sleeve entering | Full | Mid | Floor |
|---|---:|---:|---:|
| XAG Donchian 20d | **2.50%** | **1.25%** | **0.75%** |
| US100 NR7 (when flat) | **1.00%** | **0.50%** | **0.25%** |

dd&lt;5% → full; 5–8% → mid; ≥8% → floor.

## Books

| Book | Contents |
|---|---|
| **39A** | XAG soft alone (control; expect HO windows=8) |
| **39B** | US100 NR7 soft alone @1% ladder |
| **39C** | MUTEX joint (verdict) |

## Chassis (exact reuse — no retune)

### PRIMARY — XAG 20d Donchian both TP1R TIME10

- Exact C19B/C21B / C35B / C37A chassis
- Soft tiers on account peak: 2.50% / 1.25% / 0.75%
- Costs ASSUMPTION: contract 5000, spread 0.025, $3/lot

### SECONDARY — US100 NR7 @1.00% (full Explorer risk when allowed)

- Exact Explorer / C35A chassis; TIME day5; TP 2R
- Costs: spread 1, commission 0, contract 1
- Only when flat under mutex

## ACCEPT gates

Standard (HO≤90d start in HO/Ext required). Success vs C35/C37: **39C HO≤90d &gt; 0**.
CONDITIONAL if windows survive but leave-out still fails. REJECT if windows still 0. No retune.

## ASSUMPTIONS

| Item | Value |
|---|---|
| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** (ASSUMPTION — C19B/C21B) |
| US100 costs | spread 1 / comm 0 / contract 1 (catalogue) |
| Soft gov | dd&lt;5% full; 5–8% mid; ≥8% floor; never sticky-block |
| Prague day kill | −3% |
| Max positions | **MUTEX one account-wide** |
| Ext | UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) |
