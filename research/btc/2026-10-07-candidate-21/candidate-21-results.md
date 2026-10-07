# Candidate 21 Results — Soft DD governor

**CONDITIONAL (not deployable) — soft DD governor does NOT open a 1–3mo ACCEPT path.** BTC H4 channel soft (1.00→0.50→0.25): max DD **9.6%** legal, HO ~**$310/mo** (sticky was $0), Ext **−$2.6k**, leave-out fail, ≤90d **77/917** but **HO-era 0** (Fit 2024 only) → same Fit-window trap as C20. XAG Donchian soft (2.50→1.25→0.75): DD **9.4%** legal, HO ~**$847/mo**, ≤90d **48/838** with **8 HO-era**, but leave-out remaining HO **negative** → CONDITIONAL, not ACCEPT. Vs C20 sticky: soft restores HO trading; still no deployable pass.

**Measured:** 2026-10-07 12:10:20 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**XAG data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c` end `2026-09-01 23:59:00+00:00`
**BTC data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/btcusd-m1-bid-2024-01-01-2026-09-02.csv` (+ dukas-ext if present) end `2026-10-07 11:34:00+00:00`

## ASSUMPTIONS

| Item | Value |
|---|---|
| Account | $100,000 2-step |
| Challenge / Verification | +10% / +5% |
| Daily / Max DD | 5% / 10% |
| Soft gov bands | **<5%** full / **5–8%** mid / **≥8%** floor (never block) |
| BTC 21A risks | **1.00% / 0.50% / 0.25%** |
| XAG 21B risks | **2.50% / 1.25% / 0.75%** |
| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** (ASSUMPTION — C19B parity) |
| BTC spread / commission | **15** price units / **0** |
| Gold packaging | Forbidden |

## Scoreboard vs C20 sticky

| Book | Gov | Full/Mid/Floor | HO $/mo | Leave-out | Ext | Worst day | Max DD | ≤90d (HO-era) | seq90 (HO-era) | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 21B ungov 2.50% | OFF | 2.50/1.25/0.75% | 867 | -7,270 | N/A | -2.70% | 12.4% | 77/838 (0) | 60/838 (0) | NO | REJECT |
| 21B soft 2.50→1.25→0.75 | SOFT | 2.50/1.25/0.75% | 847 | -6,976 | N/A | -2.69% | 9.4% | 48/838 (8) | 60/838 (0) | YES | CONDITIONAL |
| 21A ungov ch@1.00% | OFF | 1.00/0.50/0.25% | 2,070 | -13,567 | -3,270 | -2.01% | 13.8% | 129/917 (0) | 13/917 (0) | NO | REJECT |
| 21A soft ch 1.00→0.50→0.25 | SOFT | 1.00/0.50/0.25% | 310 | -4,467 | -2,586 | -2.01% | 9.6% | 77/917 (0) | 13/917 (0) | YES | CONDITIONAL |

### C20 sticky reference (from prior run)

| Book | Sticky HO $/mo | Sticky DD | Sticky ≤90d | Sticky seq | Note |
|---|---:|---:|---:|---:|---|
| 20A sticky | 0 | 8.5% | 0/827 | 0/322 | sticky killed all windows |
| 20B sticky | 0 | 8.0% | 77/916 | 13/536 | Fit-era only; HO=$0 Ext=$0 |

## 21B — ungov 2.50% (gov=OFF)

**Decision: REJECT**

- Chassis: `xag-donchian-20d-dual-1r`
- Trades: n=56 L/S=44/12 WR=53.6% reasons={'SL': 14, 'TP': 24, 'TIME': 17, 'SL_OPEN': 1} gov_entry_states={'n/a': 56}
- HO $8,486.64 (~$866.89/mo); Fit $6,369.76; Leave-out $-7,269.73 (drop ['2026-01', '2025-12']); Ext UNAVAILABLE (XAG feed ends 2026-09-01; no dukas-ext) 
- Max DD 12.36%; worst Prague day 2026-06-14 -2.70%; fail-days=0; Legal=NO
- Windows: ≤60d 34/868; ≤90d cont 77/838 (HO-era starts 0); seq90 reset 60/838 (HO-era 0)
- Final equity $114,856.40

