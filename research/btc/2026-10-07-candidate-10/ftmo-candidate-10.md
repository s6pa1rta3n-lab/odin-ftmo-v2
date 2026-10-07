# FTMO BTC — Candidate 10 Spec

**Name:** C5 Entry + R-Multiple Trail Runner (1.0×R behind extreme)  
**Status:** Research measurement only — live engines / C4 / drip / FREEZE / MetaAPI untouched  
**Prepared:** 2026-10-07 (America/New_York)

**Scoreboard so far:**  
- C1 SMA dual R=3 → **REJECT** (leave-out)  
- C4 SMA50 exclusive dual R=1 → CONDITIONAL (fit fail); still armed ops  
- C5 SMA50 + slope E + ATR&lt;P75 R=1 → research **ACCEPT** @ 0.01; too slow (~$480/mo)  
- C6 C5 fast-scale → **REJECT** (≤60d needs illegal size)  
- C7 H4 dual R=1 → **REJECT** (~$508/mo; 0/896 windows; DD 17%)  
- C8 Filtered SMA50 dual hard R=2 (diag R=3) → **REJECT** (edge: HO −$6.8k; WR collapses)  
- C9 C5 entry + BE@+1R + ATR(14)×1 trail → **CONDITIONAL** (DD wall; ATR≫stop → trail never left BE; winners = +5R emergency only)

**Explicit: do NOT re-run SMA50 dual at hard R=2/R=3.** C10 tests whether an **R-multiple trail** (not ATR) lets the runner engage usefully.

---

## One-line thesis (a priori)

Keep **C5 entry filter** (SMA50 exclusive dual + slope E + ATR&lt;P75), keep catalogue **initial stop = 412.91**, replace hard R=1/R=2 TP with a **single-position R-multiple trail runner**: once price reaches **+1R**, move SL to **breakeven**, then trail by **1.0×R (412.91)** behind the favorable extreme since entry (long: HH−412.91; short: LL+412.91; never widen); optional emergency hard TP only at **+5R** as catastrophe cap. Ask whether this unlocks Challenge +10% then Verification +5% in **≤60 calendar days** at DD-legal size.

## Locked exit structure (chosen before measuring)

**Primary (single position):**

1. **Initial SL** = entry ± `412.91` (long below / short above).  
2. **No hard far TP** at R=2/R=3.  
3. **Activation:** first time favorable M1 extreme reaches **+1R** (`412.91` from entry) → set SL to **entry (breakeven)**.  
4. **Trail (R-multiple, NOT ATR):** after activation, on each subsequent M1 bar:  
   - long: `candidate_sl = highest_high_since_entry − 412.91`  
   - short: `candidate_sl = lowest_low_since_entry + 412.91`  
   - ratchet only in favorable direction (never widen).  
5. **Emergency cap:** hard TP at **+5R** (`2064.55`) — catastrophe only; not the thesis payoff.  
6. Same-minute SL + emergency-TP → **stop** (conservative, same as C4/C5).  
7. Open at end of slice → $0.  
8. Max **1** position; entry next **00:00 UTC** M1 open when flat.

**Why not ATR:** C9 showed BTC daily ATR(14) ≫ 412.91, so ATR×1 trail never ratcheted above BE. Fixed 1.0×R trail is the locked alternative so the trail can leave BE once extreme exceeds +1R.

**Filters (PRIMARY):** C5 slope E + V75 on.  
**Diagnostic (not a second candidate):** same R-trail exit **without** C5 filters (plain C4 entry).

## Direction / timeframe

- Exclusive dual (long **or** short by prior close vs SMA50; never both)  
- Daily regime; entry next **00:00 UTC** M1 open; max **1** position  
- C5 filters locked a priori (not re-tuned)

## Risk / costs (ASSUME $100k)

| Item | Value |
|---|---|
| Account | **$100,000** 2-step (ASSUMPTION) |
| Challenge / Verification | +10% / +5% sequential equity targets |
| Pace bar | **≤60 calendar days** for **both** steps |
| Daily / Max DD | **5% / 10%** of initial (Prague day / peak-trough equity) |
| Risk per trade (Gate B primary) | **1.0%** equity / initial stop_dist → lots = round(0.01 × equity×0.01/412.91, 2), min 0.01 |
| Also report | **0.5%** equity path + catalogue **0.01** |
| Daily kill | **−3%** realized Prague-day P&amp;L → no new entries that day |
| Cost model (ONE, stick) | **Same as C4/C5:** commission **0.065%**/side on notional×lots; swap est. **\|−30%\|/360** per UTC midnight held |

## Gates

### Gate A — robustness (catalogue 0.01 full-cost path)

1. Holdout net &gt; 0 and &gt; buy-only −$8,258.20  
2. Extension net ≥ 0  
3. Leave-out two best HO months → remaining &gt; 0  
4. Worst ET day raw ≥ −$2,000 on HO &amp; ext (0.01)  
5. Fit net ≥ −$5,000  
6. HO months ≥50% green  

### Gate B — ≤60-day fast vehicle (1.0% risk equity path)

7. ≥1 clean rolling ≤60d window: hit 1.10 then 1.155 of window-start equity, floor &gt; 0.90, no Prague day ≤ −5%  
8. HO pace ≥ ~$7.5k/mo **OR** Gate 7  
9. Mean planned stop $ ≤ $5k; worst Prague day $ ≥ −$5k; max realized DD ≤ 10%  

**ACCEPT** only if Gate A **and** Gate B pass.  
**CONDITIONAL** if A passes and B fails (robust but not fast).  
**REJECT** otherwise.

If still DD-bound at sizes that pass windows → say so.  
If R-trail still never engages usefully → recommend **different entry chassis as C11** (do not keep milking SMA50 dual exits).

## Why this (not fishing)

| Prior fact | Implication |
|---|---|
| C5 ACCEPT but ~$480/mo @ 0.01 | Edge exists at R=1; pace too slow |
| C6 REJECT | Scaling R=1 hits DD wall before ≤60d |
| C8 REJECT | Hard R=2/R=3 destroys WR/EV — do not repeat |
| C9 CONDITIONAL | ATR trail never left BE; DD-illegal at size that hits ≤60d |
| Need trail that can leave BE | Fixed 1.0×R behind extreme engages once extreme &gt; +1R |

**Not chosen:** hard R=2/R=3 (C8); ATR trail (C9); scale-out halves (heavier; deferred).

## ASSUMPTIONS

1. **ASSUMPTION — Data:** Merged Dukascopy M1 bid; no invented prices.  
2. **ASSUMPTION — Regime lag:** Prior close vs SMA50; filters use prior-day info only.  
3. **ASSUMPTION — Trail = 1.0×R** locked a priori (not fit-optimized).  
4. **ASSUMPTION — BE at exactly +1R** (not +small).  
5. **ASSUMPTION — Emergency +5R** catastrophe cap only.  
6. **ASSUMPTION — Single position** (no scale-out).  
7. **ASSUMPTION — Live untouched.**

## Slices

| Slice | UTC entry midnights |
|---|---|
| Fit | 2024-01-01 → 2025-11-07 |
| Holdout | 2025-11-08 → 2026-09-01 |
| Extension | 2026-09-02 → last available |

Results: `/workspace/btc-strategies/candidate-10-results.md`  
Runner: `/workspace/btc-strategies/run_candidate_10.py`
