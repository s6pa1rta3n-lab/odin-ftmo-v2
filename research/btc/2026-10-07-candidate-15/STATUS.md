# BTC FTMO research baseline (2026-10-07)

**Status: C15 REJECT** — H4 BB squeeze breakout exclusive dual R=2 @0.75% (chassis=h4-bb-squeeze). HO $12,595 (~$1,291/mo); fit $523; leave-out $3,005; ext $-1,823; max DD 7.4%; 60d windows 0/909. Binding: EDGE: extension, 0 ≤60d windows, pace $1,291/mo. ≤60d BTC-only still **blocked** at FTMO 5%/10% after C15. C4 still armed/ops path. Do not deploy C5–C15.

## Candidate 15 (new measurement)
H4 Bollinger(20,2σ) squeeze (bw ≤ P10 of prior 100) → band-break exclusive dual + 1.0×H4 ATR stop + R=2 TP + 0.75% risk + −3% Prague kill. Cost: spread=15 (C7/C13/C14 parity). No SMA50 regime filter.

| Cfg | HO $/mo | Fit | Leave-out | Ext | Worst day | Max DD | ≤60d | Legal |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0.50% | $845 | $418 | $2,029 | $-1,166 | -1.03% | 5.0% | 0/909 | YES |
| 0.75% | $1,291 | $523 | $3,005 | $-1,823 | -1.53% | 7.4% | 0/909 | YES |
| 1.00% | $1,736 | $465 | $3,835 | $-2,527 | -2.04% | 9.8% | 0/909 | YES |

**REJECT** as ≤60d vehicle. Binding: EDGE: extension, 0 ≤60d windows, pace $1,291/mo.

Research-next: DD-legal but pace too slow for ≤60d. Honest multi-month book only. ≤60d BTC-only still **blocked** after C15. Prefer C5/C10. Do not deploy C15.

## Prior
- C14 REJECT (H1 z-score MR; EDGE/DD)
- C13 REJECT (London ORB; leave-out + DD 15%)
- C12 REJECT + structural (0/850; stack ≠ pace)
- C11 REJECT (H1 mom EDGE+DD)
- C10 CONDITIONAL (R-trail; PACE+DD)
- C9 CONDITIONAL; C8 REJECT; C7 REJECT; C6 REJECT
- C5 research ACCEPT @0.01; too slow
- C4 armed/ops path; fit fail

## Live
Live catalogue drip / C4 ops: do not touch from research. Nothing arms from this folder.
