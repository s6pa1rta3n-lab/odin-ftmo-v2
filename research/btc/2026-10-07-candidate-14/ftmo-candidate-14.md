# FTMO BTC — Candidate 14 Spec

**Name:** H1 Z-Score Mean-Reversion Fade Exclusive Dual + Hard ATR Stop R=1.5 + 0.75% Risk + Prague Kill  
**Status:** Research measurement only — live engines / MetaAPI / C4 / drip / FREEZE untouched  
**Prepared:** 2026-10-07 (America/New_York)  
**Chassis:** `h1-zscore-mr`

**Scoreboard so far:**  
- C4 SMA50 exclusive dual R=1 → **CONDITIONAL** (fit fail; live path)  
- C5 SMA50 + slope E + ATR&lt;P75 → **ACCEPT** research @ 0.01; pace ~$0.5k/mo (too slow)  
- C6–C10 SMA50 family / scale / trail → REJECT or CONDITIONAL (pace/DD wall)  
- C11 H1 momentum exclusive dual R=2 → **REJECT** (negative HO, ~60% DD)  
- C12 C5 stack ×3 under 2% cap → **REJECT** (0/850; stack ≠ pace)  
- C13 London ORB exclusive dual R=1.5 → **REJECT** (leave-out fail + max DD 15% @0.75%)  
- Prior HF: raw H4-BREAK-6 / raw TSMOM-20 — **not revived**

---

## One-line thesis

On UTC **1-hour** bars, compute `z = (close − SMA(48)) / stdev(48 of closes)`. When `|z| ≥ 2.0` at H1 close, **fade toward the mean** — SHORT if `z ≥ +2`, LONG if `z ≤ −2`. Stop = `1.0 × ATR(14)` H1 from entry; target = `1.5 × stop_dist` (R=1.5 hard TP). Max 1 position. Size at **0.75%** equity (also report 0.50% and 1.0%). Prague-day realized kill at **−3%** of day-start equity. Entry = first M1 open at/after signal H1 bar end. Same-minute double-touch → stop. Skip if ATR undefined or `stop_dist ≤ 0` or lots &lt; 0.01. **No SMA50 regime filter** (brand-new chassis — SMA48 is only the mean inside the z-score, not a trend gate).

## Why this (a priori — not a fishing trip)

| Prior fact | Implication |
|---|---|
| C11 H1 momentum failed hard (negative HO, ~60% DD) | Mean-reversion is the **complementary** H1 hypothesis — opposite of trend-follow mom, not a retweak |
| C13 ORB had some HO edge but failed leave-out + DD | Need a different edge source: **statistical stretch** vs session structure |
| Hard ATR stop + R + fractional risk + Prague kill | DD package that C7/C11 used; C13 showed session structure alone isn’t enough for ≤60d legality |
| SMA50 dual / C5–C12 / C13 ORB / H4-BREAK-6 raw / C11 mom | **Not revived** |

**Not chosen:** any SMA50 dual entry; C11 mom retweak; another ORB session; raw no-stop books.

## Direction / timeframe

- **Direction:** Exclusive dual fade — long **or** short by z-sign; never both; never “with” the stretch  
- **Timeframe:** UTC **1-hour** signal bars; entry on next H1 open (first M1 at/after signal bar end)  
- **Max positions:** 1  

## Entry / exit / invalidation (locked a priori)

1. **H1 bars:** resample M1 bid `"1h"`, label left, closed left, origin `2024-01-01 00:00 UTC`. Drop empty bins. Drop trailing incomplete bin.  
2. **ATR(14)** on H1: simple mean of last 14 true ranges (prior close), rounded 4 decimals. Not Wilder. Known at close of bar t.  
3. **SMA(48)** on H1 close: rolling mean of last 48 completed H1 closes, known at close of bar t.  
4. **stdev(48)** on H1 close: population standard deviation (ddof=0) of the same 48 closes used for SMA(48). If stdev ≤ 0 → skip (z undefined).  
5. **z[t]** = `(close[t] − SMA48[t]) / stdev48[t]`  
6. **Signal at H1 close t** (prior completed H1 only):  
   - SHORT if `z[t] ≥ +2.0` and ATR defined &gt; 0  
   - LONG if `z[t] ≤ −2.0` and ATR defined &gt; 0  
   - Else skip  
