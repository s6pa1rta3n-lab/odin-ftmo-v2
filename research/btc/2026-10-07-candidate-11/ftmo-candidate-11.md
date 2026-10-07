# FTMO BTC — Candidate 11 Spec

**Name:** H1 Momentum Exclusive Dual + Hard ATR Stop R=2 + 0.75% Risk + Prague Kill  
**Status:** Research measurement only — live engines / MetaAPI / C4 / drip / FREEZE untouched  
**Prepared:** 2026-10-07 (America/New_York)

**Scoreboard so far:**  
- C4 SMA50 exclusive dual R=1 → **CONDITIONAL** (fit fail; live path)  
- C5 SMA50 + slope E + ATR&lt;P75 → **ACCEPT** research @ 0.01; pace ~$0.5k/mo (too slow)  
- C6 C5 scale probe → **REJECT** (≤60d needs illegal size)  
- C7 H4-BREAK Dual R=1 → **REJECT** (~$508/mo; 0 windows; DD 17%)  
- C8 hard R=2 on SMA50 → **REJECT** (edge destroyed)  
- C9 ATR trail → **CONDITIONAL** (DD; ATR never left BE)  
- C10 R-trail → **CONDITIONAL** (Gate A; Gate B PACE+DD; SMA50 exit milking exhausted)  
- Prior HF: raw H4-BREAK-6 / raw TSMOM-20 — **not revived** without hard stops + DD fix

---

## One-line thesis

Leave the SMA50 **daily-entry** family. Trade an **H1 momentum exclusive dual** with **hard ATR stops** and **a priori R=2** targets: more decisions per day than daily SMA50, but still one position, fractional risk, and a Prague-day kill so cascading H1 losses cannot print a −5% day. Goal: enough closed dollars per month at legal risk to clear Challenge+Verification inside **≤60 calendar days**.

## Why this (not a fishing trip)

| Prior fact | Implication |
|---|---|
| C5–C10 SMA50 daily entry exhausted for ≤60d | Need a **new entry chassis**, not another dual-exit tweak |
| C7 H4 break @ R=1: ~$500/mo, DD 17% | Frequency alone without R asymmetry / kill didn’t clear 60d |
| C8 hard R=2 on **daily** SMA50 killed edge (~30% WR) | R=2 on a **different market** (H1 ATR stops) is a priori — not the $412.91 book |
| Raw H4-BREAK-6 / TSMOM-20 had pass windows but illegal DD | Hard stop + 0.75% risk + −3% day kill required |
| Daily SMA50 regime still useful as filter elsewhere | Here regime is **H1 SMA50** (same clock as entry) — exclusive dual |

**Not chosen:** SMA50 dual exit variants; raw no-stop TSMOM-20; raw H4-BREAK-6 without hard stops.

**Fallback if H1 path broken:** London/NY session break of prior session H/L, exclusive dual via daily SMA50 as filter only, stop = session-range fraction, R=1.5, same risk/kill — only if Dukas M1→H1 path fails.

## Direction / timeframe

- **Direction:** Exclusive dual — long **or** short by H1 SMA50 + candle direction; never both; never counter-regime  
- **Timeframe:** UTC **1-hour** signal bars; entry on next H1 open (first M1 at/after signal bar end)  
- **Max positions:** 1  

## Entry / exit / invalidation (locked a priori)

1. **H1 bars:** resample M1 bid `"1h"`, label left, closed left, origin `2024-01-01 00:00 UTC`. Drop empty bins. Drop trailing incomplete bin.  
2. **ATR(14)** on H1: simple mean of last 14 true ranges (prior close), rounded 4 decimals. Not Wilder. Known at close of bar t.  
3. **SMA(50)** on H1 close: rolling mean of last 50 completed H1 closes, known at close of bar t.  
4. **Signal at H1 close t** (prior completed H1 only):  
   - LONG if `close[t] > SMA50[t]` **and** `close[t] > open[t]` and ATR defined &gt; 0  
   - SHORT if `close[t] < SMA50[t]` **and** `close[t] < open[t]` and ATR defined &gt; 0  
   - Else skip (including equal close/SMA or doji)  
5. **Entry:** first M1 open at or after H1 bar end (`label+1h`). Missing → next M1 open. Skip if entry would be through stop.  
6. **stop_dist** = `1.0 × ATR(14)[t]`  
   - long stop = entry − stop_dist; short stop = entry + stop_dist  
7. **target_dist** = `2.0 × stop_dist` (**R=2** hard TP) — a priori for H1 ATR book (not the daily 412.91 book)  
8. Same-minute double touch → **stop** (conservative)  
9. **Size:** `lots = round(equity × 0.0075 / stop_dist, 2)`, clamp [0.01, 50]; skip if &lt; 0.01 or stop_dist ≤ 0  
10. **Daily kill:** if Prague-day **realized** exit PnL so far ≤ **−3%** of that Prague day’s start equity → no new entries until next Prague day  
11. Ignore signals while in a position (consumed)  
12. Open at end of sample → not marked on official closed path ($0 / excluded from n)

## Risk / costs (ONE model — stick to it)

- **ASSUMPTION account:** $100,000 2-step  
- **Cost model:** FTMO BTCUSD — **spread = 15** price units × lots at exit; **commission = 0**; **swap = 0** (same model as H4-BREAK-6 / C7 HF survey).  
  - *Not* C4/C5’s 0.065%/side + swap est. Documented divergence intentional for HF parity.  
- Locked risk: **0.75%** equity per trade; also report **0.50%** and **1.0%** paths  
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

- Report same rules at **0.50%** and **1.0%** risk (DD / window table).  
- Compare $/mo and 60d hits vs C5 (~$450–480/mo @0.01; 0 windows at legal size) and C10 (0/252 @1%).

## ASSUMPTIONS

1. **ASSUMPTION — Account:** $100k 2-step; Challenge +$10k; Verification +$5k; daily −5%; max −10%.  
2. **ASSUMPTION — Data:** Merged Dukascopy M1 bid (main through 2026-09-01 + dukas-ext through ~2026-10-07); no invented prices.  
3. **ASSUMPTION — Costs:** spread=15 model (not C4/C5 %).  
4. **ASSUMPTION — 60d window:** both stages inside same 60 calendar days vs window-start (1.10 then 1.155).  
5. **ASSUMPTION — R=2 on H1 ATR** is a priori for this chassis (different market from daily 412.91 R=1 book).  
6. Research only — **not deployable live** from this folder.

## Live

Do not touch live VM, MetaAPI, C4, drip, FREEZE_NEW_BUYS, or arm anything.

## If REJECT

State binding constraint. Recommend whether BTC-only ≤60d at legal DD looks **structurally implausible** given HF survey + C5–C11, **or** name one last chassis class worth trying (e.g. multi-position capped aggregate risk).
