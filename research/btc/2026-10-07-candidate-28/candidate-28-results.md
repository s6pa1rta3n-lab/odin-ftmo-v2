# Candidate 28 Results — Index Donchian + soft DD governor

**NO — UK100/FRA40 Donchian+softgov does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

**Measured:** 2026-10-07 12:28:22 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**UK100 data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/gbridxgbp-m1-bid-2024-01-01-2026-09-02.csv` sha256 `8246f68e3830d1163a77e3c6fd51497f766c52f8c07f713c46b651d1f9478bee` end `2026-09-01 23:58:00+00:00`
**FRA40 data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/fraidxeur-m1-bid-2024-01-01-2026-09-02.csv` sha256 `aeb0b71222372e6c8101dc86903cc7a7831c5690744d0dfde315ab732dd7df4d` end `2026-09-01 19:59:00+00:00`

## ASSUMPTIONS

| Item | Value |
|---|---|
| Account | $100,000 2-step |
| Challenge / Verification | +10% / +5% |
| Daily / Max DD | 5% / 10% |
| Soft gov bands | **<5%** full / **5–8%** mid / **≥8%** floor (never block) |
| Single-book risks | **2.50% / 1.25% / 0.75%** |
| Joint per-leg risks | **1.25% / 0.625% / 0.375%** |
| contractSize | **1** (catalogue UK100.cash / FRA40.cash) |
| commission | **0** (catalogue) |
| UK100 spread | **1.5** pts (**ASSUMPTION** — feed missing) |
| FRA40 spread | **1.5** pts (**ASSUMPTION** — feed missing) |
| UK100 GBP→USD | **1:1** (**ASSUMPTION** — research; catalogue profitCurrency=GBP) |
| FRA40 EUR→USD | **1:1** (**ASSUMPTION** — research; catalogue profitCurrency=EUR) |
| Gold packaging | Forbidden |

## Scoreboard

| Book | Symbol | Gov | Full/Mid/Floor | HO $/mo | Leave-out | Ext | Worst day | Max DD | ≤90d (HO-era) | seq90 (HO-era) | Legal | Decision |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 28A ungov 2.50% | UK100 | OFF | 2.50/1.25/0.75% | 348 | -4,406 | N/A | -2.91% | 13.7% | 0/811 (0) | 0/811 (0) | NO | REJECT |
| 28A soft 2.50→1.25→0.75 | UK100 | SOFT | 2.50/1.25/0.75% | 57 | -1,840 | N/A | -2.52% | 10.3% | 0/811 (0) | 0/811 (0) | NO | REJECT |
| 28B ungov 2.50% | FRA40 | OFF | 2.50/1.25/0.75% | -508 | -8,073 | N/A | -2.52% | 20.2% | 0/852 (0) | 0/842 (0) | NO | REJECT |
| 28B soft 2.50→1.25→0.75 | FRA40 | SOFT | 2.50/1.25/0.75% | -160 | -2,576 | N/A | -2.52% | 12.1% | 0/852 (0) | 0/842 (0) | NO | REJECT |
| 28C ungov joint@1.25% | JOINT | OFF | 1.25/0.62/0.38% | 107 | -1,698 | N/A | -1.46% | 10.8% | 0/831 (0) | 0/831 (0) | NO | REJECT |
| 28C soft joint 1.25→0.625→0.375 | JOINT | SOFT | 1.25/0.62/0.38% | 7 | -770 | N/A | -1.26% | 9.0% | 0/831 (0) | 0/831 (0) | YES | REJECT |

## 28A — ungov 2.50% (gov=OFF)

**Decision: REJECT**

- Chassis: `uk100-donchian-20d-dual-1r`
- Trades: n=51 L/S=36/15 WR=51.0% reasons={'TIME': 21, 'TP': 15, 'SL': 14, 'SL_OPEN': 1} gov={'n/a': 51} by_sym={'UK100': 51}
- HO $3,406.00 (~$347.92/mo); Fit $-3,881.54; Leave-out $-4,406.11 (drop ['2026-02', '2026-01']); Ext UNAVAILABLE (index feeds end 2026-09-01; no dukas-ext) 
- Max DD 13.71%; worst Prague day 2025-06-22 -2.91%; fail-days=0; Legal=NO
- Windows: ≤60d 0/841; ≤90d cont 0/811 (HO-era starts 0); seq90 reset 0/811 (HO-era 0)
- Final equity $99,524.46