7. **Entry:** first M1 open at or after H1 bar end (`label+1h`). Missing → next M1 open. Skip if entry would be through stop.  
8. **stop_dist** = `1.0 × ATR(14)[t]`  
   - long stop = entry − stop_dist; short stop = entry + stop_dist  
9. **target_dist** = `1.5 × stop_dist` (**R=1.5** hard TP)  
10. Same-minute double touch → **stop** (conservative)  
11. **Size:** `lots = round(equity × risk / stop_dist, 2)`, clamp [0.01, 50]; skip if &lt; 0.01 or stop_dist ≤ 0  
12. **Daily kill:** if Prague-day **realized** exit PnL so far ≤ **−3%** of that Prague day’s start equity → no new entries until next Prague day  
13. Ignore signals while in a position (consumed)  
14. Open at end of sample → not marked on official closed path ($0 / excluded from n)

## Risk / costs (ONE model — stick to it)

- **ASSUMPTION account:** $100,000 2-step  
- **Cost model:** FTMO BTCUSD — **spread = 15** price units × lots at exit; **commission = 0**; **swap = 0** (same model as C7/C11/C13 HF).  
  - *Not* C4/C5’s 0.065%/side + swap est. Documented divergence intentional for HF parity.  
- Locked risk: **0.75%** equity per trade; also report **0.50%** and **1.0%** paths  
- Research worst-day bar: path day PnL / day-start ≥ **−5%**; max peak-to-trough realized DD ≤ **10%** on full path at chosen risk

## Periods

- Fit: 2024-01-01 → 2025-11-07  
- Holdout: 2025-11-08 → 2026-09-01  
- Extension: 2026-09-02 → data end  
- Prague day = Europe/Prague for kill / worst-day / DD / leave-out months  

## Gates (all required for ACCEPT as fast vehicle)

**A — robustness / edge (at locked 0.75% risk):**  
1. Holdout (2025-11-08 → 2026-09-01) net after costs **&gt; 0**  
2. Extension (2026-09-02 → data end) net after costs **≥ 0**  
3. Leave-out two best HO Prague months → remaining HO net **&gt; 0**  
4. Worst Prague day (realized) ≥ **−5%** of that day’s start equity on full path; **0** days ≤ −5%  
5. Full-path max realized DD (peak→trough) ≤ **10%**  
6. Fit (2024-01-01 → 2025-11-07) net ≥ **−$10,000** (10% of $100k ASSUMPTION)

**B — ≤60-day Challenge+Verification:**  
7. Count of **60-calendar-day** Prague windows where equity path hits **≥1.10×** window-start **and** **≥1.155×** window-start, never **≤0.90×** start, and no Prague day in window ≤ **−5%** day-start — **≥ 1** such window  
8. At locked risk, HO-like monthly pace **≥ ~$7,500/mo** **OR** Gate 7 shows real ≤60d both-step windows  
9. One stop $ and worst historical day $ at locked risk stay within **−$5,000** daily and path max DD within **−$10,000** / 10%

**ACCEPT** only if A+B all pass. Else **REJECT** with best near-miss documented.  
**CONDITIONAL** only if A passes and B fails narrowly (edge ok but pace slow) — honest multi-month estimate, no fake ≤60d hope.

## ASSUMPTIONS

1. **ASSUMPTION — Account:** $100k 2-step; Challenge +$10k; Verification +$5k; daily −5%; max −10%.  
2. **ASSUMPTION — Data:** Merged Dukascopy M1 bid (main through 2026-09-01 + dukas-ext through ~2026-10-07); no invented prices.  
3. **ASSUMPTION — Costs:** spread=15 model (not C4/C5 %).  
4. **ASSUMPTION — 60d window:** both stages inside same 60 calendar days vs window-start (1.10 then 1.155).  
5. **ASSUMPTION — Z threshold |z|≥2.0, lookback 48, R=1.5, ATR stop 1.0×** locked a priori (complement to C11 mom; not fitted).  
6. **ASSUMPTION — stdev** = population (ddof=0) of the same 48 closes as SMA48.  
7. Research only — **not deployable live** from this folder.

## Explicit non-goals

- Do not touch live engines, MetaAPI, VM, C4, drip, FREEZE, or any deploy.  
- Do not revive SMA50 dual/C5 family, C6–C12 paths, C13 ORB, H4-BREAK-6 raw, or C11 H1 momentum.  
- No fishing sweep — one locked chassis.
