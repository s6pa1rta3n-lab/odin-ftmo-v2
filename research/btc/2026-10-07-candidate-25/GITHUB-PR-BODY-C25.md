## Candidate 25 — FX majors Donchian + soft DD governor (EURUSD / GBPUSD / USDJPY)

**NO — FX majors Donchian+softgov does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

Locked a-priori: 20d Donchian both, stop 2×ATR, TP 1R, day-10 TIME, soft gov 2.50→1.25→0.75 (never sticky-block).
25D joint: equal 1/3 soft-gov risk share on shared equity / one DD peak; one position globally.
Research only. Live C4 / drip / MetaAPI untouched. Gold not packaged.

### Scoreboard

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO-era) | seq90 (HO) | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---|---|
| 25A ungov 2.50% | EURUSD | OFF | 447 | 12.6% | 0/848 (0) | 0/848 (0) | NO | REJECT |
| 25A soft 2.50→1.25→0.75 | EURUSD | SOFT | 57 | 10.8% | 0/848 (0) | 0/848 (0) | NO | REJECT |
| 25B ungov 2.50% | GBPUSD | OFF | -764 | 32.5% | 0/847 (0) | 0/847 (0) | NO | REJECT |
| 25B soft 2.50→1.25→0.75 | GBPUSD | SOFT | -267 | 16.3% | 0/847 (0) | 0/847 (0) | NO | REJECT |
| 25C ungov 2.50% | USDJPY | OFF | -855 | 21.4% | 0/845 (0) | 0/827 (0) | NO | REJECT |
| 25C soft 2.50→1.25→0.75 | USDJPY | SOFT | -263 | 11.8% | 0/845 (0) | 0/827 (0) | NO | REJECT |
| 25D ungov joint@1/3 | JOINT | OFF | -260 | 5.9% | 0/848 (0) | 0/848 (0) | YES | REJECT |
| 25D soft joint 0.833→0.417→0.250 | JOINT | SOFT | -223 | 5.6% | 0/848 (0) | 0/848 (0) | YES | REJECT |

### ASSUMPTIONS
- contractSize=100000 / commission=$5/lot (catalogue); spreads EUR=0.00010 / GBP=0.00015 / JPY=0.015 (ASSUMPTION, feed missing)
- USDJPY→USD: JPY PnL / exit bid as mid (ASSUMPTION, bid-only feed)

### Files
- `research/btc/2026-10-07-candidate-25/`
- `run_candidate_25.py`, `ftmo-candidate-25.md`, `candidate-25-results.md`, `STATUS.md`

### Live
Research only — do not deploy.
