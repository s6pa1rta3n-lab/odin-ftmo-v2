# Candidate 33 Results — AUDUSD/USDCAD Donchian + soft DD governor

**NO — AUDUSD/USDCAD Donchian+softgov does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

**Measured:** 2026-10-07 12:38:31 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**AUDUSD data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/audusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `5c472bbb005ce6e06b5a844efb5185332e06c9b9011c7cf9555fec2c89af1e4a` end `2026-09-01 23:59:00+00:00`
**USDCAD data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/usdcad-m1-bid-2024-01-01-2026-09-02.csv` sha256 `c50c676b4c9010ac7aa9f9ad719f984ad7ed63085796787232b332b42046a8a1` end `2026-09-01 23:59:00+00:00`

## ASSUMPTIONS

| Item | Value |
|---|---|
| Account | $100,000 2-step |
| Challenge / Verification | +10% / +5% |
| Daily / Max DD | 5% / 10% |
| Soft gov bands | **<5%** full / **5–8%** mid / **≥8%** floor (never block) |
| Single-book risks | **2.50% / 1.25% / 0.75%** |
| Joint per-leg risks | **1.25% / 0.625% / 0.375%** (equal 1/2 of soft tiers) |
| contractSize | **100000** both (catalogue) |
| commission | **$5/lot** flat_USD (catalogue) |
| maxTradeVolume | **100** (catalogue) |
| AUDUSD spread | **0.00015** (**ASSUMPTION** — feed missing; ≈1.5 pip mid) |
| USDCAD spread | **0.00020** (**ASSUMPTION** — feed missing; ≈2.0 pip mid) |
| USDCAD→USD | CAD PnL / exit bid as mid (**ASSUMPTION**, bid-only feed) |
| Gold packaging | Forbidden |

## Scoreboard

| Book | Symbol | Gov | Full/Mid/Floor | HO $/mo | Leave-out | Ext | Worst day | Max DD | ≤90d (HO-era) | seq90 (HO-era) | Legal | Decision |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 33A ungov 2.50% | AUDUSD | OFF | 2.50/1.25/0.75% | -237 | -5,438 | N/A | -3.54% | 30.8% | 0/841 (0) | 0/840 (0) | NO | REJECT |
| 33A soft 2.50→1.25→0.75 | AUDUSD | SOFT | 2.50/1.25/0.75% | -77 | -1,887 | N/A | -2.56% | 16.3% | 0/841 (0) | 0/840 (0) | NO | REJECT |
| 33B ungov 2.50% | USDCAD | OFF | 2.50/1.25/0.75% | 421 | -6,460 | N/A | -2.60% | 24.8% | 0/850 (0) | 0/850 (0) | NO | REJECT |
| 33B soft 2.50→1.25→0.75 | USDCAD | SOFT | 2.50/1.25/0.75% | 139 | -1,939 | N/A | -2.58% | 13.3% | 0/850 (0) | 0/850 (0) | NO | REJECT |
| 33C ungov joint@1/2 | JOINT | OFF | 1.25/0.62/0.38% | 312 | -2,338 | N/A | -1.77% | 20.9% | 0/840 (0) | 0/840 (0) | NO | REJECT |
| 33C soft joint 1.25→0.625→0.375 | JOINT | SOFT | 1.25/0.62/0.38% | 101 | -749 | N/A | -1.77% | 11.4% | 0/840 (0) | 0/840 (0) | NO | REJECT |

## 33A — ungov 2.50% (gov=OFF)

**Decision: REJECT**

- Chassis: `audusd-donchian-20d-dual-1r`
- Trades: n=48 L/S=27/21 WR=37.5% reasons={'TIME': 17, 'SL': 20, 'TP': 10, 'SL_OPEN': 1} gov={'n/a': 48} by_sym={'AUDUSD': 48}
- HO $-2,315.69 (~$-236.54/mo); Fit $-26,410.76; Leave-out $-5,438.41 (drop ['2026-08', '2026-01']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 30.76%; worst Prague day 2025-02-02 -3.54%; fail-days=0; Legal=NO
- Windows: ≤60d 0/871; ≤90d cont 0/841 (HO-era starts 0); seq90 reset 0/840 (HO-era 0)
- Final equity $71,273.55

Meta: `{"funnel": {"no_break": 450, "signals": 49, "ignored_in_pos": 36}, "final_equity": 71273.552, "peak_equity": 100000.0, "killed_days": 1, "n_daily": 826, "unfinished": 1, "chassis": "audusd-donchian-20d-dual-1r", "taken": 48, "use_gov": false, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 0.00015, "contract": 100000.0, "commission": 5.0, "symbol": "AUDUSD"}`

## 33A — soft 2.50→1.25→0.75 (gov=SOFT)

**Decision: REJECT**

- Chassis: `audusd-donchian-20d-dual-1r+softgov`
- Trades: n=48 L/S=27/21 WR=37.5% reasons={'TIME': 17, 'SL': 20, 'TP': 10, 'SL_OPEN': 1} gov={'full': 4, 'mid': 6, 'floor': 38} by_sym={'AUDUSD': 48}
- HO $-750.18 (~$-76.63/mo); Fit $-14,829.84; Leave-out $-1,887.37 (drop ['2026-08', '2026-01']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 16.35%; worst Prague day 2024-03-20 -2.56%; fail-days=0; Legal=NO
- Windows: ≤60d 0/871; ≤90d cont 0/841 (HO-era starts 0); seq90 reset 0/840 (HO-era 0)
- Final equity $84,419.98

Meta: `{"funnel": {"no_break": 450, "signals": 49, "gov_full": 4, "ignored_in_pos": 36, "gov_mid": 6, "gov_floor": 39}, "final_equity": 84419.97800000002, "peak_equity": 100000.0, "killed_days": 0, "n_daily": 826, "unfinished": 1, "chassis": "audusd-donchian-20d-dual-1r+softgov", "taken": 48, "use_gov": true, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 0.00015, "contract": 100000.0, "commission": 5.0, "symbol": "AUDUSD"}`

## 33B — ungov 2.50% (gov=OFF)

**Decision: REJECT**

- Chassis: `usdcad-donchian-20d-dual-1r`
- Trades: n=50 L/S=31/19 WR=44.0% reasons={'SL': 17, 'TIME': 16, 'TP': 17} gov={'n/a': 50} by_sym={'USDCAD': 50}
- HO $4,122.89 (~$421.14/mo); Fit $-12,037.15; Leave-out $-6,459.51 (drop ['2026-06', '2026-08']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 24.79%; worst Prague day 2026-01-21 -2.60%; fail-days=0; Legal=NO
- Windows: ≤60d 0/880; ≤90d cont 0/850 (HO-era starts 0); seq90 reset 0/850 (HO-era 0)
- Final equity $92,085.74

Meta: `{"funnel": {"no_break": 439, "signals": 50, "ignored_in_pos": 51}, "final_equity": 92085.74245686152, "peak_equity": 108492.1778482098, "killed_days": 0, "n_daily": 801, "unfinished": 0, "chassis": "usdcad-donchian-20d-dual-1r", "taken": 50, "use_gov": false, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 0.0002, "contract": 100000.0, "commission": 5.0, "symbol": "USDCAD"}`

## 33B — soft 2.50→1.25→0.75 (gov=SOFT)

**Decision: REJECT**

- Chassis: `usdcad-donchian-20d-dual-1r+softgov`
- Trades: n=50 L/S=31/19 WR=44.0% reasons={'SL': 17, 'TIME': 16, 'TP': 17} gov={'full': 14, 'mid': 7, 'floor': 29} by_sym={'USDCAD': 50}
- HO $1,356.27 (~$138.54/mo); Fit $-9,384.62; Leave-out $-1,939.35 (drop ['2026-06', '2026-08']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 13.28%; worst Prague day 2024-02-10 -2.58%; fail-days=0; Legal=NO
- Windows: ≤60d 0/880; ≤90d cont 0/850 (HO-era starts 0); seq90 reset 0/850 (HO-era 0)
- Final equity $91,971.65

Meta: `{"funnel": {"no_break": 439, "signals": 50, "gov_full": 14, "ignored_in_pos": 51, "gov_mid": 7, "gov_floor": 29}, "final_equity": 91971.64862904706, "peak_equity": 102222.45379954351, "killed_days": 0, "n_daily": 801, "unfinished": 0, "chassis": "usdcad-donchian-20d-dual-1r+softgov", "taken": 50, "use_gov": true, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 0.0002, "contract": 100000.0, "commission": 5.0, "symbol": "USDCAD"}`

## 33C — ungov joint@1/2 (gov=OFF)

**Decision: REJECT**

- Chassis: `aud+cad-donchian-joint-1/2`
- Trades: n=65 L/S=45/20 WR=41.5% reasons={'TIME': 20, 'SL': 25, 'TP': 19, 'SL_OPEN': 1} gov={'n/a': 65} by_sym={'AUDUSD': 36, 'USDCAD': 29}
- HO $3,054.50 (~$312.01/mo); Fit $-14,610.52; Leave-out $-2,338.08 (drop ['2026-06', '2026-08']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 20.93%; worst Prague day 2025-02-02 -1.77%; fail-days=0; Legal=NO
- Windows: ≤60d 0/870; ≤90d cont 0/840 (HO-era starts 0); seq90 reset 0/840 (HO-era 0)
- Final equity $88,443.99

Meta: `{"funnel": {"taken": 65, "skip_overlap": 33}, "final_equity": 88443.98666474543, "peak_equity": 102086.91125558782, "killed_days": 0, "chassis": "aud+cad-donchian-joint-1/2", "taken": 65, "use_gov": false, "full_risk": 0.0125, "mid_risk": 0.00625, "floor_risk": 0.00375, "n_aud_sigs": 48, "n_cad_sigs": 50, "symbol": "JOINT", "joint_share_rule": "equal 1/2 of soft tiers on shared equity / one DD peak; one pos global"}`

## 33C — soft joint 1.25→0.625→0.375 (gov=SOFT)

**Decision: REJECT**

- Chassis: `aud+cad-donchian-joint-1/2+softgov`
- Trades: n=65 L/S=45/20 WR=41.5% reasons={'TIME': 20, 'SL': 25, 'TP': 19, 'SL_OPEN': 1} gov={'full': 22, 'mid': 8, 'floor': 35} by_sym={'AUDUSD': 36, 'USDCAD': 29}
- HO $985.54 (~$100.67/mo); Fit $-8,031.75; Leave-out $-748.61 (drop ['2026-06', '2026-08']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 11.41%; worst Prague day 2025-02-02 -1.77%; fail-days=0; Legal=NO
- Windows: ≤60d 0/870; ≤90d cont 0/840 (HO-era starts 0); seq90 reset 0/840 (HO-era 0)
- Final equity $92,953.79

Meta: `{"funnel": {"gov_full": 22, "taken": 65, "skip_overlap": 33, "gov_mid": 8, "gov_floor": 35}, "final_equity": 92953.7943616465, "peak_equity": 102086.91125558782, "killed_days": 0, "chassis": "aud+cad-donchian-joint-1/2+softgov", "taken": 65, "use_gov": true, "full_risk": 0.0125, "mid_risk": 0.00625, "floor_risk": 0.00375, "n_aud_sigs": 48, "n_cad_sigs": 50, "symbol": "JOINT", "joint_share_rule": "equal 1/2 of soft tiers on shared equity / one DD peak; one pos global"}`

## Live

Research only — C4 / drip / FREEZE / MetaAPI / live VM **untouched**.
Gold not packaged. Do not deploy.

