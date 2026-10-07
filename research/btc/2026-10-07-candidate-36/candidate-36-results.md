# Candidate 36 Results — AUS200 Donchian + soft DD governor

**NO — AUS200 Donchian+softgov does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

**Measured:** 2026-10-07 12:42:09 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**AUS200 data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/ausidxaud-m1-bid-2024-01-01-2026-09-02.csv` sha256 `5b680ec4eb2ede73c3dcf037489792348847cde1fc1aaa8164c4525ded714672` end `2026-09-01 23:59:00+00:00`

## ASSUMPTIONS

| Item | Value |
|---|---|
| Account | $100,000 2-step |
| Challenge / Verification | +10% / +5% |
| Daily / Max DD | 5% / 10% |
| Soft gov bands | **<5%** full / **5–8%** mid / **≥8%** floor (never block) |
| Risks | **2.50% / 1.25% / 0.75%** |
| AUS200 contractSize | **1** (catalogue AUS200.cash) |
| commission | **0** (catalogue) |
| AUS200 spread | **1.5** pts (**ASSUMPTION** — feed missing; task lock; mirror C22/C28) |
| profitCurrency | **AUD** → AUD→USD **1:1 ASSUMPTION** |
| Gold packaging | Forbidden |

## Scoreboard

| Book | Symbol | Gov | Full/Mid/Floor | HO $/mo | Leave-out | Ext | Worst day | Max DD | ≤90d (HO-era) | seq90 (HO-era) | Legal | Decision |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 36A ungov 2.50% | AUS200 | OFF | 2.50/1.25/0.75% | -630 | -12,189 | N/A | -2.53% | 27.1% | 0/844 (0) | 0/844 (0) | NO | REJECT |
| 36B soft 2.50→1.25→0.75 | AUS200 | SOFT | 2.50/1.25/0.75% | -208 | -4,061 | N/A | -2.53% | 14.0% | 0/844 (0) | 0/844 (0) | NO | REJECT |

## 36A — ungov 2.50% (gov=OFF)

**Decision: REJECT**

- Chassis: `aus200-donchian-20d-dual-1r`
- Trades: n=50 L/S=33/17 WR=38.0% reasons={'TIME': 25, 'TP': 8, 'SL': 17} gov={'n/a': 50} by_sym={'AUS200': 50}
- HO $-6,163.00 (~$-629.54/mo); Fit $-17,194.91; Leave-out $-12,189.33 (drop ['2025-11', '2026-07']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 27.13%; worst Prague day 2025-12-18 -2.53%; fail-days=0; Legal=NO
- Windows: ≤60d 0/874; ≤90d cont 0/844 (HO-era starts 0); seq90 reset 0/844 (HO-era 0)
- Final equity $76,642.08

Meta: `{"funnel": {"no_break": 419, "signals": 50, "ignored_in_pos": 44, "no_next": 1}, "final_equity": 76642.081538, "peak_equity": 103528.067084, "killed_days": 0, "n_daily": 818, "unfinished": 0, "chassis": "aus200-donchian-20d-dual-1r", "taken": 50, "use_gov": false, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 1.5, "contract": 1.0, "symbol": "AUS200"}`

## 36B — soft 2.50→1.25→0.75 (gov=SOFT)

**Decision: REJECT**

- Chassis: `aus200-donchian-20d-dual-1r+softgov`
- Trades: n=50 L/S=33/17 WR=38.0% reasons={'TIME': 25, 'TP': 8, 'SL': 17} gov={'full': 9, 'mid': 1, 'floor': 40} by_sym={'AUS200': 50}
- HO $-2,033.08 (~$-207.67/mo); Fit $-8,512.86; Leave-out $-4,060.89 (drop ['2025-11', '2026-07']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 14.01%; worst Prague day 2024-07-20 -2.53%; fail-days=0; Legal=NO
- Windows: ≤60d 0/874; ≤90d cont 0/844 (HO-era starts 0); seq90 reset 0/844 (HO-era 0)
- Final equity $89,454.06

Meta: `{"funnel": {"no_break": 419, "signals": 50, "gov_full": 9, "ignored_in_pos": 44, "gov_mid": 1, "gov_floor": 40, "no_next": 1}, "final_equity": 89454.06040799999, "peak_equity": 103528.067084, "killed_days": 0, "n_daily": 818, "unfinished": 0, "chassis": "aus200-donchian-20d-dual-1r+softgov", "taken": 50, "use_gov": true, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 1.5, "contract": 1.0, "symbol": "AUS200"}`

## Live

Research only — C4 / drip / FREEZE / MetaAPI / live VM **untouched**.
Gold not packaged. Do not deploy. Do not conflict with C35.

