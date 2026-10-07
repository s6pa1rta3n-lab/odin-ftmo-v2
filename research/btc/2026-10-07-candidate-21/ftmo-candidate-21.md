# FTMO Candidate 21 — Soft DD governor on BTC H4-BREAK-6 channel

Research-only. Locked a-priori soft governor — **not** a post-hoc grid.
Live C4 / drip / FREEZE / MetaAPI untouched. Do not package Gold. No deploy.

## Thesis (locked)

C20 sticky governor made BTC H4-BREAK-6 channel DD-legal and kept ≤90d windows, but **HO=$0 / Ext=$0** (sticky block after Fit; Fit-era windows only). Soft governor: **never fully block**; only **cut risk** so HO/Ext can still trade while capping max DD ≤10%.

## Soft governor (locked — do not retune after results)

1. Peak **closed** equity high-water mark; `dd = 1 - equity/peak`.
2. If `dd < 0.05`: risk = **full**.
3. If `0.05 ≤ dd < 0.08`: risk = **mid** for new entries.
4. If `dd ≥ 0.08`: risk = **floor** for new entries — **still allow entries** (no flat ban, no sticky wait).
5. Prague −3% day kill unchanged (day kill may block entries for that Prague day only).
6. Open trades: do not force-close on governor; only size new entries.

## Books

### 21A — BTC H4-BREAK-6 channel-exit @ soft gov (primary)

- Same exclusive dual / channel exit as C20B: 4h close > prior 6-bar high; long only; stop 1.5×ATR14; exit on 4h close < prior 3-bar low or stop; spread **15**.
- Full **1.00%** / mid **0.50%** / floor **0.25%**.
- Also report ungoverened C20B baseline for delta.

### 21B — XAG Donchian C19B/20A soft-gov mirror

- Same signal as C19B/20A: daily 20d dual; stop 2×ATR; TP 1R; TIME day-10.
- Full **2.50%** / mid **1.25%** / floor **0.75%** at same dd thresholds.
- Costs ASSUMPTIONS (C19B parity): contract **5000**, spread **0.025**, commission **$3/lot**.

## Periods

| Slice | Range |
|---|---|
| Fit | 2024-01-01 → 2025-11-07 |
| HO | 2025-11-08 → 2026-09-01 |
| Ext | 2026-09-02 → data end (XAG: N/A if feed ends; BTC: dukas-ext if present) |

## Gates

- **ACCEPT**: max DD ≤10%, worst Prague day > −5% (0 days ≤−5%), **HO>0**, leave-out remaining HO>0, Ext≥0 (or Ext N/A), AND ≥1 ≤90d both-stages window with **at least one window starting in HO (2025-11-08+) or Ext**.
- **CONDITIONAL thin**: legal DD + windows but all Fit-era only, or leave-out/Ext weak — **not ACCEPT**.
- **REJECT**: DD still illegal, or HO≤0 with no deployable path, or 0 windows.
