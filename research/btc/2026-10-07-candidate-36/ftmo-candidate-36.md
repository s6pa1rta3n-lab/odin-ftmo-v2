# Candidate 36 — AUS200 Donchian + soft DD governor

**Research only.** Broad Odin mandate (Trading Ops 2026-10-07). No live risk raise. No deploy without Odin yes. Leave C4 + drip freeze untouched. Do not package Gold as primary.

## One-line thesis

Same **simple** chassis as C22/C28 (20-day Donchian both + soft DD governor) on **AUS200** (Dukas `ausidxaud`, FTMO `AUS200.cash`) — fresh liquid index unused in C22–C35.

## Locked rules (a-priori — not a fishing grid)

| Item | Value |
|---|---|
| Chassis | Daily 20-day Donchian **both** sides |
| Stop | 2×ATR14 |
| Target | **1R** |
| TIME | Day-10 exit if neither SL nor TP |
| Base risk | **2.50%** of equity at entry |
| Soft governor | dd&lt;5% → **2.50%**; 5–8% → **1.25%**; ≥8% → **0.75%** — **never sticky-block** |
| Prague day kill | −3% (no new entries that Prague day after kill) |
| Day fail bar | ≤ −5% Prague day → illegal |

### Books

1. **36A AUS200** — ungoverened @2.50%
2. **36B AUS200** — soft gov 2.50→1.25→0.75 (**verdict book**)

## ASSUMPTIONS (labelled)

FTMO catalogue (`AUS200.cash.md` / `ftmo-symbols.json` fetched 2026-10-03):

| Field | AUS200.cash | Notes |
|---|---|---|
| contractSize | **1** | From catalogue |
| commission | **0** | From catalogue |
| spread | **MISSING** | → ASSUMPTION below |
| maxTradeVolume | 1000 | From catalogue |
| profitCurrency | **AUD** | → AUD→USD **ASSUMPTION** |

**ASSUMPTION spread (industry mid; feed has none):**
- AUS200: **1.5** price points (task lock; mirror C22/C28 index mid)

**ASSUMPTION FX:**
- AUD→USD treated **1:1** for research PnL (profitCurrency=AUD). LABELLED.

PnL (side-aware): `(exit−entry)×lots×contract − spread×lots×contract − commission×lots`. Min lot 0.01.

**Data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/ausidxaud-m1-bid-2024-01-01-2026-09-02.csv`

## Periods

| Split | Range |
|---|---|
| Fit | 2024-01-01 → 2025-11-07 |
| Holdout (HO) | 2025-11-08 → 2026-09-01 |
| Ext | if data past 2026-09-01; else N/A |

## ACCEPT gates

- max DD ≤ 10%
- worst Prague day &gt; −5% (0 days ≤ −5%)
- HO net &gt; 0
- leave-out remaining HO (drop 2 best HO months) &gt; 0
- Ext ≥ 0 (or N/A if feed ends)
- ≥1 ≤90d Challenge+Verification window with **start in HO or Ext**

**CONDITIONAL** if legal DD + HO/Ext-era windows but leave-out/Ext weak.
**REJECT** otherwise. No retune.

## Deliverables

- `ftmo-candidate-36.md`, `run_candidate_36.py`, `candidate-36-results.md`
- pack `2026-10-07-candidate-36/`, `STATUS.md`, `GITHUB-PR-BODY-C36.md`
- PR `s6pa1rta3n-lab/odin-ftmo-v2` branch `research/btc/2026-10-07-candidate-36/`

## Live

Untouched. Research only. Do not package Gold. Do not conflict with C35 files.
