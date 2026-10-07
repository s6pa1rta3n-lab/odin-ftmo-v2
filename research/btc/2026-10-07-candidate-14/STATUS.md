# BTC FTMO research baseline (2026-10-07)

**Status: C14 REJECT** — H1 z-score MR fade exclusive dual R=1.5 @0.75% (chassis=h1-zscore-mr). HO $-5,922 (~$-607/mo); fit $-46,728; leave-out $-10,467; ext $-4,365; max DD 60.3%; 60d windows 1/950. Binding: EDGE/DD: HO edge, extension, leave-out, −5% day, max DD 60.3%, fit, stop/worst-day/DD dollars. ≤60d BTC-only still **blocked** at FTMO 5%/10% after C14. C4 still armed/ops path. Do not deploy C5–C14.

## Candidate 14 (new measurement)
H1 z-score mean-reversion fade (|z|≥2 on SMA48/stdev48) exclusive dual + 1.0×H1 ATR stop + R=1.5 TP + 0.75% risk + −3% Prague kill. Cost: spread=15 (C7/C11/C13 parity). No SMA50 regime filter.

| Cfg | HO $/mo | Fit | Leave-out | Ext | Worst day | Max DD | ≤60d | Legal |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0.50% | $-503 | $-36,299 | $-8,825 | $-3,133 | -4.37% | 47.2% | 0/950 | NO |
| 0.75% | $-607 | $-46,728 | $-10,467 | $-4,365 | -6.53% | 60.3% | 1/950 | NO |
| 1.00% | $-748 | $-58,216 | $-11,841 | $-4,470 | -8.72% | 72.9% | 47/950 | NO |

**REJECT** as ≤60d vehicle. Binding: EDGE/DD: HO edge, extension, leave-out, −5% day, max DD 60.3%, fit, stop/worst-day/DD dollars.

Research-next: H1 z-score mean-reversion chassis failed on edge at locked risk (complement to C11 mom also failed). Together with C5–C13, BTC-only Challenge+Verification in ≤60 days at FTMO 5%/10% DD remains **blocked** — robust edges too slow; H1 mom/MR and session/HF books lack edge or blow DD. Prefer C5/C10 multi-month robustness or diversify beyond BTC-only. Do not deploy C14.

## Prior
- C13 REJECT (London ORB; leave-out + DD 15%)
- C12 REJECT + structural (0/850; stack ≠ pace)
- C11 REJECT (H1 mom EDGE+DD)
- C10 CONDITIONAL (R-trail; PACE+DD)
- C9 CONDITIONAL; C8 REJECT; C7 REJECT; C6 REJECT
- C5 research ACCEPT @0.01; too slow
- C4 armed/ops path; fit fail

## Live
Live catalogue drip / C4 ops: do not touch from research. Nothing arms from this folder.
