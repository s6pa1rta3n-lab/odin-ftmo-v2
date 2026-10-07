## Candidate 23 — Brent/USA500 Donchian + soft DD governor (BRENT / USA500)

**NO — BRENT/USA500 Donchian+softgov does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

Locked a-priori: 20d Donchian both, stop 2×ATR, TP 1R, day-10 TIME, soft gov 2.50→1.25→0.75 (never sticky-block).
Research only. Live C4 / drip / MetaAPI untouched. Gold not packaged.

### Scoreboard

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO-era) | seq90 (HO) | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---|---|
| 23A ungov 2.50% | BRENT | OFF | 871 | 18.0% | 0/777 (0) | 0/777 (0) | NO | REJECT |
| 23A soft 2.50→1.25→0.75 | BRENT | SOFT | 273 | 11.9% | 0/777 (0) | 0/777 (0) | NO | REJECT |
| 23B ungov 2.50% | USA500 | OFF | -937 | 19.9% | 0/846 (0) | 0/846 (0) | NO | REJECT |
| 23B soft 2.50→1.25→0.75 | USA500 | SOFT | -282 | 12.4% | 0/846 (0) | 0/846 (0) | NO | REJECT |
| 23C ungov joint@1.25% | JOINT | OFF | 122 | 13.8% | 0/846 (0) | 0/846 (0) | NO | REJECT |
| 23C soft joint 1.25→0.625→0.375 | JOINT | SOFT | 40 | 10.1% | 0/846 (0) | 0/846 (0) | NO | REJECT |

### ASSUMPTIONS
- UKOIL.cash contractSize=100 / US500.cash contractSize=1; commission=0; spreads Brent=0.04 / USA500=0.50 (ASSUMPTION, feed missing)

### Files
- `research/btc/2026-10-07-candidate-23/`
- `run_candidate_23.py`, `ftmo-candidate-23.md`, `candidate-23-results.md`, `STATUS.md`

### Live
Research only — do not deploy.
