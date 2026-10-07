# FTMO Candidate 40 — GER40 Keltner55 (entry55 mirror) + soft DD governor

**Research only.** Broad Odin mandate (Trading Ops 2026-10-07). Fresh single-book GER40 Keltner after C22 GER40 Donchian REJECT, C26 GER40 three-close REJECT, and C31 JPN225 Keltner (joint only).
No live risk raise. No deploy without Odin yes. Leave C4 + drip freeze untouched.
Do not package Gold as primary. Do **not** conflict with C38/C39 files.

## One-line thesis

Mirror Gold **entry55** Keltner Channel break mechanics on **GER40** at index-lane **2.50%** risk with soft DD governor — looking for a ≤~3-month Challenge+Verification path without ~10% blow-up.

## Locked rules (a-priori — not a fishing grid)

Mechanics from `/workspace/gold-strategy/entry55_keltner_break_run.py` / entry55-preregister. Soft gov from C22. Do not retune after seeing results.

| Item | Value |
|---|---|
| Mid | EMA(close, 20); seed SMA of close[0..19] at t=19 |
| ATR | ATR14 (simple mean of TR) |
| Upper / Lower | Mid ± **1.5** × ATR |
| Entry | close crosses above Upper (long) or below Lower (short); next open |
| Stop | **2×ATR** from entry |
| TP | **2R** (2 × stop distance) |
| TIME | day **5** close |
| Sides | Both |
| Risk (40A) | **2.50%** OFF (fixed) |
| Soft governor (40B verdict) | dd&lt;5% → **2.50%**; 5–8% → **1.25%**; ≥8% → **0.75%** — **never sticky-block**; Prague day kill −3% |

### Books

1. **40A GER40 Keltner55 @2.50% OFF** — ungoverened baseline
2. **40B GER40 Keltner55 + soft DD governor** — **verdict** book

### Data

- File: `/workspace/strategy-explorer/pr36/dukascopy-raw/deuidxeur-m1-bid-2024-01-01-2026-09-02.csv`
- Expected sha256: `f2b497a703bfcfe273896e467c25b3472ab1689d050ee74f3f0f057791d8010d`
- Daily bars: resample 1D label=left closed=left origin=2024-01-01 UTC

### Costs (ASSUMPTIONS — reuse C22)

| Item | Value | Note |
|---|---|---|
| contract_size | **1** | FTMO GER40.cash catalogue |
| spread | **2.0** pts | **ASSUMPTION** — C22 GER40 (feed missing) |
| commission | **$0/lot** | catalogue |
| EUR→USD | **1:1** | **ASSUMPTION** — research; catalogue profitCurrency=EUR |
| lots | `round(risk$ / (sl_dist * contract), 2)`; skip if &lt;0.01 | |
| PnL | `sign*(exit−entry)*lots*contract − spread*lots − commission*lots` | LABEL ASSUMPTIONS |

### Periods (same as C31–C38)

| Slice | Range |
|---|---|
| Fit | 2024-01-01 → 2025-11-07 |
| HO | 2025-11-08 → 2026-09-01 |
| Ext | 2026-09-02 → data end (likely UNAVAILABLE on this feed) |

## ACCEPT gates (same as C31–C38)

- max DD ≤ 10%
- worst Prague day &gt; −5%
- HO net &gt; 0
- leave-out remaining HO (drop 2 best HO months) &gt; 0
- Ext ≥ 0 or N/A
- ≥1 ≤90d Challenge+Verification window with start in HO or Ext

Also report Explorer-style 30 Prague month-triplets (outside Aug2025–Feb2026 countable) for cross-check — **HO ≤90d windows remain the ACCEPT gate**.

### Verdict

- **ACCEPT** if all gates above clear (Ext N/A → may still be CONDITIONAL per C22 honesty).
- **CONDITIONAL** if legal DD + HO/Ext-era windows but leave-out/Ext weak, or Fit-era-only windows.
- **REJECT** otherwise. **No retune after results.**

## Stop

One locked run: 40A OFF + 40B SOFT (verdict). Nothing live. Do not conflict with C39.
