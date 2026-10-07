# FTMO BTC — Candidate 12 Spec

**Name:** Multi-Position C5 Stack (N=3, 2% Aggregate Risk Cap)  
**Status:** Research measurement only — live engines untouched  
**Prepared:** 2026-10-07 (America/New_York)

**Scoreboard so far:**  
- C5 SMA50 E+V75 R=1 → research **ACCEPT** @0.01 (~$480/mo; too slow for ≤60d)  
- C6 C5 scale → **REJECT** (DD wall)  
- C7 H4 breakout R=1 → **REJECT**  
- C8 hard R=2 → **REJECT** (edge killed)  
- C9 ATR trail → **CONDITIONAL** (PACE+DD)  
- C10 R-trail → **CONDITIONAL** (0 windows @ legal)  
- C11 H1 mom R=2 → **REJECT** (negative edge)

---

## One-line thesis

Stack up to **3** concurrent tickets on the **known-positive C5 edge** (same signal/filters/R=1), same regime direction only, with **aggregate open stop-risk ≤ 2% equity**, aiming for Challenge+Verification in ≤60 days without blowing FTMO 5%/10% DD — last BTC-only chassis before structural-implausibility call.

## Direction / timeframe

- **Direction:** Exclusive dual by regime; stack **same side only** (never long+short)  
- **Timeframe:** Daily regime; entry at next **00:00 UTC** M1 open  
- **Max positions:** **N=3** locked a priori  

## Entry / exit / invalidation

- **Regime + filters:** identical to C5 (SMA50 prior close, slope E lookback 10, ATR < P75 of prior 100d)  
- **Entry:** 00:00 UTC M1 open when filters pass, `len(opens) < 3`, same side as opens (or flat), agg risk OK, Prague day not killed  
- **Per ticket:** stop_dist = target_dist = `412.91` (R=1 hard)  
- **Same-minute double touch → stop**  
- **Do NOT** hard R=2/3; **Do NOT** use C11 losers  

## Risk / costs

| Config | Per ticket | Max N | Agg open risk cap |
|---|---|---|---|
| **A** | flat **0.01** lots | 3 | ≤ **2.0%** equity |
| **B** | **0.5%** equity at entry | 3 | ≤ **2.0%** equity |
| **C** (diagnostic) | **0.5%** equity | **1** | ≤ 2.0% (scaled C5 single) |

- If new signal would breach agg cap → **skip**  
- Prague-day kill: no new entries if realized day PnL ≤ **−3%**  
- Optional flatten all if realized day PnL ≤ **−4%** (research: close remaining at next signal bar open)  
- Commission **0.065%**/side; swap est. **|−30%|/360** per UTC midnight held  
- Account ASSUMPTION: **$100,000** 2-step; daily 5% / max 10%  

## Gates

### Robustness (esp. A @ 0.01 stack)
Report fit / HO / leave-out / ext nets, worst day, months.

### ≤60d vehicle
For each config: count rolling 60d windows that hit **+10% then +15%** without **−5%** Prague day or **−10%** trough from window start equity.

**ACCEPT** if ≥1 clean window on a DD-legal config (max DD ≤10%, no −5% days).  
**CONDITIONAL** if windows only when DD illegal.  
**REJECT** if 0 windows on DD-legal configs.

**If REJECT with 0 windows at DD-legal configs:** declare BTC-only Challenge+Verification ≤60d at FTMO 5%/10% **structurally implausible** on C5–C12 + prior survey; recommend honest slower path (C5/C10 legal size or longer horizon) — not fake hope.

## ASSUMPTIONS

1. **ASSUMPTION — Data:** Merged Dukascopy M1 bid (same as C5).  
2. **ASSUMPTION — N=3, agg 2%:** locked a priori (not fit-tuned).  
3. **ASSUMPTION — Remaining stop $:** full STOP×(lots/0.01) while open (hard R=1).  
4. **ASSUMPTION — Same-direction only:** opposite regime while open → skip new.  
5. **ASSUMPTION — Flatten:** ≤−4% closes remaining at next candidate entry bar open.  
6. **ASSUMPTION — Live untouched.**

## Slices

| Slice | UTC entry midnights |
|---|---|
| Fit | 2024-01-01 → 2025-11-07 |
| Holdout | 2025-11-08 → 2026-09-01 |
| Extension | 2026-09-02 → last available |
| 60d path | Fit start → ext end continuum |

Results: `/workspace/btc-strategies/candidate-12-results.md`
