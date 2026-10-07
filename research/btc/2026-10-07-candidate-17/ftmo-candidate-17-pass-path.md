# Candidate 17 — Pass Path Package (≤90 calendar days)

**Mandate:** Measured path to clear FTMO Challenge (~+$10k) then Verification (~+$5k) on a ~$100k 2-step account within **1–3 months (≤90 calendar days total)**, respecting 5% daily / 10% max DD. Live C4/drip/MetaAPI/VM: **DO NOT TOUCH**.

**ASSUMPTIONS (labeled):**
| Item | Value |
|---|---|
| Account | $100,000 2-step |
| Challenge / Verification | +10% / +5% (continuous proxy BOTH=1.155 of window-start) |
| Pace bar | ≤90 calendar days both stages sequential |
| Daily / Max DD | 5% / 10% |
| Prague kill | −3% day-start realized → no new entries |
| Cost (dual / C15 / C) | FTMO spread=15 × lots; commission 0; swap 0 (unified) |

## Workstreams (locked a priori)

### A — Dual-book BTC (C5 + C15)
- C5: SMA50 exclusive dual R=1 + slope E + ATR P75 skip (logic from `run_candidate_5.py`)
- C15: H4 BB squeeze breakout R=2 (logic from `run_candidate_15.py`)
- Max 1 position **per book**; both may be open
- Risk splits: **0.40%+0.40%** primary; also 0.50%+0.50% and 0.35%+0.35%
- Shared Prague −3% kill on combined realized PnL; shared max DD gate 10%

### B — C15 alone ≤90d windows
- Risk 0.75% and 1.00%; scanner WINDOW_DAYS=90 (not only 60)
- Ext reported separately; Ext failure → CONDITIONAL at best

### C — H4-BREAK-6 hard-DD revival
- Rebuild from `/workspace/btc-strategy` H4-BREAK-6 artifacts
- Wrap: hard ATR stop, R=1 and R=1.5 TP, ≤0.75% risk, Prague −3% kill, max 1 pos
- Long-only break of prior 6 H4 highs (original signal); no channel exit — hard TP instead
- If rebuild insufficient → document and skip

## Success labels
- **ACCEPT path:** ≥1 legal ≤90d both-stage pass on HO or full-after-fit; HO>0; Ext≥0 (or N/A); leave-out OK; max DD≤10%; worst day ≥−5%; Fit ≥−$10k
- **CONDITIONAL path:** legal DD + HO pace that hits +$15k in ≤90d on ≥10% of HO windows even if Ext weak — label Ext failure, do not deploy until Ext fixed
- **Closest / residual:** if all fail, quantify $/mo gap and minimum second-instrument $ contribution

## Out of scope
No live deploy. No MetaAPI/VM/C4/drip changes. No fake trades.