### ≤90d continuous pass sample
| Start | End | Era | Start eq | Max mult | Min mult | Worst day |
|---|---|---|---:|---:|---:|---:|
| 2025-07-13 | 2025-10-10 | Fit | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-14 | 2025-10-11 | Fit | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-15 | 2025-10-12 | Fit | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-16 | 2025-10-13 | Fit | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-17 | 2025-10-14 | Fit | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-18 | 2025-10-15 | Fit | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-19 | 2025-10-16 | Fit | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-20 | 2025-10-17 | Fit | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-21 | 2025-10-18 | Fit | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-22 | 2025-10-19 | Fit | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-23 | 2025-10-20 | Fit | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-24 | 2025-10-21 | Fit | $92,944 | 1.174 | 1.015 | 0.00% |

### seq90 reset pass sample
| Start | Era | Challenge done | Verification done | Total days |
|---|---|---|---|---:|
| 2025-07-13 | Fit | 2025-09-27 | 2025-10-10 | 90 |
| 2025-07-14 | Fit | 2025-09-27 | 2025-10-10 | 89 |
| 2025-07-15 | Fit | 2025-09-27 | 2025-10-10 | 88 |
| 2025-07-16 | Fit | 2025-09-27 | 2025-10-10 | 87 |
| 2025-07-17 | Fit | 2025-09-27 | 2025-10-10 | 86 |
| 2025-07-18 | Fit | 2025-09-27 | 2025-10-10 | 85 |
| 2025-07-19 | Fit | 2025-09-27 | 2025-10-10 | 84 |
| 2025-07-20 | Fit | 2025-09-27 | 2025-10-10 | 83 |
| 2025-07-21 | Fit | 2025-09-27 | 2025-10-10 | 82 |
| 2025-07-22 | Fit | 2025-09-27 | 2025-10-10 | 81 |
| 2025-07-23 | Fit | 2025-09-27 | 2025-10-10 | 80 |
| 2025-07-24 | Fit | 2025-09-27 | 2025-10-10 | 79 |

Meta: `{"funnel": {"no_break": 447, "signals": 56, "ignored_in_pos": 47}, "final_equity": 114856.40059999995, "peak_equity": 122545.82509999994, "killed_days": 0, "n_daily": 833, "unfinished": 0, "chassis": "xag-donchian-20d-dual-1r", "taken": 56, "use_gov": false, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075}`

## 21B — soft 2.50→1.25→0.75 (gov=SOFT)

**Decision: CONDITIONAL**

- Chassis: `xag-donchian-20d-dual-1r+softgov`
- Trades: n=56 L/S=44/12 WR=53.6% reasons={'SL': 14, 'TP': 24, 'TIME': 17, 'SL_OPEN': 1} gov_entry_states={'full': 37, 'mid': 13, 'floor': 6}
- HO $8,291.16 (~$846.92/mo); Fit $1,664.50; Leave-out $-6,975.55 (drop ['2026-01', '2025-12']); Ext UNAVAILABLE (XAG feed ends 2026-09-01; no dukas-ext) 
- Max DD 9.40%; worst Prague day 2026-01-31 -2.69%; fail-days=0; Legal=YES
- Windows: ≤60d 20/868; ≤90d cont 48/838 (HO-era starts 8); seq90 reset 60/838 (HO-era 0)
- Final equity $109,955.66

