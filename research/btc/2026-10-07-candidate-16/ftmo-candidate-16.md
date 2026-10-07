# FTMO BTC — Candidate 16 Spec

**Name:** H1 NR7 Breakout Exclusive Dual + Structural Stop R=1.5 + 0.75% Risk + Prague Kill  
**Status:** Research measurement only — live engines / MetaAPI / C4 / drip / FREEZE untouched  
**Prepared:** 2026-10-07 (America/New_York)  
**Chassis:** `h1-nr7-breakout`

**Scoreboard so far:**  
- C4 SMA50 exclusive dual R=1 → **CONDITIONAL** (fit fail; live path)  
- C5 SMA50 + slope E + ATR&lt;P75 → **ACCEPT** research @ 0.01; pace ~$0.5k/mo (too slow)  
- C6–C10 SMA50 family / scale / trail → REJECT or CONDITIONAL (pace/DD wall)  
- C11 H1 momentum exclusive dual R=2 → **REJECT** (negative HO, ~60% DD)  
- C12 C5 stack ×3 under 2% cap → **REJECT** (0/850; stack ≠ pace)  
- C13 London ORB exclusive dual R=1.5 → **REJECT** (leave-out fail + max DD 15% @0.75%)  
- C14 H1 z-score MR fade R=1.5 → **REJECT** (EDGE/DD; HO negative, max DD 60.3%)  
- C15 H4 BB squeeze breakout R=2 → **REJECT** near-miss (HO ~$1,291/mo; DD 7.4% legal; Ext −$1,823; 0/909 ≤60d)  
- Prior HF: raw H4-BREAK-6 / raw TSMOM-20 — **not revived**

---

## One-line thesis

On UTC **1-hour** bars, an **NR7** bar is one whose range (`high−low`) is the narrowest of the last **7** completed H1 ranges (including itself). At close of an NR7 bar `t`, set break levels = `high[t]` / `low[t]`. On subsequent H1 bars, first close beyond `high[t]` → LONG; first close beyond `low[t]` → SHORT; setup expires after **6** H1 bars with no break (first break wins). Stop = opposite side of the NR7 bar (long stop = NR7 low; short stop = NR7 high). Target = **1.5 × stop_dist** from entry (R=1.5). If stop_dist is so small that 0.75% risk sizes above 50 lots, clamp lots at 50 and document. Max 1 position. Size **0.75%** equity (also 0.50% and 1.0%). Prague-day realized kill **−3%** day-start. Entry = first M1 open at/after the **break** H1 bar end. Same-minute double-touch → stop. Ignore new NR7 signals while in a position or while a pending setup exists. **No SMA50 filter.**

## Locked NR7 / break rule (exact — use this, nothing else)

At close of bar `t` (0-based index; need `t ≥ 6`):

1. `range[i] = high[i] − low[i]` for `i ∈ {t−6 … t}`.  
2. Bar `t` is **NR7** iff `range[t] == min(range[t−6 … t])` (ties allowed: current equals the window minimum).  
3. If NR7 and no pending setup and not in a position → arm pending:  
   - `break_high = high[t]`, `break_low = low[t]`  
   - `nr7_idx = t`, `expire_idx = t + 6`  
   - Do **not** arm while a pending setup already exists or while in a position.  
4. On each subsequent bar `u` with `nr7_idx < u ≤ expire_idx` (watch bars = next 6 H1 closes):  
   - LONG if `close[u] > break_high`  
   - SHORT if `close[u] < break_low`  
   - First break wins; clear pending.  
   - If neither, continue.  
5. If `u > expire_idx` with no break → cancel pending (expired).  
6. If break fires but entry is blocked (in trade / kill / bad stop / lots) → pending is still **consumed** (break already happened).  
7. Entry clock: first M1 open at/after the **break bar** end (`label+1h`), not the NR7 bar.  
8. Stop: long → NR7 `break_low`; short → NR7 `break_high`.  
9. `stop_dist = |entry − stop|`; `target_dist = 1.5 × stop_dist`.  
10. Same-minute double-touch → **stop** (conservative).

**Not used:** ATR stops; SMA50; session ORB; BB squeeze; H1 mom/MR continuum signals; H4-BREAK-6 channel.

