## Candidate 13 — London Opening Range Breakout (ORB) Exclusive Dual (research)

**Decision: REJECT**

London ORB (07:00–08:00 UTC) exclusive dual + opposite-side stop (not mid) + R=1.5 TP + 0.75% equity risk + −3% Prague-day kill.
Cost model: FTMO spread=15 (HF parity with C7/C11). Not C4/C5 %. **No SMA50** in entry/regime.
Chassis measured: `london-orb`.

### Headline
- HO net: $4,295.48 (~$440/mo)
- Fit / Leave-out / Ext: $17,518.99 / $-9,105.58 / $5,019.64
- Max DD: 14.99%
- Worst Prague day: -1.61%
- ≤60d clean windows @0.75%: **15/951**
- Binding: EDGE/DD: leave-out, max DD 15.0%, stop/worst-day/DD dollars
- ≤60d BTC-only still **blocked** at FTMO 5%/10% after C13.

### Risk table
| Risk | HO $/mo | Fit | Leave-out | Ext | Worst day | Max DD | ≤60d | Legal |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 0.50% | $306 | $12,072 | $-5,675 | $3,189 | -1.08% | 10.2% | 0/951 | NO |
| 0.75% | $440 | $17,519 | $-9,106 | $5,020 | -1.61% | 15.0% | 15/951 | NO |
| 1.00% | $551 | $22,486 | $-12,899 | $7,002 | -2.13% | 19.7% | 45/951 | NO |

### Research-next
London ORB chassis failed Gate A (edge and/or DD) at locked risk. Together with C5–C12, BTC-only Challenge+Verification in ≤60 days at FTMO 5%/10% DD remains **blocked** — robust edges too slow; session/HF books lack edge or blow DD. Prefer C5/C10 multi-month robustness or diversify beyond BTC-only. Do not deploy C13.

### Live
Research only — C4 / drip / FREEZE / MetaAPI / live VM untouched.

Files under `research/btc/2026-10-07-candidate-13/`.