### ≤90d continuous pass sample
| Start | End | Era | Start eq | Max mult | Min mult | Worst day |
|---|---|---|---:|---:|---:|---:|
| 2025-11-01 | 2026-01-29 | Fit | $101,664 | 1.156 | 0.974 | -2.58% |
| 2025-11-02 | 2026-01-30 | Fit | $101,664 | 1.156 | 0.974 | -2.58% |
| 2025-11-03 | 2026-01-31 | Fit | $101,664 | 1.156 | 0.974 | -2.69% |
| 2025-11-04 | 2026-02-01 | Fit | $101,664 | 1.156 | 0.974 | -2.69% |
| 2025-11-05 | 2026-02-02 | Fit | $101,664 | 1.156 | 0.974 | -2.69% |
| 2025-11-06 | 2026-02-03 | Fit | $101,664 | 1.156 | 0.974 | -2.69% |
| 2025-11-07 | 2026-02-04 | Fit | $101,664 | 1.156 | 0.974 | -2.69% |
| 2025-11-08 | 2026-02-05 | HO+ | $101,664 | 1.156 | 0.974 | -2.69% |
| 2025-11-09 | 2026-02-06 | HO+ | $101,664 | 1.156 | 0.974 | -2.69% |
| 2025-11-10 | 2026-02-07 | HO+ | $101,664 | 1.156 | 0.974 | -2.69% |
| 2025-11-11 | 2026-02-08 | HO+ | $101,664 | 1.156 | 0.974 | -2.69% |
| 2025-11-12 | 2026-02-09 | HO+ | $101,664 | 1.156 | 0.974 | -2.69% |

### seq90 reset pass sample
| Start | Era | Challenge done | Verification done | Total days |
|---|---|---|---|---:|
| 2025-07-13 | Fit | 2025-09-27 | 2025-10-10 | 90 |
| 2025-07-14 | Fit | 2025-09-27 | 2025-10-10 | 89 |
| 2025-07-15 | Fit | 2025-09-27 | 2025-10-10 | 88 |
| 2025-07-16 | Fit | 2025-09-27 | 2025-10-10 | 87 |
| 2025-07-17 | Fit | 2025-09-27 | 2025-10-10 | 86 |
| 2025-07-18 | Fit | 2025-09-27 | 2025-10-10 | 85 |
| 2025-07-19 | Fit | 2025-09-27 | 2025-10-10 | 84 |
| 2025-07-20 | Fit | 2025-09-27 | 2025-10-10 | 83 |
| 2025-07-21 | Fit | 2025-09-27 | 2025-10-10 | 82 |
| 2025-07-22 | Fit | 2025-09-27 | 2025-10-10 | 81 |
| 2025-07-23 | Fit | 2025-09-27 | 2025-10-10 | 80 |
| 2025-07-24 | Fit | 2025-09-27 | 2025-10-10 | 79 |

Meta: `{"funnel": {"no_break": 447, "signals": 56, "gov_full": 37, "ignored_in_pos": 47, "gov_mid": 13, "gov_floor": 6}, "final_equity": 109955.65699999998, "peak_equity": 117488.15999999996, "killed_days": 0, "n_daily": 833, "unfinished": 0, "chassis": "xag-donchian-20d-dual-1r+softgov", "taken": 56, "use_gov": true, "full_risk": 0.025, "mid_risk": 0.0125, "floor_risk": 0.0075}`

## 21A — ungov ch@1.00% (gov=OFF)

**Decision: REJECT**

- Chassis: `btc-h4-break6-channel`
- Trades: n=240 L/S=240/0 WR=35.8% reasons={'channel': 164, 'stop': 75, 'gap-stop': 1} gov_entry_states={'n/a': 240}
- HO $20,265.96 (~$2,070.12/mo); Fit $29,288.43; Leave-out $-13,567.43 (drop ['2026-08', '2026-05']); Ext measured $-3,269.86
- Max DD 13.84%; worst Prague day 2025-12-26 -2.01%; fail-days=0; Legal=NO
- Windows: ≤60d 91/947; ≤90d cont 129/917 (HO-era starts 0); seq90 reset 13/917 (HO-era 0)
- Final equity $146,284.53

