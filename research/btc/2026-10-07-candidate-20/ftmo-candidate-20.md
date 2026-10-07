# FTMO Candidate 20 — Drawdown governor on window-capable books

Research-only. Locked a-priori governor — **not** a post-hoc grid.
Live C4 / drip / FREEZE / MetaAPI untouched. Do not package Gold. No deploy.

## Thesis (locked)

Keep the **signal** from a window-capable illegal-DD book; wrap **sizing** with a hard peak-to-trough equity governor so full-sample max DD ≤10% while preserving as many ≤90d Challenge+Verification windows as possible.

## Governor (locked — do not retune after results)

1. Track peak **closed** equity (high-water mark).
2. `dd = 1 - equity/peak`.
3. If `dd < 0.05`: full risk for **new entries only**.
4. If `0.05 ≤ dd < 0.08`: cut risk for new entries only (open trades unchanged).
5. If `dd ≥ 0.08`: **no new entries** until `dd < 0.05` again (do not flatten early).
6. Prague −3% day kill still applies (no new entries rest of Prague day if realized day PnL ≤ −3% of day-start).

## Books

### 20A — XAG 20d Donchian dual @2.50% TP1R ± governor

- Same signal as C19B: daily UTC from M1; 20-day channel (prior bars); both sides; next open; stop 2×ATR; target 1R; TIME day-10.
- Full risk **2.50%**; cut risk **1.00%**; block at **8%** DD until recovered under **5%**.
- Costs ASSUMPTIONS (parity with C19B): contract_size **5000**, spread **0.025**, commission **$3/lot**.

### 20B — BTC H4-BREAK-6 channel-exit @1.00% ± governor (window-capable prior runner)

- Original locked rule: 4h close > prior 6-bar high; long only; stop 1.5×ATR14 (simple); exit on 4h close < prior 3-bar low (channel) or stop; spread 15.
- Full **1.00%**; cut **0.40%** (same 40% ratio as XAG 2.50→1.00); block at 8%.

### 20C — BTC H4-BREAK-6 C17 R=1.5 harden @0.75% ± governor (C17 workstream C mirror)

- C17 signal: same 6-bar break / 1.5 ATR stop, but **R=1.5 target** exit (no channel); as in `run_candidate_17.py`.
- Full **0.75%**; cut **0.30%**; block at 8%.

## Periods

| Slice | Range |
|---|---|
| Fit | 2024-01-01 → 2025-11-07 |
| HO | 2025-11-08 → 2026-09-01 |
| Ext | 2026-09-02 → data end (XAG: N/A if feed ends; BTC: dukas-ext if present) |

## Gates

- **ACCEPT**: max DD ≤10%, worst Prague day > −5% (0 days ≤−5%), HO>0, leave-out remaining HO>0 (or document fail), AND ≥1 ≤90d Challenge+Ver window (continuous or sequential).
- **CONDITIONAL**: legal DD + ≥1 ≤90d window but leave-out/Ext weak.
- **REJECT**: governor kills all windows or DD still illegal.
