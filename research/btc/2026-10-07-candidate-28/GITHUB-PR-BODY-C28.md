## Candidate 28 — Index Donchian + soft DD governor (UK100 / FRA40)

**NO — UK100/FRA40 Donchian+softgov does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

Locked a-priori: 20d Donchian both, stop 2×ATR, TP 1R, day-10 TIME, soft gov 2.50→1.25→0.75 (never sticky-block).
Research only. Live C4 / drip / MetaAPI untouched. Gold not packaged.

### Scoreboard

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO-era) | seq90 (HO) | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---|---|
| 28A ungov 2.50% | UK100 | OFF | 348 | 13.7% | 0/811 (0) | 0/811 (0) | NO | REJECT |
| 28A soft 2.50→1.25→0.75 | UK100 | SOFT | 57 | 10.3% | 0/811 (0) | 0/811 (0) | NO | REJECT |
| 28B ungov 2.50% | FRA40 | OFF | -508 | 20.2% | 0/852 (0) | 0/842 (0) | NO | REJECT |
| 28B soft 2.50→1.25→0.75 | FRA40 | SOFT | -160 | 12.1% | 0/852 (0) | 0/842 (0) | NO | REJECT |
| 28C ungov joint@1.25% | JOINT | OFF | 107 | 10.8% | 0/831 (0) | 0/831 (0) | NO | REJECT |
| 28C soft joint 1.25→0.625→0.375 | JOINT | SOFT | 7 | 9.0% | 0/831 (0) | 0/831 (0) | YES | REJECT |

### ASSUMPTIONS
- contractSize=1, commission=0 (catalogue); spreads UK100=1.5 / FRA40=1.5 pts (feed missing); UK100 GBP→USD / FRA40 EUR→USD 1:1

### Files
- `research/btc/2026-10-07-candidate-28/`
- `run_candidate_28.py`, `ftmo-candidate-28.md`, `candidate-28-results.md`, `STATUS.md`

### Live
Research only — do not deploy.
