# FTMO Candidate 27 — XAGUSD Wilder Parabolic SAR

**Research only.** Broad Odin mandate (Trading Ops 2026-10-07). Explorer suggested XAG Wilder SAR as near-miss lane after C26 GER40 three-close REJECT.
No live risk raise. No deploy without Odin yes. Leave C4 + drip freeze untouched.
Do not package Gold as primary. Explorer BTC SAR @0.50% already FAIL — do **not** re-run BTC.

## One-line thesis

Mirror Gold **entry30** / Explorer **BTC-SAR** Wilder Parabolic SAR mechanics on **XAGUSD** at metals-lane **2.50%** risk — reverse-only exits, looking for a ≤~3-month Challenge+Verification path without ~10% blow-up.

## Locked rules (a-priori — not a fishing grid)

Copied from `/workspace/gold-strategy/entry30-preregister-2026-10-03.md` and `/workspace/strategy-explorer/btc-sar-preregister-2026-10-07.md` (mechanics only). Do not retune after seeing results.

| Item | Value |
|---|---|
| AF start / step / max | **0.02 / 0.02 / 0.20** |
| Seed | Bar 1 seed only (no trade); first trade = first later reversal |
| Update | Raw next SAR + long min(raw, low[t], low[t-1]) / short max(raw, high[t], high[t-1]) |
| Reverse fill | next SAR, or open if gapped through; one reverse per bar |
| New SAR after reverse | old extreme point; AF resets to 0.02 |
| Exits | Reverse-only (REVERSE / SL_OPEN). No ATR stop. No TP. No TIME |
| Sides | Both |
| Stop distance for sizing | abs(fill − new SAR) |
| Risk (27A official) | **2.50%** of equity at entry (XAG lane parity C19/C21/C24 — NOT BTC 0.50%, NOT Gold 2.60% as retune) |
| Soft governor (27B a-priori) | dd&lt;5% → **2.50%**; 5–8% → **1.25%**; ≥8% → **0.75%** — **never sticky-block**; Prague day kill −3% |
| Risk (sensitivity only) | 2.60% — readout only; **not** the verdict |

### Books

1. **27A XAG SAR @2.50%** — primary verdict book
2. **27B XAG SAR + soft DD governor** — a-priori companion (not retune)

### Data

- File: `/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv`
- Expected sha256: `6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c`
- Daily bars: October 2 harness `load_m1` + `resample(..., rule="1D", label="left", closed="left")`, Prague `FTMO_TZ`

### Costs (ASSUMPTIONS — reuse C19/C24)

| Item | Value | Note |
|---|---|---|
| contract_size | **5000** | FTMO XAG |
| spread | **0.025** | **ASSUMPTION** — C19/C24 parity |
| commission | **$3/lot** | **ASSUMPTION** — C19/C24 metals parity |
| tick_value | 1.0 | |
| lots | `round(risk$ / (sl_dist * contract), 2)`; skip if &lt;0.01 | |
| PnL | `sign*(exit−entry)*lots*contract − spread*lots*contract − commission*lots` | LABEL ASSUMPTIONS |

### Periods

| Slice | Range |
|---|---|
| Fit | 2024-01-01 → 2025-11-07 |
| HO | 2025-11-08 → 2026-09-01 |
| Ext | 2026-09-02 → data end (likely UNAVAILABLE on this feed) |

## ACCEPT gates (same as C22–C26)

- max DD ≤ 10%
- worst Prague day &gt; −5% (**floating** mark — SAR continuous book; match BTC SAR floating Prague day construction)
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