### ≤90d continuous pass sample
| Start | End | Era | Start eq | Max mult | Min mult | Worst day |
|---|---|---|---:|---:|---:|---:|
| 2024-08-17 | 2024-11-14 | Fit | $106,919 | 1.182 | 0.974 | -1.02% |
| 2024-08-18 | 2024-11-15 | Fit | $106,919 | 1.182 | 0.974 | -1.02% |
| 2024-08-19 | 2024-11-16 | Fit | $106,919 | 1.182 | 0.974 | -1.02% |
| 2024-08-20 | 2024-11-17 | Fit | $106,919 | 1.182 | 0.974 | -1.02% |
| 2024-08-21 | 2024-11-18 | Fit | $105,833 | 1.194 | 0.984 | -2.01% |
| 2024-08-22 | 2024-11-19 | Fit | $105,833 | 1.194 | 0.984 | -2.01% |
| 2024-08-23 | 2024-11-20 | Fit | $104,772 | 1.206 | 0.994 | -2.01% |
| 2024-08-24 | 2024-11-21 | Fit | $104,772 | 1.206 | 0.994 | -2.01% |
| 2024-08-25 | 2024-11-22 | Fit | $104,772 | 1.206 | 0.994 | -2.01% |
| 2024-08-26 | 2024-11-23 | Fit | $104,772 | 1.206 | 0.994 | -2.01% |
| 2024-08-27 | 2024-11-24 | Fit | $106,252 | 1.190 | 0.980 | -2.01% |
| 2024-08-28 | 2024-11-25 | Fit | $106,252 | 1.190 | 0.980 | -2.01% |

### seq90 reset pass sample
| Start | Era | Challenge done | Verification done | Total days |
|---|---|---|---|---:|
| 2024-08-22 | Fit | 2024-11-09 | 2024-11-14 | 85 |
| 2024-08-23 | Fit | 2024-11-09 | 2024-11-14 | 84 |
| 2024-08-30 | Fit | 2024-11-09 | 2024-11-14 | 77 |
| 2024-08-31 | Fit | 2024-11-09 | 2024-11-14 | 76 |
| 2024-09-01 | Fit | 2024-11-09 | 2024-11-14 | 75 |
| 2024-09-02 | Fit | 2024-11-09 | 2024-11-14 | 74 |
| 2024-09-03 | Fit | 2024-11-09 | 2024-11-14 | 73 |
| 2024-09-04 | Fit | 2024-11-09 | 2024-11-14 | 72 |
| 2024-09-05 | Fit | 2024-11-09 | 2024-11-14 | 71 |
| 2024-09-06 | Fit | 2024-11-09 | 2024-11-14 | 70 |
| 2024-09-07 | Fit | 2024-11-09 | 2024-11-14 | 69 |
| 2024-09-08 | Fit | 2024-11-09 | 2024-11-14 | 68 |

Meta: `{"signals": 240, "taken": 240, "skip_kill": 0, "skip_lots": 0, "gov_floor": 0, "gov_mid": 0, "gov_full": 0, "final_equity": 146284.5303415, "peak_equity": 151297.58471400003, "killed_days": 0, "use_gov": false, "full_risk": 0.01, "mid_risk": 0.005, "floor_risk": 0.0025, "chassis": "btc-h4-break6-channel"}`

## 21A — soft ch 1.00→0.50→0.25 (gov=SOFT)

**Decision: CONDITIONAL**

- Chassis: `btc-h4-break6-channel+softgov`
- Trades: n=240 L/S=240/0 WR=35.8% reasons={'channel': 164, 'stop': 75, 'gap-stop': 1} gov_entry_states={'full': 91, 'mid': 94, 'floor': 55}
- HO $3,036.35 (~$310.16/mo); Fit $20,930.00; Leave-out $-4,467.14 (drop ['2026-08', '2026-05']); Ext measured $-2,586.11
- Max DD 9.59%; worst Prague day 2024-11-18 -2.01%; fail-days=0; Legal=YES
- Windows: ≤60d 33/947; ≤90d cont 77/917 (HO-era starts 0); seq90 reset 13/917 (HO-era 0)
- Final equity $121,380.24

