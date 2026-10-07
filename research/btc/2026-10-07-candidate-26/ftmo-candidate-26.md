# FTMO Candidate 26 — GER40 three-close momentum

**Research only.** Broad Odin mandate (Trading Ops 2026-10-07). Strategy Explorer suggested GER40 three-close as near-miss lane.
No live risk raise. No deploy without Odin yes. Leave C4 + drip freeze untouched.
Do not package Gold as primary. C22 was GER40 **Donchian** (REJECT). C24 was XAG three-close (REJECT). This is entry5 mechanics on GER40.

## One-line thesis

Mirror Gold **entry5** three-close momentum on **GER40** (new instrument; C22 was Donchian) — shorter trend entry, looking for a ≤~3-month Challenge+Verification path without ~10% blow-up.

## Locked rules (a-priori — not a fishing grid)

Copied from `/workspace/gold-strategy/entry5-preregister-2026-10-03.md` (mechanics only). Do not retune after seeing results.

| Item | Value |
|---|---|
| Signal | Long if C[t]>C[t-1]>C[t-2]>C[t-3]; short strict mirror; else flat |
| Entry | Next daily open; one position; ignore signal if in position |
| Stop | 2× simple ATR14 (griff `compute_atr_14`, same as entry5/Donchian) |
| Target | **2R** (2 × stop distance) |
| TIME | Day-5 close if neither SL nor TP |
| Sides | Both; no MA/channel/session filter |
| Risk (26A official) | **2.50%** of equity at entry (index lane; same as C22 base) |
| Soft governor (26B a-priori) | dd&lt;5% → **2.50%**; 5–8% → **1.25%**; ≥8% → **0.75%** — **never sticky-block**; Prague day kill −3% |
| Risk (sensitivity only) | 2.60% — readout only; **not** the verdict |
| Fill priority | Same as entry5 / Donchian `resolve_bar` (SL_OPEN / SL_BOTH / SL / TP / TIME) |

### Books

1. **26A GER40 three-close @2.50%** — primary verdict book
2. **26B GER40 three-close + soft DD governor** — a-priori companion (not retune)

### Data

- File: `/workspace/strategy-explorer/pr36/dukascopy-raw/deuidxeur-m1-bid-2024-01-01-2026-09-02.csv`
- Expected sha256: `f2b497a703bfcfe273896e467c25b3472ab1689d050ee74f3f0f057791d8010d`
- Daily bars: October 2 harness `load_m1` + `resample(..., rule="1D", label="left", closed="left")`, Prague `FTMO_TZ`

### Costs (ASSUMPTIONS — reuse C22)

| Item | Value | Note |
|---|---|---|
| contract_size | **1** | FTMO GER40.cash catalogue |
| commission | **0** | catalogue |
| spread | **2.0** index points | **ASSUMPTION** — feed missing |
| profitCurrency | EUR→USD **1:1** | **ASSUMPTION** — research; not live FX |
| PnL | `(exit−entry)×lots − spread×lots` (side-aware) | min lot 0.01; cap 100 |

### Periods

| Slice | Range |
|---|---|
| Fit | 2024-01-01 → 2025-11-07 |
| HO | 2025-11-08 → 2026-09-01 |
| Ext | 2026-09-02 → data end (likely UNAVAILABLE on this feed) |

## ACCEPT gates (same as C22–C25)

- max DD ≤ 10%
- worst Prague day &gt; −5%
- HO net &gt; 0
- leave-out remaining HO (drop 2 best HO months) &gt; 0
- Ext ≥ 0 or N/A
- ≥1 ≤90d Challenge+Verification window with start in HO or Ext

Also report Explorer-style 30 Prague month-triplets (outside Aug2025–Feb2026 countable) for cross-check — **HO ≤90d windows remain the ACCEPT gate**.

### Verdict

- **ACCEPT** if all gates above clear (Ext N/A → may still be CONDITIONAL per C22 honesty).
- **CONDITIONAL** if legal DD + HO/Ext-era windows but leave-out/Ext weak.
- **REJECT** otherwise. **No retune after results.**

## Stop

One locked run at 2.50% + soft-gov book (+ 2.60% sensitivity readout). Nothing live.
