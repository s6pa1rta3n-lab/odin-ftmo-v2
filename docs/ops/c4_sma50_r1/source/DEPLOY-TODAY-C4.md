# Deploy-today brief — Candidate 4 (CONDITIONAL)

**For:** Odin → Trading Ops / Strategy Implementer  
**When:** 2026-10-07 morning ET  
**BTC spot (Kraken):** ~83,612  
**Live catalogue drip:** DO NOT silently rewrite. Treat as separate book.

## Recommendation
Deploy **Candidate 4** as a **new stopped book** (shadow or second path). Research status is **CONDITIONAL** (fit gate failed). Odin is accepting known older-year bleed risk in exchange for a leave-out-surviving, FTMO-sized ruleset **today**.

## Exact rules to implement
1. Symbol: BTCUSD, volume **0.01** (or size so full stop ≈ **$400–$450**; document if scaled).
2. Regime: prior **UTC daily close** vs **SMA50** (no look-ahead).
   - close > SMA50 → **buy only** next session
   - close < SMA50 → **sell only**
   - equal → flat
3. Entry: **00:00 UTC** M1 open only; skip if that bar missing; **max 1** open position total; no new entry while in trade.
4. Stop = entry ± **412.91**; Target = entry ± **412.91** (R=1). Hard stop required (not TP-only).
5. Same-minute double touch → treat as stop.
6. FTMO risk: stop trading the CE(S)T day if closed+float ≤ **−2%** equity; do not open if within **3%** of 10% max-loss floor.
7. Do **not** pyramid. Do **not** use catalogue 30m drip logic.

## What this is not
- Not an edit of `btc_15m_buy.py` / `catalogue-btc-15m.service`.
- Not ACCEPT research — fit years ~**−$8.9k**; holdout ~**+$7.2k**, leave-out still green, extension green.

## Parallel risk ask (separate approval)
Freeze or hard-cap the live no-stop drip (32 opens, floor 90.5k) so inventory cannot grow into the challenge floor while C4 is tested. That is risk control, not the C4 alpha claim.

## Success / kill for first 10 trading days
- **Keep:** no day worse than −2% from this book; cumulative not worse than −3% from this book alone.
- **Kill:** any FTMO daily/max-loss near-miss attributable to this book, or 10 days with net < −2% on this book.
