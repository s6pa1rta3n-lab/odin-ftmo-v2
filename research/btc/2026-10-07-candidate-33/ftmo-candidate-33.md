# Candidate 33 — FX residual majors Donchian + soft DD governor (AUDUSD / USDCAD)

**Research only.** Broad Odin mandate (Trading Ops 2026-10-07). No live risk raise. No deploy without Odin yes. Leave C4 + drip freeze untouched. Do not package Gold as primary.

## One-line thesis

Same **simple** chassis as C25 (20-day Donchian both + soft DD governor) on the remaining liquid FX majors we own Dukas M1 for and have **not** yet packaged. C25 was EURUSD/GBPUSD/USDJPY **REJECT**. Fresh pairs: **AUDUSD** and **USDCAD**.

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

1. **33A AUDUSD** — Dukas `audusd-m1-bid-2024-01-01-2026-09-02.csv` (FTMO `AUD/USD`) — OFF + SOFT
2. **33B USDCAD** — Dukas `usdcad-m1-bid-2024-01-01-2026-09-02.csv` (FTMO `USD/CAD`) — OFF + SOFT
3. **33C joint** — equal soft-gov risk share on **shared** equity / one DD peak: each leg **2.50%/2 → 1.25%/2 → 0.75%/2** (1.25% / 0.625% / 0.375%); one position at a time globally (first by entry_ts; skip overlap) — **documented a-priori**

Each single also reports ungoverened baseline @2.50% for delta. Joint also reports ungoverned @1/2 share.

## ASSUMPTIONS (labelled)

FTMO catalogue (`AUD-USD.md`, `USD-CAD.md`, fetched 2026-10-03):

| Field | AUD/USD | USD/CAD | Notes |
|---|---|---|---|
| contractSize | **100000** | **100000** | From feed |
| commission | **5** USD/lot | **5** USD/lot | flat_USD from feed |
| spread | **MISSING** | **MISSING** | → ASSUMPTION below |
| maxTradeVolume | 100 | 100 | From feed |
| profitCurrency | **USD** | **CAD** | USDCAD needs FX→USD |

**ASSUMPTION spreads (industry mid; feed has none):**
- AUDUSD: **0.00015** (≈1.5 pip)
- USDCAD: **0.00020** (≈2.0 pip)

**USDCAD PnL → USD:** raw CAD PnL `(exit−entry)×lots×100000 − spread×lots×100000`, then divide by mid USDCAD at exit (bid close used as mid — **ASSUMPTION**, bid-only feed). Commission still −$5/lot in USD.

**USDCAD sizing:** `lots = equity × risk × entry_mid / (stop_dist × contract)` so stop loss ≈ risk% in USD.

PnL AUDUSD (side-aware): `(exit−entry)×lots×contract − spread×lots×contract − commission×lots`. Min lot 0.01; max lot 100.

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

- `ftmo-candidate-33.md`, `run_candidate_33.py`, `candidate-33-results.md`
- pack `2026-10-07-candidate-33/`, `STATUS.md` (preserve C31/C32), `GITHUB-PR-BODY-C33.md`
- PR `s6pa1rta3n-lab/odin-ftmo-v2` branch `research/btc/2026-10-07-candidate-33/`

## Live

Untouched. Research only. Do not conflict with C31 naming.
