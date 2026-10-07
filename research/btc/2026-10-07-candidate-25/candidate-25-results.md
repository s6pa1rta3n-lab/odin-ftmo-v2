# Candidate 25 Results — FX majors Donchian + soft DD governor

**NO — FX majors Donchian+softgov does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

**Measured:** 2026-10-07 12:19:57 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**EURUSD data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/eurusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `30223c125b9d0d7036e677be2b25505a9f3101f8c73cc1105e82def79f322a44` end `2026-09-01 23:59:00+00:00`
**GBPUSD data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/gbpusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `b238efd8d8240da677456a082fb1f301413715738b21314ce4f9d021f7daeb95` end `2026-09-01 23:59:00+00:00`
**USDJPY data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/usdjpy-m1-bid-2024-01-01-2026-09-02.csv` sha256 `ed7c8db716fe2e4a572dfe15d21157944427086636d1b97929bbdd49097cdcca` end `2026-09-01 23:59:00+00:00`

## ASSUMPTIONS

| Item | Value |
|---|---|
| Account | $100,000 2-step |
| Challenge / Verification | +10% / +5% |
| Daily / Max DD | 5% / 10% |
| Soft gov bands | **<5%** full / **5–8%** mid / **≥8%** floor (never block) |
| Single-book risks | **2.50% / 1.25% / 0.75%** |
| Joint per-leg risks | **≈0.833% / 0.417% / 0.250%** (equal 1/3 of soft tiers) |
| contractSize | **100000** all three (catalogue) |
| commission | **$5/lot** flat_USD (catalogue) |
| maxTradeVolume | **100** (catalogue) |
| EURUSD spread | **0.00010** (**ASSUMPTION** — feed missing; ≈1.0 pip mid) |
| GBPUSD spread | **0.00015** (**ASSUMPTION** — feed missing; ≈1.5 pip mid) |
| USDJPY spread | **0.015** (**ASSUMPTION** — feed missing; ≈1.5 pip mid) |
| USDJPY→USD | JPY PnL / exit bid as mid (**ASSUMPTION**, bid-only feed) |
| Gold packaging | Forbidden |

## Scoreboard

| Book | Symbol | Gov | Full/Mid/Floor | HO $/mo | Leave-out | Ext | Worst day | Max DD | ≤90d (HO-era) | seq90 (HO-era) | Legal | Decision |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 25A ungov 2.50% | EURUSD | OFF | 2.50/1.25/0.75% | 447 | -1,746 | N/A | -4.06% | 12.6% | 0/848 (0) | 0/848 (0) | NO | REJECT |
| 25A soft 2.50→1.25→0.75 | EURUSD | SOFT | 2.50/1.25/0.75% | 57 | -1,682 | N/A | -2.54% | 10.8% | 0/848 (0) | 0/848 (0) | NO | REJECT |
| 25B ungov 2.50% | GBPUSD | OFF | 2.50/1.25/0.75% | -764 | -11,225 | N/A | -2.56% | 32.5% | 0/847 (0) | 0/847 (0) | NO | REJECT |
| 25B soft 2.50→1.25→0.75 | GBPUSD | SOFT | 2.50/1.25/0.75% | -267 | -3,941 | N/A | -2.54% | 16.3% | 0/847 (0) | 0/847 (0) | NO | REJECT |
| 25C ungov 2.50% | USDJPY | OFF | 2.50/1.25/0.75% | -855 | -16,039 | N/A | -2.58% | 21.4% | 0/845 (0) | 0/827 (0) | NO | REJECT |
| 25C soft 2.50→1.25→0.75 | USDJPY | SOFT | 2.50/1.25/0.75% | -263 | -5,006 | N/A | -2.57% | 11.8% | 0/845 (0) | 0/827 (0) | NO | REJECT |
| 25D ungov joint@1/3 | JOINT | OFF | 0.83/0.42/0.25% | -260 | -5,116 | N/A | -0.86% | 5.9% | 0/848 (0) | 0/848 (0) | YES | REJECT |
| 25D soft joint 0.833→0.417→0.250 | JOINT | SOFT | 0.83/0.42/0.25% | -223 | -4,754 | N/A | -0.86% | 5.6% | 0/848 (0) | 0/848 (0) | YES | REJECT |

## 25A — ungov 2.50% (gov=OFF)

**Decision: REJECT**

- Chassis: `eurusd-donchian-20d-dual-1r`
- Trades: n=54 L/S=26/28 WR=51.9% reasons={'TIME': 19, 'SL': 16, 'TP': 18, 'SL_OPEN': 1} gov={'n/a': 54} by_sym={'EURUSD': 54}
- HO $4,378.69 (~$447.27/mo); Fit $-5,141.43; Leave-out $-1,745.53 (drop ['2025-12', '2026-04']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 12.58%; worst Prague day 2025-02-02 -4.06%; fail-days=0; Legal=NO
- Windows: ≤60d 0/878; ≤90d cont 0/848 (HO-era starts 0); seq90 reset 0/848 (HO-era 0)
- Final equity $99,237.26

Meta: `{"funnel": {"no_break": 429, "signals": 54, "ignored_in_pos": 43}, "final_equity": 99237.26400000007, "peak_equity": 104256.42200000008, "killed_days": 1, "n_daily": 836, "unfinished": 0, "chassis": "eurusd-donchian-20d-dual-1r", "taken": 54, "use_gov": false, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 0.0001, "contract": 100000.0, "commission": 5.0, "symbol": "EURUSD"}`

## 25A — soft 2.50→1.25→0.75 (gov=SOFT)

**Decision: REJECT**

- Chassis: `eurusd-donchian-20d-dual-1r+softgov`
- Trades: n=54 L/S=26/28 WR=51.9% reasons={'TIME': 19, 'SL': 16, 'TP': 18, 'SL_OPEN': 1} gov={'full': 9, 'mid': 21, 'floor': 24} by_sym={'EURUSD': 54}
- HO $555.98 (~$56.79/mo); Fit $-8,501.83; Leave-out $-1,682.04 (drop ['2026-04', '2026-01']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 10.85%; worst Prague day 2024-06-08 -2.54%; fail-days=0; Legal=NO
- Windows: ≤60d 0/878; ≤90d cont 0/848 (HO-era starts 0); seq90 reset 0/848 (HO-era 0)
- Final equity $92,054.15

Meta: `{"funnel": {"no_break": 429, "signals": 54, "gov_full": 9, "ignored_in_pos": 43, "gov_mid": 21, "gov_floor": 24}, "final_equity": 92054.14800000006, "peak_equity": 100115.49999999999, "killed_days": 0, "n_daily": 836, "unfinished": 0, "chassis": "eurusd-donchian-20d-dual-1r+softgov", "taken": 54, "use_gov": true, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 0.0001, "contract": 100000.0, "commission": 5.0, "symbol": "EURUSD"}`

## 25B — ungov 2.50% (gov=OFF)

**Decision: REJECT**

- Chassis: `gbpusd-donchian-20d-dual-1r`
- Trades: n=59 L/S=30/29 WR=37.3% reasons={'SL': 28, 'TIME': 17, 'TP': 14} gov={'n/a': 59} by_sym={'GBPUSD': 59}
- HO $-7,479.04 (~$-763.97/mo); Fit $-24,995.86; Leave-out $-11,225.18 (drop ['2025-12', '2026-06']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 32.47%; worst Prague day 2026-08-29 -2.56%; fail-days=0; Legal=NO
- Windows: ≤60d 0/877; ≤90d cont 0/847 (HO-era starts 0); seq90 reset 0/847 (HO-era 0)
- Final equity $67,525.10

Meta: `{"funnel": {"no_break": 431, "signals": 59, "ignored_in_pos": 40}, "final_equity": 67525.09600000003, "peak_equity": 100000.0, "killed_days": 0, "n_daily": 828, "unfinished": 0, "chassis": "gbpusd-donchian-20d-dual-1r", "taken": 59, "use_gov": false, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 0.00015, "contract": 100000.0, "commission": 5.0, "symbol": "GBPUSD"}`

## 25B — soft 2.50→1.25→0.75 (gov=SOFT)

**Decision: REJECT**

- Chassis: `gbpusd-donchian-20d-dual-1r+softgov`
- Trades: n=59 L/S=30/29 WR=37.3% reasons={'SL': 28, 'TIME': 17, 'TP': 14} gov={'full': 4, 'mid': 4, 'floor': 51} by_sym={'GBPUSD': 59}
- HO $-2,612.93 (~$-266.90/mo); Fit $-13,737.00; Leave-out $-3,941.07 (drop ['2025-12', '2026-06']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 16.35%; worst Prague day 2024-04-26 -2.54%; fail-days=0; Legal=NO
- Windows: ≤60d 0/877; ≤90d cont 0/847 (HO-era starts 0); seq90 reset 0/847 (HO-era 0)
- Final equity $83,650.07

Meta: `{"funnel": {"no_break": 431, "signals": 59, "gov_full": 4, "ignored_in_pos": 40, "gov_mid": 4, "gov_floor": 51}, "final_equity": 83650.07400000004, "peak_equity": 100000.0, "killed_days": 0, "n_daily": 828, "unfinished": 0, "chassis": "gbpusd-donchian-20d-dual-1r+softgov", "taken": 59, "use_gov": true, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 0.00015, "contract": 100000.0, "commission": 5.0, "symbol": "GBPUSD"}`

## 25C — ungov 2.50% (gov=OFF)

**Decision: REJECT**

- Chassis: `usdjpy-donchian-20d-dual-1r`
- Trades: n=52 L/S=36/16 WR=50.0% reasons={'TIME': 15, 'SL': 19, 'TP': 17, 'SL_BOTH': 1} gov={'n/a': 52} by_sym={'USDJPY': 52}
- HO $-8,373.26 (~$-855.31/mo); Fit $2,214.65; Leave-out $-16,039.17 (drop ['2026-01', '2025-11']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 21.38%; worst Prague day 2026-06-12 -2.58%; fail-days=0; Legal=NO
- Windows: ≤60d 0/875; ≤90d cont 0/845 (HO-era starts 0); seq90 reset 0/827 (HO-era 0)
- Final equity $93,841.38

Meta: `{"funnel": {"no_break": 468, "signals": 53, "ignored_in_pos": 41}, "final_equity": 93841.38478001136, "peak_equity": 119359.17978421938, "killed_days": 0, "n_daily": 833, "unfinished": 1, "chassis": "usdjpy-donchian-20d-dual-1r", "taken": 52, "use_gov": false, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 0.015, "contract": 100000.0, "commission": 5.0, "symbol": "USDJPY"}`

## 25C — soft 2.50→1.25→0.75 (gov=SOFT)

**Decision: REJECT**

- Chassis: `usdjpy-donchian-20d-dual-1r+softgov`
- Trades: n=52 L/S=36/16 WR=50.0% reasons={'TIME': 15, 'SL': 19, 'TP': 17, 'SL_BOTH': 1} gov={'full': 20, 'mid': 9, 'floor': 23} by_sym={'USDJPY': 52}
- HO $-2,578.56 (~$-263.39/mo); Fit $6,613.07; Leave-out $-5,005.75 (drop ['2026-01', '2025-11']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 11.81%; worst Prague day 2024-04-30 -2.57%; fail-days=0; Legal=NO
- Windows: ≤60d 0/875; ≤90d cont 0/845 (HO-era starts 0); seq90 reset 0/827 (HO-era 0)
- Final equity $104,034.51

Meta: `{"funnel": {"no_break": 468, "signals": 53, "gov_full": 20, "ignored_in_pos": 41, "gov_mid": 9, "gov_floor": 24}, "final_equity": 104034.5073472378, "peak_equity": 117960.83859805041, "killed_days": 0, "n_daily": 833, "unfinished": 1, "chassis": "usdjpy-donchian-20d-dual-1r+softgov", "taken": 52, "use_gov": true, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075, "spread": 0.015, "contract": 100000.0, "commission": 5.0, "symbol": "USDJPY"}`

## 25D — ungov joint@1/3 (gov=OFF)

**Decision: REJECT**

- Chassis: `eur+gbp+jpy-donchian-joint-1/3`
- Trades: n=81 L/S=48/33 WR=55.6% reasons={'TIME': 25, 'TP': 29, 'SL': 26, 'SL_BOTH': 1} gov={'n/a': 81} by_sym={'EURUSD': 34, 'USDJPY': 23, 'GBPUSD': 24}
- HO $-2,540.81 (~$-259.54/mo); Fit $5,266.06; Leave-out $-5,116.39 (drop ['2026-03', '2026-01']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 5.90%; worst Prague day 2026-06-12 -0.86%; fail-days=0; Legal=YES
- Windows: ≤60d 0/878; ≤90d cont 0/848 (HO-era starts 0); seq90 reset 0/848 (HO-era 0)
- Final equity $102,725.25

Meta: `{"funnel": {"taken": 81, "skip_overlap": 84}, "final_equity": 102725.25138023238, "peak_equity": 109166.11135205103, "killed_days": 0, "chassis": "eur+gbp+jpy-donchian-joint-1/3", "taken": 81, "use_gov": false, "full_risk": 0.008333333333333333, "mid_risk": 0.004166666666666667, "floor_risk": 0.0025, "n_eur_sigs": 54, "n_gbp_sigs": 59, "n_jpy_sigs": 52, "symbol": "JOINT", "joint_share_rule": "equal 1/3 of soft tiers on shared equity / one DD peak; one pos global"}`

## 25D — soft joint 0.833→0.417→0.250 (gov=SOFT)

**Decision: REJECT**

- Chassis: `eur+gbp+jpy-donchian-joint-1/3+softgov`
- Trades: n=81 L/S=48/33 WR=55.6% reasons={'TIME': 25, 'TP': 29, 'SL': 26, 'SL_BOTH': 1} gov={'full': 79, 'mid': 2} by_sym={'EURUSD': 34, 'USDJPY': 23, 'GBPUSD': 24}
- HO $-2,178.78 (~$-222.56/mo); Fit $5,266.06; Leave-out $-4,754.36 (drop ['2026-03', '2026-01']); Ext UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) 
- Max DD 5.57%; worst Prague day 2026-06-12 -0.86%; fail-days=0; Legal=YES
- Windows: ≤60d 0/878; ≤90d cont 0/848 (HO-era starts 0); seq90 reset 0/848 (HO-era 0)
- Final equity $103,087.28

Meta: `{"funnel": {"gov_full": 79, "taken": 81, "skip_overlap": 84, "gov_mid": 2}, "final_equity": 103087.28138023237, "peak_equity": 109166.11135205103, "killed_days": 0, "chassis": "eur+gbp+jpy-donchian-joint-1/3+softgov", "taken": 81, "use_gov": true, "full_risk": 0.008333333333333333, "mid_risk": 0.004166666666666667, "floor_risk": 0.0025, "n_eur_sigs": 54, "n_gbp_sigs": 59, "n_jpy_sigs": 52, "symbol": "JOINT", "joint_share_rule": "equal 1/3 of soft tiers on shared equity / one DD peak; one pos global"}`

## Live

Research only — C4 / drip / FREEZE / MetaAPI / live VM **untouched**.
Gold not packaged. Do not deploy.

