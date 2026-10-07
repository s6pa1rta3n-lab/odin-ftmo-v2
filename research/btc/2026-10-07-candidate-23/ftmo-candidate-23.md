# Candidate 23 — Brent / USA500 Donchian + soft DD governor

**Research only.** Broad Odin mandate (Trading Ops 2026-10-07). No live risk raise. No deploy without Odin yes. Leave C4 + drip freeze untouched. Do not package Gold as primary.

## One-line thesis

Same **simple** chassis as C22 (20-day Donchian both + soft DD governor) on **Brent** and **USA500** — liquid symbols we own in this research lane — looking for a ≤~3-month Challenge+Verification path without ~10% blow-up.

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

### Symbols

1. **23A Brent** — Dukas `brentcmdusd-m1-bid-2024-01-01-2026-09-02.csv` (FTMO `UKOIL.cash`)
2. **23B USA500** — Dukas `usa500idxusd-m1-bid-2024-01-01-2026-09-02.csv` (FTMO `US500.cash`)
3. **23C joint** (if singles finish cleanly) — Brent@1.25% + USA500@1.25% soft-gov on **shared** equity / one DD peak

Each single also reports ungoverened baseline @2.50% for delta.

## ASSUMPTIONS (labelled)

FTMO catalogue (`UKOIL.cash.md`, `US500.cash.md`):

| Field | UKOIL.cash (Brent) | US500.cash | Notes |
|---|---|---|---|
| contractSize | **100** | **1** | From feed |
| commission | **0** | **0** | From feed |
| spread | **MISSING** | **MISSING** | → ASSUMPTION below |
| maxTradeVolume | 1000 | 1000 | From feed |
| profitCurrency | **USD** | **USD** | No FX conversion |

**ASSUMPTION spreads (industry mid; feed has none):**
- Brent: **0.04** price units (≈$0.04/bbl typical Brent CFD mid)
- USA500: **0.50** index points (typical SPX CFD mid; between US100=1.0 and tighter quotes)

PnL (side-aware): `(exit−entry)×lots×contract − spread×lots×contract − commission×lots`. Min lot 0.01.

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
**REJECT** otherwise.

## Deliverables

- `ftmo-candidate-23.md`, `run_candidate_23.py`, `candidate-23-results.md`
- pack `2026-10-07-candidate-23/`, `STATUS.md`, `GITHUB-PR-BODY-C23.md`
- PR `s6pa1rta3n-lab/odin-ftmo-v2` branch `research/btc/2026-10-07-candidate-23/`

## Live

Untouched. Research only.
