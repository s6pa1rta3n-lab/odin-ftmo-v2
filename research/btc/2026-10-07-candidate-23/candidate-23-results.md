# Candidate 23 Results — Brent/USA500 Donchian + soft DD governor

**NO — BRENT/USA500 Donchian+softgov does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

**Measured:** 2026-10-07 12:15:26 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**BRENT data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/brentcmdusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `e91d5f87bc6b7cf38d10f346b69eabeddcd42be184eb6fa007876baea91f79c3` end `2026-09-01 20:59:00+00:00`
**USA500 data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/usa500idxusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `c8c9f62ebf76720d780d40fb5503a2b79ce5c1f78d688575286828956db98195` end `2026-09-01 23:59:00+00:00`

## ASSUMPTIONS

| Item | Value |
|---|---|
| Account | $100,000 2-step |
| Challenge / Verification | +10% / +5% |
| Daily / Max DD | 5% / 10% |
| Soft gov bands | **<5%** full / **5–8%** mid / **≥8%** floor (never block) |
| Single-book risks | **2.50% / 1.25% / 0.75%** |
| Joint per-leg risks | **1.25% / 0.625% / 0.375%** |
| Brent contractSize | **100** (catalogue UKOIL.cash) |
| USA500 contractSize | **1** (catalogue US500.cash) |
| commission | **0** (catalogue both) |
| Brent spread | **0.04** price units (**ASSUMPTION** — feed missing; industry mid) |
| USA500 spread | **0.50** pts (**ASSUMPTION** — feed missing; industry mid) |
| profitCurrency | **USD** both (no FX) |
| Gold packaging | Forbidden |

## Scoreboard

| Book | Symbol | Gov | Full/Mid/Floor | HO $/mo | Leave-out | Ext | Worst day | Max DD | ≤90d (HO-era) | seq90 (HO-era) | Legal | Decision |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 23A ungov 2.50% | BRENT | OFF | 2.50/1.25/0.75% | 871 | +725 | N/A | -2.53% | 18.0% | 0/777 (0) | 0/777 (0) | NO | REJECT |
| 23A soft 2.50→1.25→0.75 | BRENT | SOFT | 2.50/1.25/0.75% | 273 | +264 | N/A | -2.53% | 11.9% | 0/777 (0) | 0/777 (0) | NO | REJECT |
| 23B ungov 2.50% | USA500 | OFF | 2.50/1.25/0.75% | -937 | -13,930 | N/A | -2.52% | 19.9% | 0/846 (0) | 0/846 (0) | NO | REJECT |
| 23B soft 2.50→1.25→0.75 | USA500 | SOFT | 2.50/1.25/0.75% | -282 | -4,305 | N/A | -2.52% | 12.4% | 0/846 (0) | 0/846 (0) | NO | REJECT |
| 23C ungov joint@1.25% | JOINT | OFF | 1.25/0.62/0.38% | 122 | -2,410 | N/A | -1.27% | 13.8% | 0/846 (0) | 0/846 (0) | NO | REJECT |
| 23C soft joint 1.25→0.625→0.375 | JOINT | SOFT | 1.25/0.62/0.38% | 40 | -716 | N/A | -1.27% | 10.1% | 0/846 (0) | 0/846 (0) | NO | REJECT |

## 23A — ungov 2.50% (gov=OFF)

**Decision: REJECT**

