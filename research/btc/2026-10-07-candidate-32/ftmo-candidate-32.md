# FTMO Candidate 32 — USA30 three-close momentum

**Research only.** Broad Odin mandate (Trading Ops 2026-10-07).
No live risk raise. No deploy without Odin yes. Leave C4 + drip freeze untouched.
Do not package Gold as primary. C26 was GER40 **three-close** (REJECT). C22 was USA30 **Donchian** (REJECT). This is entry5 mechanics on USA30 (sibling index we own; not yet run on three-close).

## One-line thesis

Mirror Gold **entry5** / C26 three-close momentum on **USA30** — shorter trend entry on the USD index sibling, looking for a ≤~3-month Challenge+Verification path without ~10% blow-up.

## Locked rules (a-priori — not a fishing grid)

Copied from `/workspace/gold-strategy/entry5-preregister-2026-10-03.md` (mechanics only) / C26 chassis. Do not retune after seeing results.

| Item | Value |
|---|---|
| Signal | Long if C[t]>C[t-1]>C[t-2]>C[t-3]; short strict mirror; else flat |
| Entry | Next daily open; one position; ignore signal if in position |
| Stop | 2× simple ATR14 (griff `compute_atr_14`, same as entry5/Donchian) |
| Target | **2R** (2 × stop distance) |
| TIME | Day-5 close if neither SL nor TP |
| Sides | Both; no MA/channel/session filter |
| Risk (32A official) | **2.50%** of equity at entry |
| Soft governor (32B a-priori) | dd&lt;5% → **2.50%**; 5–8% → **1.25%**; ≥8% → **0.75%** — **never sticky-block**; Prague day kill −3% |
| Risk (sensitivity only) | 2.60% — readout only; **not** the verdict |
| Fill priority | Same as entry5 / Donchian `resolve_bar` (SL_OPEN / SL_BOTH / SL / TP / TIME) |

### Books

1. **32A USA30 three-close @2.50%** — primary verdict book (OFF)
2. **32B USA30 three-close + soft DD governor** — a-priori companion (not retune)

### Data

- File: `/workspace/strategy-explorer/pr36/dukascopy-raw/usa30idxusd-m1-bid-2024-01-01-2026-09-02.csv`
- Expected sha256: `968d27f1eb1ea5e8df4fb138a077ec73be4d478238c4ad938cb021ec3b84746a`
- Daily bars: October 2 harness `load_m1` + `resample(..., rule="1D", label="left", closed="left")`, Prague `FTMO_TZ`

### Costs (ASSUMPTIONS — reuse C22 USA30)

| Item | Value | Note |
|---|---|---|
| contract_size | **1** | FTMO US30.cash catalogue |
| commission | **0** | catalogue |
| spread | **2.5** index points | **ASSUMPTION** — feed missing (C22) |
| profitCurrency | **USD** | no FX conversion |
| PnL | `(exit−entry)×lots − spread×lots` (side-aware) | min lot 0.01; cap 100 |

### Periods

| Slice | Range |
|---|---|
| Fit | 2024-01-01 → 2025-11-07 |
| HO | 2025-11-08 → 2026-09-01 |
| Ext | 2026-09-02 → data end (likely UNAVAILABLE on this feed) |

## ACCEPT gates (same as C22–C26)

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

One locked run at 2.50% + soft-gov book (+ 2.60% sensitivity readout). Nothing live. Do not re-run GER40. Do not conflict with C31 file names.
