## Candidate 27 — XAGUSD Wilder Parabolic SAR (entry30 / BTC-SAR port)

Research only. Broad Odin mandate. Explorer near-miss lane. **No deploy.** Live C4 untouched.

**Primary verdict: `REJECT`** via 27A@2.50%

| Book | Risk/gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Explorer out | Leave-out | Legal | Decision |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 27A@2.50% | 2.50% OFF | 2,052 | 21.1% | 21/863 (0) | 25/863 (10) | 0 | 2,899 | NO | REJECT |
| 27B+soft | SOFT | 757 | 12.8% | 0/863 (0) | 25/863 (10) | 0 | 658 | NO | REJECT |
| sens@2.60% | 2.60% sens | 2,173 | 21.9% | 38/863 (0) | 25/863 (10) | 0 | 3,063 | NO | REJECT |

### Lead
**NO — XAG Wilder SAR does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

### Mechanics
- Mirror of Gold entry30 / Explorer BTC-SAR: AF 0.02/0.02/0.20; reverse-only; both sides
- Stop distance = abs(fill − new SAR); no ATR / TP / TIME
- 27A risk locked **2.50%** (XAG lane; not BTC 0.50%, not Gold 2.60% retune)
- 27B soft gov 2.50→1.25→0.75 + Prague day kill −3% (a-priori)
- 2.60% sensitivity readout only — not verdict
- XAG costs ASSUMPTION (C19/C24): contract 5000, spread 0.025, commission $3/lot
- Floating Prague day mark for legal/Explorer (BTC SAR construction)
- ACCEPT gates = C22–C26 (HO ≤90d is gate; Explorer outside is cross-check)

### Paths
- Spec: `research/btc/2026-10-07-candidate-27/ftmo-candidate-27.md`
- Runner: `research/btc/2026-10-07-candidate-27/run_candidate_27.py`
- Results: `research/btc/2026-10-07-candidate-27/candidate-27-results.md`

Nothing live. Do not arm without Odin yes.
