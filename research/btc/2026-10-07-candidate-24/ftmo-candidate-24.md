# FTMO Candidate 24 — XAG three-close momentum

**Research only.** Broad Odin mandate (Trading Ops 2026-10-07). Strategy Explorer directed this hypothesis.
No live risk raise. No deploy without Odin yes. Leave C4 + drip freeze untouched.
Do not package Gold as primary. Do not duplicate BTC Wilder SAR or Gold weekly Donchian (Explorer owns those).

## One-line thesis

Mirror Gold **entry5** three-close momentum on **XAGUSD** (swap symbol/data/costs only) — shorter trend entry than Donchian, looking for a ≤~3-month Challenge+Verification path without ~10% blow-up.

## Locked rules (a-priori — not a fishing grid)

Copied from `/workspace/gold-strategy/entry5-preregister-2026-10-03.md`. Do not retune after seeing results.

| Item | Value |
|---|---|
| Signal | Long if C[t]>C[t-1]>C[t-2]>C[t-3]; short strict mirror; else flat |
| Entry | Next daily open; one position; ignore signal if in position |
| Stop | 2× simple ATR14 (griff `compute_atr_14`, same as entry5/Donchian) |
| Target | **2R** (2 × stop distance) |
| TIME | Day-5 close if neither SL nor TP |
| Sides | Both; no MA/channel/session filter |
| Risk (official) | **2.50%** of equity at entry |
| Risk (sensitivity only) | 2.60% — readout only; **not** the verdict |
| Fill priority | Same as entry5 `resolve_bar` (SL_OPEN / SL_BOTH / SL / TP / TIME) |

### Data

- File: `/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv`
- Expected sha256: `6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c`
- Daily bars: October 2 harness `load_m1` + `resample(..., rule="1D", label="left", closed="left")`, Prague `FTMO_TZ`

### Costs (ASSUMPTIONS — reuse C19)

| Item | Value | Note |
|---|---|---|
| contract_size | 5000 | FTMO XAG/USD catalogue |
| spread | 0.025 | ASSUMPTION (feed has no typical_spread) |
| commission | $3 / lot | ASSUMPTION — Gold metals harness parity |
| tick_value | 1.0 | price × contract |
| lots | `round(risk$ / (sl_dist × 5000), 2)`; below 0.01 stay flat; no 50-lot clamp (cap 100) |

### Periods

| Slice | Range |
|---|---|
| Fit | 2024-01-01 → 2025-11-07 |
| HO | 2025-11-08 → 2026-09-01 |
| Ext | 2026-09-02 → data end (likely UNAVAILABLE on this feed) |

## Gates (BOTH)

1. **Explorer-style** 30 Prague month-triplets: 1.10 + 1.155, floor 0.90, no day ≤−5%, TIME-zero scratch; report outside Aug2025–Feb2026 countable.
2. **Our Fit/HO/Ext** + ≤90d continuous / seq-reset windows + max DD ≤10%.

### Verdict

- **ACCEPT** if DD-legal, HO>0, leave-out OK, and (≥1 HO-era ≤90d window **OR** ≥1 outside-streak countable under Explorer bar). Ext N/A → may still ACCEPT on the OR clause; label Ext honestly.
- **CONDITIONAL** if DD-legal + some signal (Fit-only windows, thin outside, Ext gap) but not full ACCEPT.
- **REJECT** otherwise. No retune.

## Stop

One locked run at 2.50% (+ 2.60% sensitivity readout). Nothing live.
