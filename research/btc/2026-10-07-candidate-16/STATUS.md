# BTC FTMO research baseline (2026-10-07)

**Status: C16 REJECT** — H1 NR7 breakout exclusive dual R=1.5 @0.75% (chassis=h1-nr7-breakout). HO $-30,727 (~$-3,149/mo); fit $-29,665; leave-out $-34,249; ext $-3,061; max DD 63.9%; 60d windows 50/951. Binding: EDGE/DD: HO edge, extension, leave-out, −5% day, max DD 63.9%, fit, stop/worst-day/DD dollars. ≤60d BTC-only still **blocked** at FTMO 5%/10% after C16. Pace vs C15: C16 $-3,149/mo vs C15 ~$1,291/mo. C4 still armed/ops path. Do not deploy C5–C16.

## Candidate 16 (new measurement)
H1 NR7 (narrowest of last 7 H1 ranges) → pending breakout exclusive dual (expire 6 bars) + structural NR7 stop + R=1.5 TP + 0.75% risk + −3% Prague kill. Cost: spread=15 (C7/C13/C15 parity). No SMA50 regime filter.

| Cfg | HO $/mo | Fit | Leave-out | Ext | Worst day | Max DD | ≤60d | Legal |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0.50% | $-2,575 | $-20,115 | $-27,934 | $-2,851 | -3.49% | 48.5% | 0/951 | NO |
| 0.75% | $-3,149 | $-29,665 | $-34,249 | $-3,061 | -5.23% | 63.9% | 50/951 | NO |
| 1.00% | $-3,439 | $-39,152 | $-37,450 | $-2,804 | -6.98% | 75.9% | 93/951 | NO |

**REJECT** as ≤60d vehicle. Binding: EDGE/DD: HO edge, extension, leave-out, −5% day, max DD 63.9%, fit, stop/worst-day/DD dollars.

Research-next: H1 NR7 breakout chassis failed on edge at locked risk. C16 HO pace $-3,149/mo vs C15 ~$1,291/mo (-2.44×). Together with C5–C15, BTC-only Challenge+Verification in ≤60 days at FTMO 5%/10% DD remains **blocked** — robust edges too slow; HF books lack edge or blow DD. Prefer C5/C10 multi-month robustness or diversify beyond BTC-only. Do not deploy C16.

## Prior
- C15 REJECT near-miss (H4 BB squeeze; HO ~$1.3k/mo; Ext fail; 0/909)
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
