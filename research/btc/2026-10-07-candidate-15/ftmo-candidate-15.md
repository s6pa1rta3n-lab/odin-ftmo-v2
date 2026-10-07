# FTMO BTC — Candidate 15 Spec

**Name:** H4 Bollinger Squeeze Breakout Exclusive Dual + Hard ATR Stop R=2 + 0.75% Risk + Prague Kill  
**Status:** Research measurement only — live engines / MetaAPI / C4 / drip / FREEZE untouched  
**Prepared:** 2026-10-07 (America/New_York)  
**Chassis:** `h4-bb-squeeze`

**Scoreboard so far:**  
- C4 SMA50 exclusive dual R=1 → **CONDITIONAL** (fit fail; live path)  
- C5 SMA50 + slope E + ATR&lt;P75 → **ACCEPT** research @ 0.01; pace ~$0.5k/mo (too slow)  
- C6–C10 SMA50 family / scale / trail → REJECT or CONDITIONAL (pace/DD wall)  
- C11 H1 momentum exclusive dual R=2 → **REJECT** (negative HO, ~60% DD)  
- C12 C5 stack ×3 under 2% cap → **REJECT** (0/850; stack ≠ pace)  
- C13 London ORB exclusive dual R=1.5 → **REJECT** (leave-out fail + max DD 15% @0.75%)  
- C14 H1 z-score MR fade R=1.5 → **REJECT** (EDGE/DD; HO negative, max DD 60.3%)  
- Prior HF: raw H4-BREAK-6 / raw TSMOM-20 — **not revived**

---

## One-line thesis

On UTC **4-hour** bars, compute Bollinger(20, 2σ) on close and `bandwidth = (upper−lower)/middle`. A squeeze is active when bandwidth ≤ the 10th percentile of the prior 100 completed H4 bandwidth values (known at bar t close — no lookahead). On the first H4 close that exits the squeeze via a **band break** (locked rule below), take direction from the break: LONG if close > upper band, SHORT if close < lower band; if neither, skip. Stop = `1.0 × ATR(14)` H4 from entry; target = `2.0 × stop_dist` (R=2 hard TP — a priori for rare squeeze events). Max 1 position. Size at **0.75%** equity (also report 0.50% and 1.0%). Prague-day realized kill at **−3%** of day-start equity. Entry = first M1 open at/after signal H4 bar end. Same-minute double-touch → stop. **No SMA50 regime filter.**

## Locked squeeze-exit rule (exact — use this, nothing else)

At close of bar `t` (0-based index):

1. `middle[t] = SMA(20)` of `close[t−19..t]` (population window of 20 closes).  
2. `std[t] =` population stdev (ddof=0) of the same 20 closes.  
3. `upper[t] = middle[t] + 2·std[t]`; `lower[t] = middle[t] − 2·std[t]`.  
4. `bw[t] = (upper[t] − lower[t]) / middle[t]` (skip if middle ≤ 0).  
5. `squeeze_flag[t] = True` iff `bw[t] ≤ percentile_10(bw[t−99..t])` — i.e. the inclusive window of the last **100** completed bandwidth values ending at `t` (indices `t−99` … `t`). All inputs known at close `t`; no future bars.  
6. **Break signal at close t** (requires `t ≥ 1` and `squeeze_flag[t−1]` defined):  
   - LONG if `squeeze_flag[t−1] == True` **and** `close[t] > upper[t]`  
   - SHORT if `squeeze_flag[t−1] == True` **and** `close[t] < lower[t]`  
   - Else skip (including: still in squeeze, or squeeze exit without closing outside the band)  
7. If both long and short would fire (impossible with one close vs bands), skip.

**Not used:** bandwidth rising above P10 alone as the exit trigger. Break = **prior bar in squeeze + this bar closes outside the band**. Documented a priori so measurement cannot silently swap to a bandwidth-only exit.

## Why this (a priori — not a fishing trip)

| Prior fact | Implication |
|---|---|
| C11 H1 mom / C14 H1 MR both failed | Need a **volatility-regime** chassis, not continuum mom/MR |
| C13 ORB had HO edge but failed leave-out + DD | Session structure ≠ squeeze→expansion |
| C7 H4-BREAK-6 was channel break + SMA50 regime | This is **BB squeeze breakout**, no SMA50, no lookback-6 channel |
| Squeeze → expansion is a classic vol-regime hypothesis | R=2 justified by rarer setups (fewer trades, need more $ per win for ≤60d pace) |
| Hard ATR stop + R + fractional risk + Prague kill | DD package from C7/C11/C13/C14 |

**Not chosen / not revived:** SMA50 dual/C5 family; C11 H1 mom; C14 H1 z MR; C13 London ORB; C7 H4-BREAK-6; C12 stack.

## Direction / timeframe

- **Direction:** Exclusive dual breakout — long **or** short by band side; never both  
- **Timeframe:** UTC **4-hour** signal bars; entry on next H4 open (first M1 at/after signal bar end)  
- **Max positions:** 1  

## Entry / exit / invalidation (locked a priori)

1. **H4 bars:** resample M1 bid `"4h"`, label left, closed left, origin `2024-01-01 00:00 UTC`. Drop empty bins. Drop trailing incomplete bin.  
2. **ATR(14)** on H4: simple mean of last 14 true ranges (prior close), rounded 4 decimals. Not Wilder. Known at close of bar t.  
3. **Bollinger / squeeze / break:** as locked rule above. Warmup: need ≥100 bandwidth values → first possible `squeeze_flag` at index 99; first possible signal at index ≥ 100.  
4. **Entry:** first M1 open at or after H4 bar end (`label+4h`). Missing → next M1 open. Skip if entry would be through stop.  
5. **stop_dist** = `1.0 × ATR(14)[t]`  
   - long stop = entry − stop_dist; short stop = entry + stop_dist  
6. **target_dist** = `2.0 × stop_dist` (**R=2** hard TP)  
7. Same-minute double touch → **stop** (conservative)  
8. **Size:** `lots = round(equity × risk / stop_dist, 2)`, clamp [0.01, 50]; skip if &lt; 0.01 or stop_dist ≤ 0  
9. **Daily kill:** if Prague-day **realized** exit PnL so far ≤ **−3%** of that Prague day’s start equity → no new entries until next Prague day  
10. Ignore signals while in a position (consumed)  
11. Open at end of sample → not marked on official closed path ($0 / excluded from n)

## Risk / costs (ONE model — stick to it)

- **ASSUMPTION account:** $100,000 2-step  
- **Cost model:** FTMO BTCUSD — **spread = 15** price units × lots at exit; **commission = 0**; **swap = 0** (same model as C7/C11/C13/C14 HF).  
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
5. **ASSUMPTION — BB(20,2σ), P10 of 100 bw, R=2, ATR stop 1.0×** locked a priori (classic squeeze→expansion; not fitted).  
6. **ASSUMPTION — stdev** for BB = population (ddof=0) of the same 20 closes as SMA20.  
7. **ASSUMPTION — percentile_10** = numpy `np.percentile(window, 10)` (linear).  
8. Research only — **not deployable live** from this folder.

## Explicit non-goals

- Do not touch live engines, MetaAPI, VM, C4, drip, FREEZE, or any deploy.  
- Do not revive SMA50 dual/C5 family, C6–C12 paths, C13 ORB, C14 H1 z MR, H4-BREAK-6 raw, or C11 H1 momentum.  
- No fishing sweep — one locked chassis.  
- If BB/H4 path is broken (missing data), document and stop — do **not** silently swap chassis.
