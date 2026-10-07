## Candidate 30 — WTI / light crude Donchian + soft DD governor (USOIL.cash)

**NO — WTI Donchian+softgov does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

Locked a-priori: 20d Donchian both, stop 2×ATR, TP 1R, day-10 TIME, soft gov 2.50→1.25→0.75 (never sticky-block).
Research only. Live C4 / drip / MetaAPI untouched. Gold not packaged. Brent not re-run.

### Scoreboard

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO-era) | seq90 (HO) | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---|---|
| 30A ungov 2.50% | WTI | OFF | 623 | 10.2% | 0/824 (0) | 0/824 (0) | NO | REJECT |
| 30B soft 2.50→1.25→0.75 | WTI | SOFT | 30 | 8.8% | 0/824 (0) | 0/824 (0) | YES | REJECT |

### ASSUMPTIONS
- USOIL.cash contractSize=100; commission=0; spread WTI=0.03 (**ASSUMPTION**, feed missing; Brent C23 used 0.04)

### Files
- `research/btc/2026-10-07-candidate-30/`
- `run_candidate_30.py`, `ftmo-candidate-30.md`, `candidate-30-results.md`, `STATUS.md`

### Live
Research only — do not deploy.
