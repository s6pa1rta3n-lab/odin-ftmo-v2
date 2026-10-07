# Candidate 4b — Fit-Repair Filters on C4 Base

**Decision: CONDITIONAL**

**One sentence:** CONDITIONAL Candidate 4b: no filter meets all gates. Closest useful: **E SMA50 slope (rising long / falling short)** (fit $-6,693.22, HO $7,229.50, leave-out $2,320.09, gates all=False).

**Measured:** 2026-10-07 07:47:14 EDT
**Live engines:** not modified.
**Base:** C4 SMA50 exclusive dual, stop=target 412.91 (R=1), max 1.

## Recommendation

Keep **C4 baseline** as research baseline (leave-out already works). Best preserving filter was **E SMA50 slope (rising long / falling short)** (fit $-6,693.22, still short of −$5k by $1,693.22). Wait for more OOS rather than Candidate 5 unless fit worsens.

## Comparison table (full cost $)

| Variant | Fit full | HO full | Ext full | Leave-out full (dropped months) | HO months green | Worst HO / Ext | All gates? |
|---|---:|---:|---:|---|---|---|---|
| C4 baseline (no filter) | -8,949.23 | 7,158.94 | 786.15 | 2,251.35 (['2025-11', '2026-04']) | 8/11 | -825.82 / -825.82 | NO |
| A Volatility gate (ATR < 100d median) | -3,251.21 | 3,927.86 | -424.76 | -571.88 (['2026-04', '2026-06']) | 5/9 | -825.82 / -825.82 | NO |
| B Trend strength |c-SMA50|/SMA50 ≥ 1% | -7,651.22 | 5,120.49 | 786.15 | 211.11 (['2025-11', '2026-04']) | 8/11 | -825.82 / -825.82 | NO |
| D Time stop 48h → next 00:00 UTC | -8,949.23 | 7,751.35 | 786.15 | 2,843.76 (['2025-11', '2026-04']) | 8/11 | -825.82 / -825.82 | NO |
| E SMA50 slope (rising long / falling short) | -6,693.22 | 7,229.50 | 786.15 | 2,320.09 (['2025-11', '2026-04']) | 7/11 | -825.82 / -825.82 | NO |

## Gate pass matrix

| Variant | g1 HO | g2 Ext | g3 Leave-out | g4 Worst-day | g5 Fit≥−5k | g6 Months≥50% | Fit≥0? |
|---|---|---|---|---|---|---|---|
| C4 baseline (no filter) | Y | Y | Y | Y | N | Y | N |
| A Volatility gate (ATR < 100d median) | Y | N | N | Y | Y | Y | N |
| B Trend strength |c-SMA50|/SMA50 ≥ 1% | Y | Y | Y | Y | N | Y | N |
| D Time stop 48h → next 00:00 UTC | Y | Y | Y | Y | N | Y | N |
| E SMA50 slope (rising long / falling short) | Y | Y | Y | Y | N | Y | N |

## Per-variant notes

### A Volatility gate (ATR < 100d median)

- Trades fit/HO/ext: 291/192/9; HO win rate 52.6%; L/S HO 92/100
- Filter skips (fit/HO entry opportunities blocked): 298/75
- vs C4 baseline fit Δ = $5,698.02; HO Δ = $-3,231.08

### B Trend strength |c-SMA50|/SMA50 ≥ 1%

- Trades fit/HO/ext: 527/235/34; HO win rate 52.8%; L/S HO 88/147
- Filter skips (fit/HO entry opportunities blocked): 52/31
- vs C4 baseline fit Δ = $1,298.01; HO Δ = $-2,038.45

### D Time stop 48h → next 00:00 UTC

- Trades fit/HO/ext: 578/262/34; HO win rate 53.8%; L/S HO 103/159
- Time-stop exits HO: 1
- Filter skips (fit/HO entry opportunities blocked): 0/0
- vs C4 baseline fit Δ = $0.00; HO Δ = $592.41

### E SMA50 slope (rising long / falling short)

- Trades fit/HO/ext: 413/206/34; HO win rate 54.4%; L/S HO 65/141
- Filter skips (fit/HO entry opportunities blocked): 177/63
- vs C4 baseline fit Δ = $2,256.01; HO Δ = $70.56

## ASSUMPTIONS

1. Same C4 base rules; filters use prior-day info only (no look-ahead).
2. **A:** prior ATR(14) < median of ATR values on the inclusive prior 100 UTC days (need ≥50 non-null).
3. **B:** |prior close − SMA50| / SMA50 ≥ 1%.
4. **D:** if still open at first 00:00 UTC at/after entry+48h, exit at that bar open (barriers still win if hit on that bar).
5. **E:** long only if SMA50(prior) > SMA50(prior−10 calendar days in series); short only if SMA50 falling.
6. Leave-out = drop two best HO ET exit months by full-cost net.
7. Real Dukas M1 merged; no live changes.

## User summary (≤15 lines)

1. **CONDITIONAL** — tried A/B/D/E one at a time on C4 base.
2. C4 baseline: fit **$-8,949.23**, HO **$7,158.94**, leave-out **$2,251.35**, ext **$786.15**.
3. **A**: fit $-3,251.21 · HO $3,927.86 · leave-out $-571.88 · ext $-424.76 · all-gates FAIL.
4. **B**: fit $-7,651.22 · HO $5,120.49 · leave-out $211.11 · ext $786.15 · all-gates FAIL.
5. **D**: fit $-8,949.23 · HO $7,751.35 · leave-out $2,843.76 · ext $786.15 · all-gates FAIL.
6. **E**: fit $-6,693.22 · HO $7,229.50 · leave-out $2,320.09 · ext $786.15 · all-gates FAIL.
7. CONDITIONAL Candidate 4b: no filter meets all gates. Closest useful: **E SMA50 slope (rising long / falling short)** (fit $-6,693.22, HO $7,229.50, leave-out $2,320.09, gates all=False).
8. Keep **C4 baseline** as research baseline (leave-out already works). Best preserving filter was **E SMA50 slope (rising long / falling short)** (fit $-6,693.22, still short of −$5k by $1,693.22). Wait for more OOS rather than Candidate 5 unless fit worsens.
9. Live engines untouched.
