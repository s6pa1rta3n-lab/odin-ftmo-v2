## Candidate 26 — GER40 three-close momentum (Gold entry5 port)

Research only. Broad Odin mandate. Explorer near-miss lane. **No deploy.** Live C4 untouched.

**Primary verdict: `REJECT`** via 26B+soft

| Book | Risk/gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Explorer out | Leave-out | Legal | Decision |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 26A@2.50% | 2.50% OFF | -603 | 13.0% | 0/858 (0) | 0/864 (0) | 0 | -19,002 | NO | REJECT |
| 26B+soft | SOFT | -261 | 10.4% | 0/858 (0) | 0/864 (0) | 0 | -6,354 | NO | REJECT |
| sens@2.60% | 2.60% sens | -633 | 13.6% | 0/858 (0) | 0/864 (0) | 0 | -19,831 | NO | REJECT |

### Lead
**NO — GER40 three-close does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

### Mechanics
- Mirror of Gold entry5: three strict consecutive daily closes → next open; SL 2×ATR14; TP 2R; day-5 TIME
- 26A risk locked **2.50%**; 26B soft gov 2.50→1.25→0.75 + Prague day kill −3% (a-priori)
- 2.60% sensitivity readout only — not verdict
- GER40 costs ASSUMPTION (C22): contractSize=1, commission=0, spread=2.0 pts, EUR→USD 1:1
- ACCEPT gates = C22–C25 (HO ≤90d is gate; Explorer outside is cross-check)

### Paths
- Spec: `research/btc/2026-10-07-candidate-26/ftmo-candidate-26.md`
- Runner: `research/btc/2026-10-07-candidate-26/run_candidate_26.py`
- Results: `research/btc/2026-10-07-candidate-26/candidate-26-results.md`

Nothing live. Do not arm without Odin yes.
