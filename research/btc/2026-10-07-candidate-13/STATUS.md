# BTC FTMO research baseline (2026-10-07)

**Status: C13 REJECT** — London ORB exclusive dual R=1.5 @0.75% (chassis=london-orb). HO $4,295 (~$440/mo); fit $17,519; leave-out $-9,106; ext $5,020; max DD 15.0%; 60d windows 15/951. Binding: EDGE/DD: leave-out, max DD 15.0%, stop/worst-day/DD dollars. ≤60d BTC-only still **blocked** at FTMO 5%/10% after C13. C4 still armed/ops path. Do not deploy C5–C13.

## Candidate 13 (new measurement)
London ORB (07:00–08:00 UTC) exclusive dual + opposite-side stop + R=1.5 + 0.75% risk + −3% Prague kill. Cost: spread=15 (C7/C11 parity). No SMA50.

| Cfg | HO $/mo | Fit | Leave-out | Ext | Worst day | Max DD | ≤60d | Legal |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0.50% | $306 | $12,072 | $-5,675 | $3,189 | -1.08% | 10.2% | 0/951 | NO |
| 0.75% | $440 | $17,519 | $-9,106 | $5,020 | -1.61% | 15.0% | 15/951 | NO |
| 1.00% | $551 | $22,486 | $-12,899 | $7,002 | -2.13% | 19.7% | 45/951 | NO |

**REJECT** as ≤60d vehicle. Binding: EDGE/DD: leave-out, max DD 15.0%, stop/worst-day/DD dollars.

Research-next: London ORB chassis failed Gate A (edge and/or DD) at locked risk. Together with C5–C12, BTC-only Challenge+Verification in ≤60 days at FTMO 5%/10% DD remains **blocked** — robust edges too slow; session/HF books lack edge or blow DD. Prefer C5/C10 multi-month robustness or diversify beyond BTC-only. Do not deploy C13.

## Prior
- C12 REJECT + structural (0/850; stack ≠ pace)
- C11 REJECT (H1 mom EDGE+DD)
- C10 CONDITIONAL (R-trail; PACE+DD)
- C9 CONDITIONAL; C8 REJECT; C7 REJECT; C6 REJECT
- C5 research ACCEPT @0.01; too slow
- C4 armed/ops path; fit fail

## Live
Live catalogue drip / C4 ops: do not touch from research. Nothing arms from this folder.
