# Candidate 30 Results — WTI / light crude Donchian + soft DD governor

**NO — WTI Donchian+softgov does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

**Measured:** 2026-10-07 12:34:09 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**WTI data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/lightcmdusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `57ad7da74341f61274b11b6a369c90004797a02813b60deadd50b1242de48b8e` end `2026-09-01 23:59:00+00:00`

## ASSUMPTIONS

| Item | Value |
|---|---|
| Account | $100,000 2-step |
| Challenge / Verification | +10% / +5% |
| Daily / Max DD | 5% / 10% |
| Soft gov bands | **<5%** full / **5–8%** mid / **≥8%** floor (never block) |
| Risks | **2.50% / 1.25% / 0.75%** |
| WTI contractSize | **100** (catalogue USOIL.cash) |
| commission | **0** (catalogue) |
| WTI spread | **0.03** price units (**ASSUMPTION** — feed missing; task lock; Brent C23 used 0.04) |
| profitCurrency | **USD** (no FX) |
| Gold packaging | Forbidden |
| Brent re-run | Forbidden (C23 already REJECT) |

## Scoreboard

| Book | Symbol | Gov | Full/Mid/Floor | HO $/mo | Leave-out | Ext | Worst day | Max DD | ≤90d (HO-era) | seq90 (HO-era) | Legal | Decision |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 30A ungov 2.50% | WTI | OFF | 2.50/1.25/0.75% | 623 | -5,014 | N/A | -2.86% | 10.2% | 0/824 (0) | 0/824 (0) | NO | REJECT |
| 30B soft 2.50→1.25→0.75 | WTI | SOFT | 2.50/1.25/0.75% | 30 | -2,989 | N/A | -2.53% | 8.8% | 0/824 (0) | 0/824 (0) | YES | REJECT |

## 30A — ungov 2.50% (gov=OFF)

**Decision: REJECT**

- Chassis: `wti-donchian-20d-dual-1r`
- Trades: n=51 L/S=32/19 WR=51.0% reasons={'SL': 16, 'TIME': 12, 'TP': 21, 'SL_BOTH': 1, 'SL_OPEN': 1} gov={'n/a': 51} by_sym={'WTI': 51}
- HO $6,097.68 (~$622.86/mo); Fit $-2,046.05; Leave-out $-5,014.04 (drop ['2026-03', '2026-01']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 10.17%; worst Prague day 2026-07-26 -2.86%; fail-days=0; Legal=NO
- Windows: ≤60d 0/854; ≤90d cont 0/824 (HO-era starts 0); seq90 reset 0/824 (HO-era 0)
- Final equity $104,051.63

Meta: `{"funnel": {"no_break": 521, "signals": 51, "ignored_in_pos": 39, "no_next": 1}, "final_equity": 104051.62500000006, "peak_equity": 108063.35160000007, "killed_days": 0, "n_daily": 832, "unfinished": 0, "chassis": "wti-donchian-20d-dual-1r", "taken": 51, "use_gov": false, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 0.03, "contract": 100.0, "symbol": "WTI"}`

## 30B — soft 2.50→1.25→0.75 (gov=SOFT)

**Decision: REJECT**

- Chassis: `wti-donchian-20d-dual-1r+softgov`
- Trades: n=51 L/S=32/19 WR=51.0% reasons={'SL': 16, 'TIME': 12, 'TP': 21, 'SL_BOTH': 1, 'SL_OPEN': 1} gov={'full': 16, 'mid': 28, 'floor': 7} by_sym={'WTI': 51}
- HO $289.70 (~$29.59/mo); Fit $-7,854.27; Leave-out $-2,989.30 (drop ['2026-03', '2026-01']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 8.84%; worst Prague day 2025-04-04 -2.53%; fail-days=0; Legal=YES
- Windows: ≤60d 0/854; ≤90d cont 0/824 (HO-era starts 0); seq90 reset 0/824 (HO-era 0)
- Final equity $92,435.43

Meta: `{"funnel": {"no_break": 521, "signals": 51, "gov_full": 16, "ignored_in_pos": 39, "gov_mid": 28, "gov_floor": 7, "no_next": 1}, "final_equity": 92435.42920000001, "peak_equity": 100000.0, "killed_days": 0, "n_daily": 832, "unfinished": 0, "chassis": "wti-donchian-20d-dual-1r+softgov", "taken": 51, "use_gov": true, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 0.03, "contract": 100.0, "symbol": "WTI"}`

## Live

Research only — C4 / drip / FREEZE / MetaAPI / live VM **untouched**.
Gold not packaged. Brent not re-run. Do not deploy.