### ≤90d continuous pass sample
| Start | End | Era | Start eq | Max mult | Min mult | Worst day |
|---|---|---|---:|---:|---:|---:|
| 2024-08-21 | 2024-11-18 | Fit | $106,962 | 1.161 | 0.992 | -2.01% |
| 2024-08-22 | 2024-11-19 | Fit | $106,962 | 1.161 | 0.992 | -2.01% |
| 2024-08-23 | 2024-11-20 | Fit | $106,424 | 1.166 | 0.997 | -2.01% |
| 2024-08-24 | 2024-11-21 | Fit | $106,424 | 1.166 | 0.997 | -2.01% |
| 2024-08-25 | 2024-11-22 | Fit | $106,424 | 1.166 | 0.997 | -2.01% |
| 2024-08-26 | 2024-11-23 | Fit | $106,424 | 1.166 | 0.997 | -2.01% |
| 2024-08-27 | 2024-11-24 | Fit | $107,174 | 1.158 | 0.990 | -2.01% |
| 2024-08-28 | 2024-11-25 | Fit | $107,174 | 1.158 | 0.990 | -2.01% |
| 2024-08-29 | 2024-11-26 | Fit | $107,174 | 1.158 | 0.990 | -2.01% |
| 2024-08-30 | 2024-11-27 | Fit | $107,174 | 1.158 | 0.990 | -2.01% |
| 2024-08-31 | 2024-11-28 | Fit | $106,630 | 1.164 | 0.995 | -2.01% |
| 2024-09-01 | 2024-11-29 | Fit | $106,630 | 1.164 | 0.995 | -2.01% |

### seq90 reset pass sample
| Start | Era | Challenge done | Verification done | Total days |
|---|---|---|---|---:|
| 2024-08-22 | Fit | 2024-11-09 | 2024-11-14 | 85 |
| 2024-08-23 | Fit | 2024-11-09 | 2024-11-14 | 84 |
| 2024-08-30 | Fit | 2024-11-09 | 2024-11-14 | 77 |
| 2024-08-31 | Fit | 2024-11-09 | 2024-11-14 | 76 |
| 2024-09-01 | Fit | 2024-11-09 | 2024-11-14 | 75 |
| 2024-09-02 | Fit | 2024-11-09 | 2024-11-14 | 74 |
| 2024-09-03 | Fit | 2024-11-09 | 2024-11-14 | 73 |
| 2024-09-04 | Fit | 2024-11-09 | 2024-11-14 | 72 |
| 2024-09-05 | Fit | 2024-11-09 | 2024-11-14 | 71 |
| 2024-09-06 | Fit | 2024-11-09 | 2024-11-14 | 70 |
| 2024-09-07 | Fit | 2024-11-09 | 2024-11-14 | 69 |
| 2024-09-08 | Fit | 2024-11-09 | 2024-11-14 | 68 |

Meta: `{"signals": 240, "taken": 240, "skip_kill": 0, "skip_lots": 0, "gov_floor": 55, "gov_mid": 94, "gov_full": 91, "final_equity": 121380.24300100005, "peak_equity": 128814.03448850002, "killed_days": 0, "use_gov": true, "full_risk": 0.01, "mid_risk": 0.005, "floor_risk": 0.0025, "chassis": "btc-h4-break6-channel+softgov"}`

## Soft vs sticky delta (critical)

| Pair | Soft HO$/mo | Sticky HO$/mo | Soft DD | Sticky DD | Soft ≤90d (HO) | Sticky ≤90d |
|---|---:|---:|---:|---:|---:|---:|
| BTC H4 channel | 310 | 0 | 9.6% | 8.0% | 77/917 (0) | 77/916 |
| XAG Donchian | 847 | 0 | 9.4% | 8.5% | 48/838 (8) | 0/827 |

## Live

Research only — C4 / drip / FREEZE / MetaAPI / live VM **untouched**.
Gold not packaged. Do not deploy.