Meta: `{"funnel": {"no_break": 426, "signals": 51, "ignored_in_pos": 50}, "final_equity": 99524.45934200003, "peak_equity": 106677.633104, "killed_days": 0, "n_daily": 816, "unfinished": 0, "chassis": "uk100-donchian-20d-dual-1r", "taken": 51, "use_gov": false, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 1.5, "symbol": "UK100"}`

## 28A — soft 2.50→1.25→0.75 (gov=SOFT)

**Decision: REJECT**

- Chassis: `uk100-donchian-20d-dual-1r+softgov`
- Trades: n=51 L/S=36/15 WR=51.0% reasons={'TIME': 21, 'TP': 15, 'SL': 14, 'SL_OPEN': 1} gov={'full': 9, 'mid': 7, 'floor': 35} by_sym={'UK100': 51}
- HO $557.03 (~$56.90/mo); Fit $-3,059.92; Leave-out $-1,840.31 (drop ['2026-02', '2026-01']); Ext UNAVAILABLE (index feeds end 2026-09-01; no dukas-ext) 
- Max DD 10.29%; worst Prague day 2024-08-03 -2.52%; fail-days=0; Legal=NO
- Windows: ≤60d 0/841; ≤90d cont 0/811 (HO-era starts 0); seq90 reset 0/811 (HO-era 0)
- Final equity $97,497.11

Meta: `{"funnel": {"no_break": 426, "signals": 51, "gov_full": 9, "ignored_in_pos": 50, "gov_mid": 7, "gov_floor": 35}, "final_equity": 97497.11396199994, "peak_equity": 106677.633104, "killed_days": 0, "n_daily": 816, "unfinished": 0, "chassis": "uk100-donchian-20d-dual-1r+softgov", "taken": 51, "use_gov": true, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 1.5, "symbol": "UK100"}`

## 28B — ungov 2.50% (gov=OFF)

**Decision: REJECT**

- Chassis: `fra40-donchian-20d-dual-1r`
- Trades: n=40 L/S=22/18 WR=47.5% reasons={'TIME': 17, 'TP': 10, 'SL': 13} gov={'n/a': 40} by_sym={'FRA40': 40}
- HO $-4,969.99 (~$-507.67/mo); Fit $-6,257.40; Leave-out $-8,072.59 (drop ['2026-01', '2026-06']); Ext UNAVAILABLE (index feeds end 2026-09-01; no dukas-ext) 
- Max DD 20.22%; worst Prague day 2024-09-06 -2.52%; fail-days=0; Legal=NO
- Windows: ≤60d 0/882; ≤90d cont 0/852 (HO-era starts 0); seq90 reset 0/842 (HO-era 0)
- Final equity $88,772.61

Meta: `{"funnel": {"signals": 41, "no_break": 368, "ignored_in_pos": 27}, "final_equity": 88772.60669599997, "peak_equity": 111015.34435399996, "killed_days": 0, "n_daily": 681, "unfinished": 1, "chassis": "fra40-donchian-20d-dual-1r", "taken": 40, "use_gov": false, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 1.5, "symbol": "FRA40"}`

## 28B — soft 2.50→1.25→0.75 (gov=SOFT)

**Decision: REJECT**

