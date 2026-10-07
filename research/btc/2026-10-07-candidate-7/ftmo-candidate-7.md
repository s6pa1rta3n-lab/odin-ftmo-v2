# FTMO BTC — Candidate 7 Spec

**Name:** H4-BREAK Dual R=1 + SMA50 Regime + 0.75% Risk + Daily Kill  
**Status:** Research measurement only — live engines / MetaAPI / C4 / drip / FREEZE untouched  
**Prepared:** 2026-10-07 (America/New_York)

**Scoreboard so far:**  
- C4 SMA50 exclusive dual R=1 → **CONDITIONAL** (fit fail; live path)  
- C5 SMA50 + slope E + ATR&lt;P75 → **ACCEPT** research @ 0.01; pace ~$0.5k/mo (too slow)  
- C6 C5 scale probe → **REJECT** (≤60d needs illegal size)  
- Prior HF: H4-BREAK-6 had 4/30 floating 3-mo passes but ~14.8% max DD / floating −6.9% — **not revived as-is**

---

## One-line thesis

Take the only prior HF structure that showed any Challenge-like window passes (H4 6-bar break), and lock a **DD-legal frequency package**: trade **both** sides with daily SMA50 regime, replace the open-ended channel exit with a **hard R=1 TP**, size at **0.75% equity** (not 1%), stop at **1.0× H4 ATR** (tighter than 1.5), and add a **−3% Prague-day kill** so cascading losses cannot print a −5% day. Goal: enough closed dollars per month at legal risk to clear Challenge+Verification inside **≤60 calendar days** on equity-path windows — without C6’s size wall.

## Why this (not a fishing trip)

| Prior fact | Implication |
|---|---|
| C5/C6 daily SMA books are robust but ~1 trade/day max; scale hits 5% daily | Need **higher frequency**, not more size on C5 |
| H4-BREAK-6: 4 floating-inclusive 3-mo passes, sum net R ~49, but max DD 14.8% + floating −6.9% | Edge fragment exists; **DD path is the failure** |
| H4-BREAK-6: long-only, no TP, 1.5 ATR stop, 1% risk | Open risk + large risk% drives floating DD |
| Asia / PDHL / NR4 / most blankets: 0/30 on 3-mo rule | Do not revive those |
| C4/C5 SMA50 regime | Reuse as **direction filter only** (not the entry clock) |

**Not chosen:** raw H4-BREAK-6 revival; TSMOM20 (6 passes but −6% day / 18% DD); session Asia break (0 passes); drip without hard stops.

## Direction / timeframe

- **Direction:** Exclusive dual — long **or** short by SMA50 regime; never both; never counter-regime  
- **Timeframe:** UTC **4-hour** signal bars; entry on next M1 open after signal bar end  
- **Max positions:** 1  

## Entry / exit / invalidation (locked a priori)

1. **H4 bars:** resample M1 bid `"4h"`, label left, closed left, origin `2024-01-01 00:00 UTC`. Drop empty bins. Drop trailing incomplete bin.  
2. **ATR(14)** on H4: simple mean of last 14 true ranges (prior close), rounded 4 decimals. Not Wilder. Known at close of bar t.  
3. **Break signal at H4 close t:**  
   - LONG candidate if `close[t] > max(high[t-6..t-1])` and ATR defined &gt; 0  
   - SHORT candidate if `close[t] < min(low[t-6..t-1])` and ATR defined &gt; 0  
   - If both (should not happen), skip  
4. **Regime (prior completed UTC daily close vs SMA50):**  
   - prior close **&gt;** SMA50 → allow **long** only  
   - prior close **&lt;** SMA50 → allow **short** only  
   - equal / insufficient history → flat (skip)  
5. **Entry:** first M1 open at or after H4 bar end (`label+4h`). Missing → next M1 open. Skip if entry would be through stop.  
6. **stop_dist** = `1.0 × ATR(14)[t]`  
   - long stop = entry − stop_dist; short stop = entry + stop_dist  
7. **target_dist** = stop_dist (**R=1** hard TP)  
8. Same-minute double touch → **stop** (conservative)  
9. **Size:** `lots = round(equity × 0.0075 / stop_dist, 2)`, clamp [0.01, 50]; skip if &lt; 0.01  
10. **Daily kill:** if Prague-day **realized** exit PnL so far ≤ **−3%** of that Prague day’s start equity → no new entries until next Prague day  
11. Ignore signals while in a position (consumed)  
12. Open at end of sample → not marked on official closed path ($0 / excluded from n)

## Risk / costs (ONE model — stick to it)

- **ASSUMPTION account:** $100,000 2-step  
- **Cost model:** FTMO BTCUSD from `ftmo_asset_specs.json` — **spread = 15** price units × lots at exit; **commission = 0**; **swap = 0** (same model as H4-BREAK-6 / strategy-explorer HF survey).  
  - *Not* C4/C5’s 0.065%/side + swap est. Documented divergence intentional for HF parity with prior H4 measurement.  
- One planned stop ≈ **0.75%** equity (~$750 at $100k) — well inside −$5k daily  
- Research worst-day bar: path day PnL / day-start ≥ **−5%**; max peak-to-trough realized DD ≤ **10%** on full path at chosen risk

## Gates (all required for ACCEPT as fast vehicle)

**A — robustness / edge (at locked 0.75% risk):**  
1. Holdout (2025-11-08 → 2026-09-01) net after costs **&gt; 0**  
2. Extension (2026-09-02 → data end) net after costs **≥ 0**  
3. Leave-out two best HO Prague months → remaining HO net **&gt; 0**  
4. Worst Prague day (realized) ≥ **−5%** of that day’s start equity on full path; **0** days ≤ −5%  
5. Full-path max realized DD (peak→trough) ≤ **10%**  
6. Fit (2024-01-01 → 2025-11-07) net ≥ **−$10,000** (10% of $100k ASSUMPTION)

**B — ≤60-day Challenge+Verification:**  
7. Count of **60-calendar-day** Prague windows (starts each complete Prague day that has 60 days of path ahead) where equity path hits **≥1.10×** window-start **and** **≥1.155×** window-start, never **≤0.90×** start, and no Prague day in window ≤ **−5%** day-start — **≥ 1** such window on the full sample (prefer several)  
8. At locked risk, HO-like monthly pace **≥ ~$7,500/mo** **OR** Gate 7 shows real ≤60d both-step windows (Gate 7 preferred)  
9. One stop $ and worst historical day $ at locked risk stay within **−$5,000** daily and path max DD within **−$10,000** / 10%

**ACCEPT** only if A+B all pass. Else **REJECT** with best near-miss documented.  
**CONDITIONAL** only if A passes and B fails narrowly (e.g. windows exist but &lt;1 fully clean, or pace close).

## Diagnostics (not a new candidate)

- Optional ablation **after** decision: same rules at **0.50%** risk (DD safety check) — report only; does not re-lock C7.

## ASSUMPTIONS

1. **ASSUMPTION — Account:** $100k 2-step; Challenge +$10k; Verification +$5k; daily −5%; max −10%.  
2. **ASSUMPTION — Data:** Merged Dukascopy M1 bid (main through 2026-09-01 + dukas-ext through ~2026-10-07); no invented prices.  
3. **ASSUMPTION — Costs:** spread=15 model (not C4/C5 %).  
4. **ASSUMPTION — 60d window:** both stages inside same 60 calendar days vs window-start (1.10 then 1.155), matching prior 3-mo reading but shorter bar.  
5. Research only — **not deployable live** from this folder.

## Live

Do not touch live VM, MetaAPI, C4, drip, FREEZE_NEW_BUYS, or arm anything.