## Why this (a priori — not a fishing trip)

| Prior fact | Implication |
|---|---|
| C15 H4 squeeze was DD-legal but ~$1.3k/mo and Ext failed | Need **higher frequency** expansion chassis for more closed $/mo |
| C11 H1 mom / C14 H1 MR both failed | Not continuum mom/MR — NR7 is **range contraction → breakout** |
| C13 London ORB is session structure | NR7 is **pattern**, not London open |
| C7 H4-BREAK-6 is lookback-6 channel + often SMA50 | NR7 is narrowest-of-7 range, exclusive dual, no SMA50 |
| Crabel-style NR7 → expansion | Classic; tighter structural stops → more trades/mo at same % risk if edge exists |
| R=1.5 + structural stop | Risk defined by the pattern itself (ATR-free) |

**Not chosen / not revived:** SMA50 dual/C5 family; C11 H1 mom; C14 H1 z MR; C13 London ORB; C15 H4 BB squeeze; C7 H4-BREAK-6; C12 stack.

## Direction / timeframe

- **Direction:** Exclusive dual breakout — long **or** short by first break; never both  
- **Timeframe:** UTC **1-hour** signal bars; entry on next H1 open after **break** bar (first M1 at/after break bar end)  
- **Max positions:** 1  
- **Pending:** at most one NR7 setup; ignore new NR7 while pending or in trade  

## Entry / exit / invalidation (locked a priori)

1. **H1 bars:** resample M1 bid `"1h"`, label left, closed left, origin `2024-01-01 00:00 UTC`. Drop empty bins. Drop trailing incomplete bin.  
2. **NR7 / pending / break:** as locked rule above. Warmup: first possible NR7 at index 6.  
3. **Entry:** first M1 open at or after break H1 bar end (`label+1h`). Missing → next M1 open. Skip if entry would be through stop (`stop_dist ≤ 0`).  
4. **stop_dist** from structural NR7 opposite side (not ATR).  
5. **target_dist** = `1.5 × stop_dist` (**R=1.5** hard TP)  
6. Same-minute double touch → **stop**  
7. **Size:** `lots = round(equity × risk / stop_dist, 2)`, clamp [0.01, 50]; if raw size would exceed 50, clamp and count `lot_clamps`; skip if &lt; 0.01  
8. **Daily kill:** if Prague-day **realized** exit PnL so far ≤ **−3%** of that Prague day’s start equity → no new entries until next Prague day  
9. Ignore new NR7 while in a position or while pending exists  
10. Open at end of sample → not marked on official closed path ($0 / excluded from n)

## Risk / costs (ONE model — stick to it)

- **ASSUMPTION account:** $100,000 2-step  
- **Cost model:** FTMO BTCUSD — **spread = 15** price units × lots at exit; **commission = 0**; **swap = 0** (same model as C7/C11/C13/C14/C15 HF).  
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
**CONDITIONAL** only if A passes and B fails narrowly (edge ok but pace slow) — honest multi-month estimate, no fake ≤60d hope. Compare pace to C15’s ~$1,291/mo.

## ASSUMPTIONS

1. **ASSUMPTION — Account:** $100k 2-step; Challenge +$10k; Verification +$5k; daily −5%; max −10%.  
2. **ASSUMPTION — Data:** Merged Dukascopy M1 bid (main through 2026-09-01 + dukas-ext through ~2026-10-07); no invented prices.  
3. **ASSUMPTION — Costs:** spread=15 model (not C4/C5 %).  
4. **ASSUMPTION — 60d window:** both stages inside same 60 calendar days vs window-start (1.10 then 1.155).  
5. **ASSUMPTION — NR7 window=7, expire=6 bars, R=1.5, structural stop** locked a priori (Crabel-style; not fitted).  
6. **ASSUMPTION — NR7 ties:** current range equals window min → still NR7.  
7. **ASSUMPTION — lot clamp 50** when tiny NR7 range would oversized; document clamp count.  
8. Research only — **not deployable live** from this folder.

## Explicit non-goals

- Do not touch live engines, MetaAPI, VM, C4, drip, FREEZE, or any deploy.  
- Do not silently swap chassis if H1 NR7 path is broken — document and stop.  
- Do not milk C15 BB params into this runner.
