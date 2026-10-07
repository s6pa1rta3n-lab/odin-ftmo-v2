# FTMO BTC — Candidate 13 Spec

**Name:** London Opening Range Breakout (ORB) Exclusive Dual + Opposite-Side Stop R=1.5 + 0.75% Risk + Prague Kill  
**Status:** Research measurement only — live engines / MetaAPI / C4 / drip / FREEZE untouched  
**Prepared:** 2026-10-07 (America/New_York)

**Scoreboard so far:**  
- C4 SMA50 exclusive dual R=1 → **CONDITIONAL** (fit fail; live path)  
- C5 SMA50 + slope E + ATR&lt;P75 → **ACCEPT** research @ 0.01; pace ~$0.5k/mo (too slow)  
- C6 C5 scale probe → **REJECT** (≤60d needs illegal size)  
- C7 H4-BREAK Dual R=1 → **REJECT** (~$508/mo; 0 windows; DD 17%)  
- C8 hard R=2 on SMA50 → **REJECT** (edge destroyed)  
- C9 ATR trail → **CONDITIONAL** (DD; ATR never left BE)  
- C10 R-trail → **CONDITIONAL** (Gate A; Gate B PACE+DD)  
- C11 H1 mom R=2 → **REJECT** (negative HO edge; ~60% DD)  
- C12 multi-pos C5 stack → **REJECT** (0/850 windows; structural call)  
- **C13** = brand-new session-structure chassis (no SMA50 entry/regime)

---

## One-line thesis

**London Opening Range Breakout (ORB) exclusive dual:** trade break of the first completed London hour range (07:00–08:00 UTC), long on break of that hour’s high, short on break of that hour’s low, hard stop at **opposite side of the range** (locked a priori — not mid), target R=1.5 × stop distance, max 1 position, size at 0.75% equity, Prague-day realized kill at −3% of day-start equity.

## Why this (a priori, not fishing)

| Prior fact | Implication |
|---|---|
| C5–C12 / SMA50 daily family exhausted for ≤60d pace at legal DD | Need a **new entry chassis**, not another SMA50 tweak |
| C7 H4-break dual R=1: ~$508/mo, 0 windows, DD 17% | Different clock (H4 channel), **not** session ORB |
| C11 H1 mom R=2: negative edge / ~60% DD | Momentum continuum failed; ORB is **structure/session**, not mom |
| Survey Asia/PDHL/NR4 had 0 passes | London ORB is a distinct session-structure hypothesis |
| One trade/day potential + hard stop = range | DD-bounded by construction at fractional risk |

**Not revived:** SMA50 dual entry; C5 filters; hard R=2 on SMA50; ATR/R trails on C5; H4-BREAK-6 raw; H1 mom C11; C12 stack.

**Fallback if London ORB data path broken:** H1 z-score mean-reversion fade (|z|≥2 on 48-bar close vs SMA, fade toward mean, stop 1×ATR, R=1.5, same risk/kill, **no SMA50 regime**) — only if OR ranges cannot be formed. Prefer ORB if runnable.

## Direction / timeframe

- **Direction:** Exclusive dual — long **or** short by first confirmed OR break that UTC day; never both; max 1 position  
- **Timeframe:** UTC **M1** for OR formation, break confirmation, entry, and exit management  
- **Max positions:** 1  
- **No SMA50** in entry or regime filter

## Entry / exit / invalidation (locked a priori)