- Chassis: `fra40-donchian-20d-dual-1r+softgov`
- Trades: n=40 L/S=22/18 WR=47.5% reasons={'TIME': 17, 'TP': 10, 'SL': 13} gov={'full': 13, 'mid': 7, 'floor': 20} by_sym={'FRA40': 40}
- HO $-1,566.65 (~$-160.03/mo); Fit $-768.08; Leave-out $-2,575.67 (drop ['2026-01', '2026-06']); Ext UNAVAILABLE (index feeds end 2026-09-01; no dukas-ext) 
- Max DD 12.09%; worst Prague day 2024-09-06 -2.52%; fail-days=0; Legal=NO
- Windows: ≤60d 0/882; ≤90d cont 0/852 (HO-era starts 0); seq90 reset 0/842 (HO-era 0)
- Final equity $97,665.27

Meta: `{"funnel": {"signals": 41, "gov_full": 13, "no_break": 368, "ignored_in_pos": 27, "gov_mid": 7, "gov_floor": 21}, "final_equity": 97665.27381799997, "peak_equity": 111015.34435399996, "killed_days": 0, "n_daily": 681, "unfinished": 1, "chassis": "fra40-donchian-20d-dual-1r+softgov", "taken": 40, "use_gov": true, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 1.5, "symbol": "FRA40"}`

## 28C — ungov joint@1.25% (gov=OFF)

**Decision: REJECT**

- Chassis: `uk100+fra40-donchian-joint-1.25`
- Trades: n=60 L/S=38/22 WR=51.7% reasons={'TIME': 24, 'TP': 17, 'SL': 18, 'SL_OPEN': 1} gov={'n/a': 60} by_sym={'FRA40': 21, 'UK100': 39}
- HO $1,048.36 (~$107.09/mo); Fit $-2,893.95; Leave-out $-1,697.59 (drop ['2026-01', '2026-03']); Ext UNAVAILABLE (index feeds end 2026-09-01; no dukas-ext) 
- Max DD 10.82%; worst Prague day 2025-06-22 -1.46%; fail-days=0; Legal=NO
- Windows: ≤60d 0/861; ≤90d cont 0/831 (HO-era starts 0); seq90 reset 0/831 (HO-era 0)
- Final equity $98,154.41

Meta: `{"funnel": {"taken": 60, "skip_overlap": 31}, "final_equity": 98154.41202999995, "peak_equity": 106576.13802799997, "killed_days": 0, "chassis": "uk100+fra40-donchian-joint-1.25", "taken": 60, "use_gov": false, "full_risk": 0.0125, "mid_risk": 0.00625, "floor_risk": 0.00375, "n_uk_sigs": 51, "n_fra_sigs": 40, "symbol": "JOINT"}`

## 28C — soft joint 1.25→0.625→0.375 (gov=SOFT)

**Decision: REJECT**

- Chassis: `uk100+fra40-donchian-joint-1.25+softgov`
- Trades: n=60 L/S=38/22 WR=51.7% reasons={'TIME': 24, 'TP': 17, 'SL': 18, 'SL_OPEN': 1} gov={'full': 20, 'mid': 22, 'floor': 18} by_sym={'FRA40': 21, 'UK100': 39}
- HO $69.87 (~$7.14/mo); Fit $-2,360.16; Leave-out $-769.88 (drop ['2026-01', '2026-03']); Ext UNAVAILABLE (index feeds end 2026-09-01; no dukas-ext) 
- Max DD 8.97%; worst Prague day 2024-09-13 -1.26%; fail-days=0; Legal=YES
- Windows: ≤60d 0/861; ≤90d cont 0/831 (HO-era starts 0); seq90 reset 0/831 (HO-era 0)
- Final equity $97,709.72

Meta: `{"funnel": {"gov_full": 20, "taken": 60, "skip_overlap": 31, "gov_mid": 22, "gov_floor": 18}, "final_equity": 97709.71620599992, "peak_equity": 106576.13802799997, "killed_days": 0, "chassis": "uk100+fra40-donchian-joint-1.25+softgov", "taken": 60, "use_gov": true, "full_risk": 0.0125, "mid_risk": 0.00625, "floor_risk": 0.00375, "n_uk_sigs": 51, "n_fra_sigs": 40, "symbol": "JOINT"}`

## Live

Research only — C4 / drip / FREEZE / MetaAPI / live VM **untouched**.
Gold not packaged. Do not deploy.

