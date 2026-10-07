# FTMO BTC — Candidate 8 Spec

**Name:** Filtered SMA50 Dual R=2 (catalogue stop) — “Let winners run past R=1”  
**Status:** Research measurement only — live engines / C4 / drip / FREEZE / MetaAPI untouched  
**Prepared:** 2026-10-07 (America/New_York)

**Scoreboard so far:**  
- C1 SMA dual R=3 (stop=2×412.91) → **REJECT** leave-out (concentration)  
- C4 SMA50 exclusive dual R=1 → CONDITIONAL (fit fail); still armed ops  
- C5 SMA50 + slope E + ATR&lt;P75 R=1 → research **ACCEPT** @ 0.01; too slow (~$480/mo)  
- C6 C5 fast-scale → **REJECT** (≤60d needs illegal size)  
- C7 H4 dual R=1 → **REJECT** (~$508/mo; 0/896 60d windows; DD 17%)

**C7 insight driving C8:** more trades + hard R=1 still ~$0.5k/mo — winners capped. Raise expected $/month via **higher R**, not more size on R=1.

---

## One-line thesis (a priori)

Keep C5’s SMA50 exclusive dual + slope + elevated-vol skip, keep catalogue **stop = 412.91**, but set **target = 2 × 412.91 (R=2)** so winners pay more than one stop. Size at fractional equity risk (primary **1.0%**/trade) and ask whether Challenge +10% then Verification +5% occurs in **≤60 calendar days** without −5% Prague day or −10% equity trough.

**vs C1 (documented difference):**  
| | C1 | C8 |
|---|---|---|
| Stop | 825.82 (2× catalogue) | **412.91** (1× catalogue) |
| Target / R | 2477.46 / R=3 vs that stop | **825.82 / R=2** vs catalogue stop |
| Filters | none | **C5 slope E + ATR &lt; P75(100d)** |
| Leave-out | failed historically | re-measured under filters |

## Direction / timeframe

- Exclusive dual (long **or** short by prior close vs SMA50; never both)  
- Daily regime; entry next **00:00 UTC** M1 open; max **1** position  
- Same C5 filters (locked a priori; not re-tuned)

## Entry / exit / invalidation

- Regime + Filter E (slope lookback 10) + Filter V75 (ATR &lt; P75 of prior 100d) — identical to C5  
- **stop_dist** = `412.91`  
- **target_dist** = `825.82` (R=2) — **PRIMARY**  
- Same-minute double touch → **stop**  
- Open at end of slice → $0  
- **Diagnostic (not a new candidate):** same rules with **target = 1238.73 (R=3)**

## Risk / costs (ASSUME $100k)

| Item | Value |
|---|---|
| Account | **$100,000** 2-step (ASSUMPTION) |
| Challenge / Verification | +10% / +5% sequential equity targets |
| Pace bar | **≤60 calendar days** for **both** steps |
| Daily / Max DD | **5% / 10%** of initial (Prague day / peak-trough equity) |
| Risk per trade (primary) | **1.0%** equity / stop_dist → lots = round(equity×0.01/412.91, 2), min 0.01 |
| Daily kill | **−3%** realized Prague-day P&amp;L → no new entries that day (buffer under 5%) |
| Cost model (ONE, stick) | **Same as C4/C5:** commission **0.065%**/side on notional×lots; swap est. **\|−30%\|/360** per UTC midnight held |

Catalogue **0.01** dollars also reported for Gate-A-style comparison to C5.

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

## Why this (not fishing)

| Prior fact | Implication |
|---|---|
| C5 ACCEPT but ~$480/mo @ 0.01 | Edge exists; R=1 caps dollar pace |
| C6 REJECT | Scaling R=1 hits DD wall before ≤60d |
| C7 REJECT | Higher frequency + R=1 still ~$0.5k/mo |
| C1 R=3 REJECT leave-out | Unfiltered large-stop R=3 concentrated; try **filtered** + **smaller stop** + **R=2** |

**Not chosen:** raw H4-BREAK-6 revival; dual scale-out (thesis C) deferred unless R=2 fails cleanly; unfiltered R=3 (already rejected as C1).

## Slices

| Slice | UTC entry midnights |
|---|---|
| Fit | 2024-01-01 → 2025-11-07 |
| Holdout | 2025-11-08 → 2026-09-01 |
| Extension | 2026-09-02 → last available |

Results: `/workspace/btc-strategies/candidate-8-results.md`  
Runner: `/workspace/btc-strategies/run_candidate_8.py`
