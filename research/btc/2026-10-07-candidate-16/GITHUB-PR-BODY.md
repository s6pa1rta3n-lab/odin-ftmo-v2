## Candidate 16 — H1 NR7 Breakout Exclusive Dual (research)

**Decision: REJECT**

H1 NR7 (narrowest of last 7 H1 ranges) → pending breakout exclusive dual (expire after 6 bars) + structural NR7 stop + R=1.5 TP + 0.75% equity risk + −3% Prague-day kill.
Cost model: FTMO spread=15 (HF parity with C7/C11/C13/C14/C15). Not C4/C5 %. **No SMA50** regime filter.
Chassis measured: `h1-nr7-breakout`. Distinct from SMA50 / ORB / H1 mom / H1 MR / H4-BREAK-6 / H4 BB squeeze.

### Headline
- HO net: $-30,726.64 (~$-3,149/mo)
- Fit / Leave-out / Ext: $-29,664.67 / $-34,248.80 / $-3,060.92
- Max DD: 63.87%
- Worst Prague day: -5.23%
- ≤60d clean windows @0.75%: **50/951**
- Binding: EDGE/DD: HO edge, extension, leave-out, −5% day, max DD 63.9%, fit, stop/worst-day/DD dollars
- Pace vs C15: C16 $-3,149/mo vs C15 ~$1,291/mo
- ≤60d BTC-only still **blocked** at FTMO 5%/10% after C16.

### Risk table
| Risk | HO $/mo | Fit | Leave-out | Ext | Worst day | Max DD | ≤60d | Legal |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0.50% | $-2,575 | $-20,115 | $-27,934 | $-2,851 | -3.49% | 48.5% | 0/951 | NO |
| 0.75% | $-3,149 | $-29,665 | $-34,249 | $-3,061 | -5.23% | 63.9% | 50/951 | NO |
| 1.00% | $-3,439 | $-39,152 | $-37,450 | $-2,804 | -6.98% | 75.9% | 93/951 | NO |

### Research-next
H1 NR7 breakout chassis failed on edge at locked risk. C16 HO pace $-3,149/mo vs C15 ~$1,291/mo (-2.44×). Together with C5–C15, BTC-only Challenge+Verification in ≤60 days at FTMO 5%/10% DD remains **blocked** — robust edges too slow; HF books lack edge or blow DD. Prefer C5/C10 multi-month robustness or diversify beyond BTC-only. Do not deploy C16.

### Live
Research only — C4 / drip / FREEZE / MetaAPI / live VM untouched.

Files under `research/btc/2026-10-07-candidate-16/`.
