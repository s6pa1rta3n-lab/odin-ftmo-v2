## Candidate 22 — Index Donchian + soft DD governor (GER40 / USA30)

**CONDITIONAL — index Donchian+softgov legal DD + windows, not ACCEPT** via 22A (soft 2.50→1.25→0.75): max DD 9.4%, ≤90d 7/842 (HO-era 0), seq HO-era 0, HO ~$-268/mo. Fit-only / leave-out / Ext weak → not deployable.

Locked a-priori: 20d Donchian both, stop 2×ATR, TP 1R, day-10 TIME, soft gov 2.50→1.25→0.75 (never sticky-block).
Research only. Live C4 / drip / MetaAPI untouched. Gold not packaged.

### Scoreboard

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO-era) | seq90 (HO) | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---|---|
| 22A ungov 2.50% | GER40 | OFF | -629 | 11.8% | 7/842 (0) | 7/842 (0) | NO | REJECT |
| 22A soft 2.50→1.25→0.75 | GER40 | SOFT | -268 | 9.4% | 7/842 (0) | 7/842 (0) | YES | CONDITIONAL |
| 22B ungov 2.50% | USA30 | OFF | -200 | 19.3% | 0/843 (0) | 0/843 (0) | NO | REJECT |
| 22B soft 2.50→1.25→0.75 | USA30 | SOFT | -54 | 11.8% | 0/843 (0) | 0/843 (0) | NO | REJECT |
| 22C ungov joint@1.25% | JOINT | OFF | -21 | 7.2% | 0/842 (0) | 0/842 (0) | YES | REJECT |
| 22C soft joint 1.25→0.625→0.375 | JOINT | SOFT | -193 | 6.6% | 0/842 (0) | 0/842 (0) | YES | REJECT |

### ASSUMPTIONS
- contractSize=1, commission=0 (catalogue); spreads GER40=2.0 / USA30=2.5 pts (feed missing); GER40 EUR→USD 1:1

### Files
- `research/btc/2026-10-07-candidate-22/`
- `run_candidate_22.py`, `ftmo-candidate-22.md`, `candidate-22-results.md`, `STATUS.md`

### Live
Research only — do not deploy.