- Chassis: `brent-donchian-20d-dual-1r`
- Trades: n=40 L/S=23/17 WR=50.0% reasons={'TIME': 12, 'TP': 13, 'SL': 14, 'SL_BOTH': 1} gov={'n/a': 40} by_sym={'BRENT': 40}
- HO $8,527.68 (~$871.08/mo); Fit $-13,470.91; Leave-out $725.18 (drop ['2026-03', '2026-06']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 18.05%; worst Prague day 2024-07-11 -2.53%; fail-days=0; Legal=NO
- Windows: ≤60d 0/807; ≤90d cont 0/777 (HO-era starts 0); seq90 reset 0/777 (HO-era 0)
- Final equity $95,056.77

Meta: `{"funnel": {"no_break": 395, "signals": 40, "ignored_in_pos": 38, "no_next": 1}, "final_equity": 95056.7748, "peak_equity": 104461.12940000002, "killed_days": 0, "n_daily": 661, "unfinished": 0, "chassis": "brent-donchian-20d-dual-1r", "taken": 40, "use_gov": false, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 0.04, "contract": 100.0, "symbol": "BRENT"}`

## 23A — soft 2.50→1.25→0.75 (gov=SOFT)

**Decision: REJECT**

- Chassis: `brent-donchian-20d-dual-1r+softgov`
- Trades: n=40 L/S=23/17 WR=50.0% reasons={'TIME': 12, 'TP': 13, 'SL': 14, 'SL_BOTH': 1} gov={'full': 11, 'mid': 7, 'floor': 22} by_sym={'BRENT': 40}
- HO $2,670.61 (~$272.80/mo); Fit $-8,349.30; Leave-out $263.91 (drop ['2026-03', '2026-06']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 11.93%; worst Prague day 2024-07-11 -2.53%; fail-days=0; Legal=NO
- Windows: ≤60d 0/807; ≤90d cont 0/777 (HO-era starts 0); seq90 reset 0/777 (HO-era 0)
- Final equity $94,321.32

Meta: `{"funnel": {"no_break": 395, "signals": 40, "gov_full": 11, "ignored_in_pos": 38, "gov_mid": 7, "gov_floor": 22, "no_next": 1}, "final_equity": 94321.31520000003, "peak_equity": 103728.232, "killed_days": 0, "n_daily": 661, "unfinished": 0, "chassis": "brent-donchian-20d-dual-1r+softgov", "taken": 40, "use_gov": true, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 0.04, "contract": 100.0, "symbol": "BRENT"}`

## 23B — ungov 2.50% (gov=OFF)

**Decision: REJECT**

- Chassis: `usa500-donchian-20d-dual-1r`
- Trades: n=62 L/S=45/17 WR=43.5% reasons={'SL': 21, 'TP': 16, 'TIME': 25} gov={'n/a': 62} by_sym={'USA500': 62}
- HO $-9,172.93 (~$-936.99/mo); Fit $-4,726.59; Leave-out $-13,929.61 (drop ['2026-04', '2026-05']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 19.90%; worst Prague day 2024-02-01 -2.52%; fail-days=0; Legal=NO
- Windows: ≤60d 0/876; ≤90d cont 0/846 (HO-era starts 0); seq90 reset 0/846 (HO-era 0)
- Final equity $86,100.48

Meta: `{"funnel": {"no_break": 376, "signals": 62, "ignored_in_pos": 74, "no_next": 1}, "final_equity": 86100.47806200001, "peak_equity": 103822.25441399995, "killed_days": 0, "n_daily": 833, "unfinished": 0, "chassis": "usa500-donchian-20d-dual-1r", "taken": 62, "use_gov": false, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 0.5, "contract": 1.0, "symbol": "USA500"}`

## 23B — soft 2.50→1.25→0.75 (gov=SOFT)

**Decision: REJECT**

- Chassis: `usa500-donchian-20d-dual-1r+softgov`
- Trades: n=62 L/S=45/17 WR=43.5% reasons={'SL': 21, 'TP': 16, 'TIME': 25} gov={'full': 18, 'mid': 15, 'floor': 29} by_sym={'USA500': 62}
- HO $-2,756.05 (~$-281.52/mo); Fit $-5,340.66; Leave-out $-4,304.95 (drop ['2026-04', '2026-05']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 12.44%; worst Prague day 2024-02-01 -2.52%; fail-days=0; Legal=NO
- Windows: ≤60d 0/876; ≤90d cont 0/846 (HO-era starts 0); seq90 reset 0/846 (HO-era 0)
- Final equity $91,903.28

Meta: `{"funnel": {"no_break": 376, "signals": 62, "gov_full": 18, "ignored_in_pos": 74, "gov_mid": 15, "gov_floor": 29, "no_next": 1}, "final_equity": 91903.28348999997, "peak_equity": 103822.25441399995, "killed_days": 0, "n_daily": 833, "unfinished": 0, "chassis": "usa500-donchian-20d-dual-1r+softgov", "taken": 62, "use_gov": true, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 0.5, "contract": 1.0, "symbol": "USA500"}`

## 23C — ungov joint@1.25% (gov=OFF)

**Decision: REJECT**

- Chassis: `brent+usa500-donchian-joint-1.25`
- Trades: n=73 L/S=52/21 WR=42.5% reasons={'SL': 25, 'TP': 20, 'TIME': 27, 'SL_BOTH': 1} gov={'n/a': 73} by_sym={'USA500': 45, 'BRENT': 28}
- HO $1,197.99 (~$122.37/mo); Fit $-10,370.10; Leave-out $-2,409.80 (drop ['2026-03', '2026-06']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 13.80%; worst Prague day 2025-04-04 -1.27%; fail-days=0; Legal=NO
- Windows: ≤60d 0/876; ≤90d cont 0/846 (HO-era starts 0); seq90 reset 0/846 (HO-era 0)
- Final equity $90,827.89

Meta: `{"funnel": {"taken": 73, "skip_overlap": 29}, "final_equity": 90827.89126399996, "peak_equity": 100000.0, "killed_days": 0, "chassis": "brent+usa500-donchian-joint-1.25", "taken": 73, "use_gov": false, "full_risk": 0.0125, "mid_risk": 0.00625, "floor_risk": 0.00375, "n_brent_sigs": 40, "n_usa500_sigs": 62, "symbol": "JOINT"}`

## 23C — soft joint 1.25→0.625→0.375 (gov=SOFT)

**Decision: REJECT**

- Chassis: `brent+usa500-donchian-joint-1.25+softgov`
- Trades: n=73 L/S=52/21 WR=42.5% reasons={'SL': 25, 'TP': 20, 'TIME': 27, 'SL_BOTH': 1} gov={'full': 13, 'mid': 21, 'floor': 39} by_sym={'USA500': 45, 'BRENT': 28}
- HO $393.10 (~$40.15/mo); Fit $-9,066.29; Leave-out $-716.29 (drop ['2026-03', '2026-06']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 10.12%; worst Prague day 2024-04-18 -1.27%; fail-days=0; Legal=NO
- Windows: ≤60d 0/876; ≤90d cont 0/846 (HO-era starts 0); seq90 reset 0/846 (HO-era 0)
- Final equity $91,326.82

Meta: `{"funnel": {"gov_full": 13, "taken": 73, "skip_overlap": 29, "gov_mid": 21, "gov_floor": 39}, "final_equity": 91326.81510200001, "peak_equity": 100000.0, "killed_days": 0, "chassis": "brent+usa500-donchian-joint-1.25+softgov", "taken": 73, "use_gov": true, "full_risk": 0.0125, "mid_risk": 0.00625, "floor_risk": 0.00375, "n_brent_sigs": 40, "n_usa500_sigs": 62, "symbol": "JOINT"}`

## Live

Research only — C4 / drip / FREEZE / MetaAPI / live VM **untouched**.
Gold not packaged. Do not deploy.

