## Candidate 38 — USA30 Wilder Parabolic SAR (entry30 / BTC-SAR port)

Research only. Broad Odin mandate. Fresh index SAR lane (C27 XAG SAR REJECT; Explorer BTC SAR FAIL). **No deploy.** Live C4 untouched.

**Primary verdict: `REJECT`** via 38B+soft

| Book | Risk/gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Explorer out | Leave-out | Legal | Decision |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 38A@2.50% | 2.50% OFF | -1,618 | 20.7% | 0/884 (0) | 0/872 (0) | 0 | -22,269 | NO | REJECT |
| 38B+soft | SOFT | -557 | 11.4% | 0/884 (0) | 0/872 (0) | 0 | -7,322 | NO | REJECT |
| sens@2.60% | 2.60% sens | -1,679 | 21.4% | 0/884 (0) | 0/872 (0) | 0 | -23,096 | NO | REJECT |

### Lead
**NO — USA30 Wilder SAR does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

### Mechanics
- Mirror of Gold entry30 / Explorer BTC-SAR: AF 0.02/0.02/0.20; reverse-only; both sides
- Stop distance = abs(fill − new SAR); no ATR / TP / TIME
- 38A risk locked **2.50%** (index lane C22/C32; not BTC 0.50%, not Gold 2.60% retune)
- 38B soft gov 2.50→1.25→0.75 + Prague day kill −3% (a-priori)
- 2.60% sensitivity readout only — not verdict
- USA30 costs ASSUMPTION (C22): contractSize=1, commission=0, spread=2.5 pts, USD
- Floating Prague day mark for legal/Explorer (BTC SAR construction)
- ACCEPT gates = C22–C26 (HO ≤90d is gate; Explorer outside is cross-check)

### Paths
- Spec: `research/btc/2026-10-07-candidate-38/ftmo-candidate-38.md`
- Runner: `research/btc/2026-10-07-candidate-38/run_candidate_38.py`
- Results: `research/btc/2026-10-07-candidate-38/candidate-38-results.md`

Nothing live. Do not arm without Odin yes.
