## Candidate 15 — H4 Bollinger Squeeze Breakout Exclusive Dual (research)

**Decision: REJECT**

H4 Bollinger(20, 2σ) squeeze (bw ≤ P10 of prior 100 bandwidths) → band-break exclusive dual + 1.0×H4 ATR stop + R=2 TP + 0.75% equity risk + −3% Prague-day kill.
Cost model: FTMO spread=15 (HF parity with C7/C11/C13/C14). Not C4/C5 %. **No SMA50** regime filter.
Chassis measured: `h4-bb-squeeze`. Distinct from SMA50 / ORB / H1 mom / H1 MR / H4-BREAK-6.

### Headline
- HO net: $12,594.53 (~$1,291/mo)
- Fit / Leave-out / Ext: $522.55 / $3,005.28 / $-1,822.74
- Max DD: 7.41%
- Worst Prague day: -1.53%
- ≤60d clean windows @0.75%: **0/909**
- Binding: EDGE: extension, 0 ≤60d windows, pace $1,291/mo
- ≤60d BTC-only still **blocked** at FTMO 5%/10% after C15.

### Risk table
| Risk | HO $/mo | Fit | Leave-out | Ext | Worst day | Max DD | ≤60d | Legal |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0.50% | $845 | $418 | $2,029 | $-1,166 | -1.03% | 5.0% | 0/909 | YES |
| 0.75% | $1,291 | $523 | $3,005 | $-1,823 | -1.53% | 7.4% | 0/909 | YES |
| 1.00% | $1,736 | $465 | $3,835 | $-2,527 | -2.04% | 9.8% | 0/909 | YES |

### Research-next
DD-legal but pace too slow for ≤60d. Honest multi-month book only. ≤60d BTC-only still **blocked** after C15. Prefer C5/C10. Do not deploy C15.

### Live
Research only — C4 / drip / FREEZE / MetaAPI / live VM untouched.

Files under `research/btc/2026-10-07-candidate-15/`.
