# Candidate 22 Results — Index Donchian + soft DD governor

**CONDITIONAL — index Donchian+softgov legal DD + windows, not ACCEPT** via 22A (soft 2.50→1.25→0.75): max DD 9.4%, ≤90d 7/842 (HO-era 0), seq HO-era 0, HO ~$-268/mo. Fit-only / leave-out / Ext weak → not deployable.

**Measured:** 2026-10-07 12:13:22 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**GER40 data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/deuidxeur-m1-bid-2024-01-01-2026-09-02.csv` sha256 `f2b497a703bfcfe273896e467c25b3472ab1689d050ee74f3f0f057791d8010d` end `2026-09-01 23:59:00+00:00`
**USA30 data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/usa30idxusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `968d27f1eb1ea5e8df4fb138a077ec73be4d478238c4ad938cb021ec3b84746a` end `2026-09-01 23:59:00+00:00`

## ASSUMPTIONS

| Item | Value |
|---|---|
| Account | $100,000 2-step |
| Challenge / Verification | +10% / +5% |
| Daily / Max DD | 5% / 10% |
| Soft gov bands | **<5%** full / **5–8%** mid / **≥8%** floor (never block) |
| Single-book risks | **2.50% / 1.25% / 0.75%** |
| Joint per-leg risks | **1.25% / 0.625% / 0.375%** |
| contractSize | **1** (catalogue GER40.cash / US30.cash) |
| commission | **0** (catalogue) |
| GER40 spread | **2.0** pts (**ASSUMPTION** — feed missing) |
| USA30 spread | **2.5** pts (**ASSUMPTION** — feed missing) |
| GER40 EUR→USD | **1:1** (**ASSUMPTION** — research; catalogue profitCurrency=EUR) |
| Gold packaging | Forbidden |

## Scoreboard

| Book | Symbol | Gov | Full/Mid/Floor | HO $/mo | Leave-out | Ext | Worst day | Max DD | ≤90d (HO-era) | seq90 (HO-era) | Legal | Decision |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 22A ungov 2.50% | GER40 | OFF | 2.50/1.25/0.75% | -629 | -16,469 | N/A | -2.52% | 11.8% | 7/842 (0) | 7/842 (0) | NO | REJECT |
| 22A soft 2.50→1.25→0.75 | GER40 | SOFT | 2.50/1.25/0.75% | -268 | -6,474 | N/A | -2.52% | 9.4% | 7/842 (0) | 7/842 (0) | YES | CONDITIONAL |
| 22B ungov 2.50% | USA30 | OFF | 2.50/1.25/0.75% | -200 | -8,521 | N/A | -2.51% | 19.3% | 0/843 (0) | 0/843 (0) | NO | REJECT |
| 22B soft 2.50→1.25→0.75 | USA30 | SOFT | 2.50/1.25/0.75% | -54 | -2,643 | N/A | -2.51% | 11.8% | 0/843 (0) | 0/843 (0) | NO | REJECT |
| 22C ungov joint@1.25% | JOINT | OFF | 1.25/0.62/0.38% | -21 | -7,045 | N/A | -1.26% | 7.2% | 0/842 (0) | 0/842 (0) | YES | REJECT |
| 22C soft joint 1.25→0.625→0.375 | JOINT | SOFT | 1.25/0.62/0.38% | -193 | -5,967 | N/A | -1.26% | 6.6% | 0/842 (0) | 0/842 (0) | YES | REJECT |

## 22A — ungov 2.50% (gov=OFF)

**Decision: REJECT**

- Chassis: `ger40-donchian-20d-dual-1r`
- Trades: n=51 L/S=36/15 WR=54.9% reasons={'TIME': 16, 'TP': 21, 'SL': 14} gov={'n/a': 51} by_sym={'GER40': 51}
- HO $-6,160.36 (~$-629.27/mo); Fit $21,173.99; Leave-out $-16,468.61 (drop ['2026-01', '2026-08']); Ext UNAVAILABLE (index feeds end 2026-09-01; no dukas-ext) 
- Max DD 11.82%; worst Prague day 2024-04-04 -2.52%; fail-days=0; Legal=NO
- Windows: ≤60d 0/872; ≤90d cont 7/842 (HO-era starts 0); seq90 reset 7/842 (HO-era 0)
- Final equity $115,013.63

### ≤90d continuous pass sample
| Start | End | Era | Start eq | Max mult | Min mult | Worst day |
|---|---|---|---:|---:|---:|---:|
| 2024-02-17 | 2024-05-16 | Fit | $100,317 | 1.157 | 1.025 | -2.52% |
| 2024-02-18 | 2024-05-17 | Fit | $100,317 | 1.157 | 1.025 | -2.52% |
| 2024-02-19 | 2024-05-18 | Fit | $100,317 | 1.157 | 1.025 | -2.52% |
| 2024-02-20 | 2024-05-19 | Fit | $100,317 | 1.157 | 1.025 | -2.52% |
| 2024-02-21 | 2024-05-20 | Fit | $100,317 | 1.157 | 1.025 | -2.52% |
| 2024-02-22 | 2024-05-21 | Fit | $100,317 | 1.157 | 1.025 | -2.52% |
| 2024-02-23 | 2024-05-22 | Fit | $100,317 | 1.157 | 1.025 | -2.52% |

### seq90 reset pass sample
| Start | Era | Challenge done | Verification done | Total days |
|---|---|---|---|---:|
| 2024-02-17 | Fit | 2024-03-28 | 2024-05-16 | 90 |
| 2024-02-18 | Fit | 2024-03-28 | 2024-05-16 | 89 |
| 2024-02-19 | Fit | 2024-03-28 | 2024-05-16 | 88 |
| 2024-02-20 | Fit | 2024-03-28 | 2024-05-16 | 87 |
| 2024-02-21 | Fit | 2024-03-28 | 2024-05-16 | 86 |
| 2024-02-22 | Fit | 2024-03-28 | 2024-05-16 | 85 |
| 2024-02-23 | Fit | 2024-03-28 | 2024-05-16 | 84 |

Meta: `{"funnel": {"no_break": 467, "signals": 51, "ignored_in_pos": 48, "no_next": 1}, "final_equity": 115013.63312600004, "peak_equity": 128744.40092600007, "killed_days": 0, "n_daily": 822, "unfinished": 0, "chassis": "ger40-donchian-20d-dual-1r", "taken": 51, "use_gov": false, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 2.0, "symbol": "GER40"}`

## 22A — soft 2.50→1.25→0.75 (gov=SOFT)

**Decision: CONDITIONAL**

- Chassis: `ger40-donchian-20d-dual-1r+softgov`
- Trades: n=51 L/S=36/15 WR=54.9% reasons={'TIME': 16, 'TP': 21, 'SL': 14} gov={'full': 36, 'mid': 9, 'floor': 6} by_sym={'GER40': 51}
- HO $-2,619.75 (~$-267.60/mo); Fit $18,245.87; Leave-out $-6,473.85 (drop ['2026-01', '2026-04']); Ext UNAVAILABLE (index feeds end 2026-09-01; no dukas-ext) 
- Max DD 9.44%; worst Prague day 2024-04-04 -2.52%; fail-days=0; Legal=YES
- Windows: ≤60d 0/872; ≤90d cont 7/842 (HO-era starts 0); seq90 reset 7/842 (HO-era 0)
- Final equity $115,626.12

### ≤90d continuous pass sample
| Start | End | Era | Start eq | Max mult | Min mult | Worst day |
|---|---|---|---:|---:|---:|---:|
| 2024-02-17 | 2024-05-16 | Fit | $100,317 | 1.157 | 1.025 | -2.52% |
| 2024-02-18 | 2024-05-17 | Fit | $100,317 | 1.157 | 1.025 | -2.52% |
| 2024-02-19 | 2024-05-18 | Fit | $100,317 | 1.157 | 1.025 | -2.52% |
| 2024-02-20 | 2024-05-19 | Fit | $100,317 | 1.157 | 1.025 | -2.52% |
| 2024-02-21 | 2024-05-20 | Fit | $100,317 | 1.157 | 1.025 | -2.52% |
| 2024-02-22 | 2024-05-21 | Fit | $100,317 | 1.157 | 1.025 | -2.52% |
| 2024-02-23 | 2024-05-22 | Fit | $100,317 | 1.157 | 1.025 | -2.52% |

### seq90 reset pass sample
| Start | Era | Challenge done | Verification done | Total days |
|---|---|---|---|---:|
| 2024-02-17 | Fit | 2024-03-28 | 2024-05-16 | 90 |
| 2024-02-18 | Fit | 2024-03-28 | 2024-05-16 | 89 |
| 2024-02-19 | Fit | 2024-03-28 | 2024-05-16 | 88 |
| 2024-02-20 | Fit | 2024-03-28 | 2024-05-16 | 87 |
| 2024-02-21 | Fit | 2024-03-28 | 2024-05-16 | 86 |
| 2024-02-22 | Fit | 2024-03-28 | 2024-05-16 | 85 |
| 2024-02-23 | Fit | 2024-03-28 | 2024-05-16 | 84 |

Meta: `{"funnel": {"no_break": 467, "signals": 51, "gov_full": 36, "ignored_in_pos": 48, "gov_mid": 9, "gov_floor": 6, "no_next": 1}, "final_equity": 115626.12364800005, "peak_equity": 127174.73459000007, "killed_days": 0, "n_daily": 822, "unfinished": 0, "chassis": "ger40-donchian-20d-dual-1r+softgov", "taken": 51, "use_gov": true, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 2.0, "symbol": "GER40"}`

## 22B — ungov 2.50% (gov=OFF)

**Decision: REJECT**

- Chassis: `usa30-donchian-20d-dual-1r`
- Trades: n=55 L/S=36/19 WR=41.8% reasons={'TP': 16, 'SL': 18, 'TIME': 21} gov={'n/a': 55} by_sym={'USA30': 55}
- HO $-1,960.93 (~$-200.30/mo); Fit $-7,374.14; Leave-out $-8,520.96 (drop ['2026-03', '2026-01']); Ext UNAVAILABLE (index feeds end 2026-09-01; no dukas-ext) 
- Max DD 19.28%; worst Prague day 2024-06-04 -2.51%; fail-days=0; Legal=NO
- Windows: ≤60d 0/873; ≤90d cont 0/843 (HO-era starts 0); seq90 reset 0/843 (HO-era 0)
- Final equity $90,664.93

Meta: `{"funnel": {"no_break": 432, "signals": 55, "ignored_in_pos": 54}, "final_equity": 90664.930086, "peak_equity": 106348.32934399998, "killed_days": 0, "n_daily": 833, "unfinished": 0, "chassis": "usa30-donchian-20d-dual-1r", "taken": 55, "use_gov": false, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 2.5, "symbol": "USA30"}`

## 22B — soft 2.50→1.25→0.75 (gov=SOFT)

**Decision: REJECT**

- Chassis: `usa30-donchian-20d-dual-1r+softgov`
- Trades: n=55 L/S=36/19 WR=41.8% reasons={'TP': 16, 'SL': 18, 'TIME': 21} gov={'full': 21, 'mid': 13, 'floor': 21} by_sym={'USA30': 55}
- HO $-525.72 (~$-53.70/mo); Fit $-4,415.00; Leave-out $-2,642.65 (drop ['2026-03', '2026-01']); Ext UNAVAILABLE (index feeds end 2026-09-01; no dukas-ext) 
- Max DD 11.82%; worst Prague day 2024-06-04 -2.51%; fail-days=0; Legal=NO
- Windows: ≤60d 0/873; ≤90d cont 0/843 (HO-era starts 0); seq90 reset 0/843 (HO-era 0)
- Final equity $95,059.28

Meta: `{"funnel": {"no_break": 432, "signals": 55, "gov_full": 21, "ignored_in_pos": 54, "gov_mid": 13, "gov_floor": 21}, "final_equity": 95059.28236999997, "peak_equity": 105981.60483999999, "killed_days": 0, "n_daily": 833, "unfinished": 0, "chassis": "usa30-donchian-20d-dual-1r+softgov", "taken": 55, "use_gov": true, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 2.5, "symbol": "USA30"}`

## 22C — ungov joint@1.25% (gov=OFF)

**Decision: REJECT**

- Chassis: `ger40+usa30-donchian-joint-1.25`
- Trades: n=69 L/S=48/21 WR=55.1% reasons={'TIME': 23, 'TP': 27, 'SL': 19} gov={'n/a': 69} by_sym={'GER40': 34, 'USA30': 35}
- HO $-209.02 (~$-21.35/mo); Fit $11,146.36; Leave-out $-7,045.24 (drop ['2026-01', '2026-03']); Ext UNAVAILABLE (index feeds end 2026-09-01; no dukas-ext) 
- Max DD 7.20%; worst Prague day 2024-04-04 -1.26%; fail-days=0; Legal=YES
- Windows: ≤60d 0/872; ≤90d cont 0/842 (HO-era starts 0); seq90 reset 0/842 (HO-era 0)
- Final equity $110,937.34

Meta: `{"funnel": {"taken": 69, "skip_overlap": 37}, "final_equity": 110937.34496400003, "peak_equity": 115508.66623400003, "killed_days": 0, "chassis": "ger40+usa30-donchian-joint-1.25", "taken": 69, "use_gov": false, "full_risk": 0.0125, "mid_risk": 0.00625, "floor_risk": 0.00375, "n_ger_sigs": 51, "n_usa_sigs": 55, "symbol": "JOINT"}`

## 22C — soft joint 1.25→0.625→0.375 (gov=SOFT)

**Decision: REJECT**

- Chassis: `ger40+usa30-donchian-joint-1.25+softgov`
- Trades: n=69 L/S=48/21 WR=55.1% reasons={'TIME': 23, 'TP': 27, 'SL': 19} gov={'full': 62, 'mid': 7} by_sym={'GER40': 34, 'USA30': 35}
- HO $-1,886.21 (~$-192.67/mo); Fit $11,146.36; Leave-out $-5,966.86 (drop ['2026-03', '2026-01']); Ext UNAVAILABLE (index feeds end 2026-09-01; no dukas-ext) 
- Max DD 6.61%; worst Prague day 2024-04-04 -1.26%; fail-days=0; Legal=YES
- Windows: ≤60d 0/872; ≤90d cont 0/842 (HO-era starts 0); seq90 reset 0/842 (HO-era 0)
- Final equity $109,260.15

Meta: `{"funnel": {"gov_full": 62, "taken": 69, "skip_overlap": 37, "gov_mid": 7}, "final_equity": 109260.14939800002, "peak_equity": 115508.66623400003, "killed_days": 0, "chassis": "ger40+usa30-donchian-joint-1.25+softgov", "taken": 69, "use_gov": true, "full_risk": 0.0125, "mid_risk": 0.00625, "floor_risk": 0.00375, "n_ger_sigs": 51, "n_usa_sigs": 55, "symbol": "JOINT"}`

## Live

Research only — C4 / drip / FREEZE / MetaAPI / live VM **untouched**.
Gold not packaged. Do not deploy.

