## Candidate 33 — AUDUSD/USDCAD Donchian + soft DD governor

**NO — AUDUSD/USDCAD Donchian+softgov does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

Locked a-priori: 20d Donchian both, stop 2×ATR, TP 1R, day-10 TIME, soft gov 2.50→1.25→0.75 (never sticky-block).
33C joint: equal 1/2 soft-gov risk share on shared equity / one DD peak; one position globally.
Research only. Live C4 / drip / MetaAPI untouched. Gold not packaged.

### Scoreboard

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO-era) | seq90 (HO) | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---|---|
| 33A ungov 2.50% | AUDUSD | OFF | -237 | 30.8% | 0/841 (0) | 0/840 (0) | NO | REJECT |
| 33A soft 2.50→1.25→0.75 | AUDUSD | SOFT | -77 | 16.3% | 0/841 (0) | 0/840 (0) | NO | REJECT |
| 33B ungov 2.50% | USDCAD | OFF | 421 | 24.8% | 0/850 (0) | 0/850 (0) | NO | REJECT |
| 33B soft 2.50→1.25→0.75 | USDCAD | SOFT | 139 | 13.3% | 0/850 (0) | 0/850 (0) | NO | REJECT |
| 33C ungov joint@1/2 | JOINT | OFF | 312 | 20.9% | 0/840 (0) | 0/840 (0) | NO | REJECT |
| 33C soft joint 1.25→0.625→0.375 | JOINT | SOFT | 101 | 11.4% | 0/840 (0) | 0/840 (0) | NO | REJECT |

### ASSUMPTIONS
- contractSize=100000 / commission=$5/lot (catalogue); spreads AUD=0.00015 / CAD=0.00020 (ASSUMPTION, feed missing)
- USDCAD→USD: CAD PnL / exit bid as mid (ASSUMPTION, bid-only feed)

### Files
- `research/btc/2026-10-07-candidate-33/`
- `run_candidate_33.py`, `ftmo-candidate-33.md`, `candidate-33-results.md`, `STATUS.md`

### Live
Research only — do not deploy.
