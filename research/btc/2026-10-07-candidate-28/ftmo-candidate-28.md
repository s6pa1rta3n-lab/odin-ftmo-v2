# Candidate 28 — Index Donchian + soft DD governor (UK100 / FRA40)

**Research only.** Broad Odin mandate (Trading Ops 2026-10-07). No live risk raise. No deploy without Odin yes. Leave C4 + drip freeze untouched. Do not package Gold.

## One-line thesis

**20-day Donchian both sides + soft DD governor** on remaining European index CFDs we have Dukas for and have NOT packaged (C22 was GER40/USA30 REJECT; C23 Brent/USA500 REJECT; C25 FX REJECT).

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

1. **28A UK100** — Dukas `gbridxgbp-m1-bid-2024-01-01-2026-09-02.csv`
2. **28B FRA40** — Dukas `fraidxeur-m1-bid-2024-01-01-2026-09-02.csv`
3. **28C joint** — UK100@1.25% + FRA40@1.25% soft-gov on **shared** equity / one DD peak (each leg 1/2 of soft tiers)

Each single also reports ungoverened baseline @2.50% for delta.

## ASSUMPTIONS (labelled)

FTMO catalogue (`UK100.cash.md`, `FRA40.cash.md` in `/workspace/FTMO-Catalogue/`):

| Field | UK100.cash | FRA40.cash | Notes |
|---|---|---|---|
| contractSize | **1** | **1** | From feed |
| commission | **0** | **0** | From feed |
| spread | **MISSING** | **MISSING** | → ASSUMPTION below |
| maxTradeVolume | 1000 | 1000 | From feed |
| profitCurrency | **GBP** | **EUR** | GBP/EUR→USD: ASSUMPTION **1:1** (research; not live FX) |

**ASSUMPTION spreads (industry mid; feed has none; locked a-priori):**
- UK100: **1.5** index points
- FRA40: **1.5** index points

PnL (per lot, contract=1): `(exit−entry)×lots − spread×lots` (side-aware). Min lot 0.01.

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

- `ftmo-candidate-28.md`, `run_candidate_28.py`, `candidate-28-results.md`
- pack `2026-10-07-candidate-28/`, `STATUS.md`, `GITHUB-PR-BODY-C28.md`
- PR `s6pa1rta3n-lab/odin-ftmo-v2` branch `research/btc/2026-10-07-candidate-28/`

## Live

Untouched. Research only.
