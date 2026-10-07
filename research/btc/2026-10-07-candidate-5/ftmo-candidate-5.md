# FTMO BTC — Candidate 5 Spec

**Name:** SMA50 Slope + Elevated-Vol Skip (exclusive dual R=1)  
**Status:** Research measurement only — live engines untouched  
**Prepared:** 2026-10-07 (America/New_York)

**Scoreboard so far:**  
- C1 SMA dual R=3 → **REJECT** (leave-out)  
- C2 SMA50 long R=1.5 → **CONDITIONAL** (leave-out + fit)  
- C3 4H Donchian ATR → **REJECT** (OOS + oversized stops)  
- C4 SMA50 exclusive dual R=1 → **CONDITIONAL** (fit −$8,949)  
- C4b filters A/B/D/E → none cleared all gates; closest **E** (fit −$6,693)

---

## One-line thesis

Keep C4’s SMA50 exclusive dual R=1 book, add C4b’s slope confirmation (trade with SMA50 drift), and skip only **elevated** volatility days (ATR ≥ 75th percentile of the prior 100d ATR) — milder than C4b-A’s median gate — aiming to clear fit ≥ −$5k without repeating A’s leave-out/extension kill.

## Direction / timeframe

- **Direction:** Exclusive dual (long **or** short by regime; never both)  
- **Timeframe:** Daily regime; entry at next **00:00 UTC** M1 open  
- **Max positions:** 1 total  

## Entry / exit / invalidation

- **Regime (prior completed UTC daily close vs SMA50):**  
  - prior close **>** SMA50 → **long** candidate  
  - prior close **<** SMA50 → **short** candidate  
  - equal → **flat**  
- **Filter E — SMA50 slope (prior-day only):**  
  - long only if SMA50(prior) **>** SMA50(prior−10 series days)  
  - short only if SMA50(prior) **<** SMA50(prior−10 series days)  
  - insufficient history → skip  
- **Filter V75 — elevated-vol skip (prior-day only):**  
  - prior ATR(14) must be **<** the 75th percentile of ATR values on the inclusive prior **100** UTC days  
  - need ≥50 non-null ATRs in that window; else skip  
  - **ASSUMPTION a priori:** milder than C4b-A (median / 50th); only skip top-quartile vol  
- **Entry:** 00:00 UTC M1 open when flat and both filters pass; missing midnights skipped  
- **stop_dist** = `412.91` (1× catalogue measured stop)  
- **target_dist** = `412.91` (R=1)  
- Same-minute double touch → **stop**  
- Open at end of slice → $0  

## Risk / costs

- Volume **0.01** catalogue dollars → one full stop ≈ **−$412.91**  
- Commission **0.065%**/side; swap est. **|−30%|/360** per UTC midnight held  
- Research worst-day budget: raw ≥ **−$2,000**  

## Gates (all required for ACCEPT)

1. Holdout after costs **> 0** and **> buy-only −$8,258.20**  
2. Extension after costs **≥ 0**  
3. Leave-out two best holdout months → remaining after costs **> 0**  
4. Worst ET day raw ≥ **−$2,000** on HO and ext  
5. Fit after costs ≥ **−$5,000**  
6. Holdout months with trades: **≥50%** green on full cost  

**ACCEPT** only if all pass; else **CONDITIONAL** or **REJECT**.

## Why this (not a fishing trip)

| Prior fact | Implication |
|---|---|
| C4 fails only fit (−$8,949) | Need fit repair that preserves HO/ext/leave-out |
| C4b-E slope: fit −$6,693, HO/ext/leave-out intact | Best preserving filter; still ~$1.7k short of −$5k |
| C4b-A median ATR: fit cleared, leave-out/ext died | Median vol gate too aggressive for OOS |
| Combine E + **milder** vol (P75) | One structural add-on: confirm trend + skip only elevated chop |

**Not chosen here:** SMA100 exclusive dual (prior robustness already flagged weak long book under larger stops); asymmetric short-primary (would be a second candidate); survey non-SMA ideas (need full FTMO gate re-measure first).

## Diagnostics (not a new candidate)

- Optional ablation: **E-only** (no V75) re-confirm C4b numbers on same runner — reported as diagnostic.

## ASSUMPTIONS

1. **ASSUMPTION — Data:** Merged Dukascopy M1 bid; no invented prices.  
2. **ASSUMPTION — Regime lag:** Prior close vs SMA50; filters use prior-day info only.  
3. **ASSUMPTION — Slope window:** 10 series days (locked from C4b-E; not re-tuned).  
4. **ASSUMPTION — Vol threshold:** 75th percentile of prior 100d ATR (a priori milder than A’s median; not fit-optimized).  
5. **ASSUMPTION — ATR:** Wilder ATR(14) on UTC daily OHLC (same construction as C4b-A).  
6. **ASSUMPTION — Leave-out:** Two best HO months by ET exit-month full-cost net.  
7. **ASSUMPTION — Exclusive:** No new entry while any position open.  
8. **ASSUMPTION — Live untouched.**  

## Slices

| Slice | UTC entry midnights |
|---|---|
| Fit | 2024-01-01 → 2025-11-07 |
| Holdout | 2025-11-08 → 2026-09-01 |
| Extension | 2026-09-02 → last available |

Results: `/workspace/btc-strategies/candidate-5-results.md`