1. **London OR hour:** for each UTC calendar day, collect M1 bars with hour ∈ [07:00, 07:59] UTC. Require **≥ 45** M1 bars in that hour else skip day (thin-data guard).  
2. **OR_high** = max high; **OR_low** = min low; **OR_range** = OR_high − OR_low. Skip if OR_range ≤ 0.  
3. **ASSUMPTION — stop rule (ONE locked):** stop = **opposite side of the range always** (long stop = OR_low; short stop = OR_high). **Not** mid-of-range. Rationale: full-range stop maximizes stop distance → smaller lots → tighter DD bound by construction; mid would inflate size.  
4. **Break watch:** from first M1 at/after **08:00 UTC** through end of same UTC calendar day (23:59). First confirmed break wins; no second ORB that day.  
5. **Break confirmation:** M1 **close** beyond OR high (long) or OR low (short).  
6. **Entry:** first M1 **open** after the confirming close. Missing next bar → skip. Skip if entry would be through stop.  
7. **stop_dist** = |entry − opposite OR side|.  
8. **target_dist** = **1.5 × stop_dist** (R=1.5 hard TP).  
9. Same-minute double touch → **stop** (conservative).  
10. **Size:** `lots = round(equity × risk / stop_dist, 2)`, clamp [0.01, 50]; skip if &lt; 0.01 or stop_dist ≤ 0. Locked risk **0.75%**; also report **0.50%** and **1.0%**.  
11. **Daily kill:** if Prague-day **realized** exit PnL so far ≤ **−3%** of that Prague day’s start equity → no new entries until next Prague day.  
12. Ignore further breaks while in a position / after one ORB taken that UTC day.  
13. Open at end of sample → not marked on official closed path ($0 / excluded from n).

## Risk / costs (ONE model — stick to it)

- **ASSUMPTION account:** $100,000 2-step  
- **Cost model:** FTMO BTCUSD — **spread = 15** price units × lots at exit; **commission = 0**; **swap = 0** (same HF model as C7/C11).  
  - *Not* C4/C5’s 0.065%/side + swap. Intentional HF parity for session book.  
- Locked risk: **0.75%** equity per trade; also report **0.50%** and **1.0%**  
- Research worst-day bar: path day PnL / day-start ≥ **−5%**; max peak-to-trough realized DD ≤ **10%** on full path at chosen risk

## Periods

- Fit: 2024-01-01 → 2025-11-07  
- Holdout: 2025-11-08 → 2026-09-01  
- Extension: 2026-09-02 → data end  
- Prague day = Europe/Prague calendar day for daily kill / worst-day / DD path / leave-out months

## Gates (ACCEPT as fast vehicle only if ALL pass)

**A — edge/DD at locked 0.75%:**  
1. HO net after costs **&gt; 0**  
2. Ext net after costs **≥ 0**  
3. Leave-out two best HO **Prague** months → remaining HO **&gt; 0**  
4. Worst Prague day ≥ **−5%** of that day’s start equity; **0** days ≤ −5%  
5. Full-path max realized DD ≤ **10%**  
6. Fit net ≥ **−$10,000**

**B — ≤60d Challenge+Verification:**  
7. Sliding 60-calendar-day Prague windows: hit **≥1.10×** window-start **and** **≥1.155×** (Challenge+Verification combined, same convention as C7–C12), never **≤0.90×**, no Prague day ≤ **−5%** — **≥ 1** such window  
8. At locked risk, HO pace **≥ ~$7,500/mo** **OR** Gate 7  
9. Mean one-stop $ and worst historical day $ stay within **−$5,000** daily and path max DD within 10%

**ACCEPT** only if A+B all pass.  
**CONDITIONAL** if A passes and B fails (honest multi-month estimate — no fake ≤60d hope).  
Else **REJECT** with reason EDGE / DD / PACE.

## ASSUMPTIONS

1. **ASSUMPTION — Account:** $100k 2-step; Challenge +$10k; Verification +$5k; daily −5%; max −10%.  
2. **ASSUMPTION — Data:** Merged Dukascopy M1 bid (main through 2026-09-01 + dukas-ext through ~2026-10-07); no invented prices.  
3. **ASSUMPTION — Costs:** spread=15 model (not C4/C5 %).  
4. **ASSUMPTION — 60d window:** both stages inside same 60 calendar days vs window-start (1.10 then 1.155).  
5. **ASSUMPTION — Stop:** opposite OR side always (not mid).  
6. **ASSUMPTION — R=1.5** a priori on ORB stop distance.  
7. **ASSUMPTION — OR hour:** 07:00–08:00 UTC; ≥45 M1 bars required.  
8. Research only — **not deployable live** from this folder.

## Live

Do not touch live VM, MetaAPI, C4, drip, FREEZE_NEW_BUYS, or arm anything.

## If REJECT / CONDITIONAL

State binding constraint (EDGE / DD / PACE). Honest call on whether ≤60d BTC-only still looks open or still blocked after C13.
