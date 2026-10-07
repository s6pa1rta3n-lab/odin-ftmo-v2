# Candidate 20 Results — Drawdown governor

**CONDITIONAL (thin) — BTC H4-BREAK-6 channel + governor is the only legal ≤90d path:** max DD **8.0%**, ≤90d cont **77/916**, seq **13/536**. BUT **HO net = $0** and **Ext = $0** — governor sticky-blocked after Fit; all counted windows sit in Fit (2024). XAG Donchian+gov kills every window. C17 R15+gov: legal DD, still 0 windows. **Not ACCEPT. Not deployable as a live 1–3mo start.**

**Measured:** 2026-10-07 12:07:25 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**XAG data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c` end `2026-09-01 23:59:00+00:00`
**BTC data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/btcusd-m1-bid-2024-01-01-2026-09-02.csv` (+ dukas-ext if present) end `2026-10-07 11:34:00+00:00`

## ASSUMPTIONS

| Item | Value |
|---|---|
| Account | $100,000 2-step |
| Challenge / Verification | +10% / +5% |
| Daily / Max DD | 5% / 10% |
| Governor soft / hard | **5%** cut / **8%** block until dd<5% |
| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** (ASSUMPTION — C19B parity) |
| BTC spread / commission | **15** price units / **0** |
| Gold packaging | Forbidden |

## Scoreboard — ungoverened vs governed

| Book | Gov | Full/Cut | HO $/mo | Fit | Leave-out | Ext | Worst day | Max DD | ≤60d | ≤90d cont | seq90 | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 20A ungov 2.50% | NO | 2.50%/1.00% | 867 | +6,370 | -7,270 | N/A | -2.70% | 12.4% | 34/868 | 77/838 | 60/838 | NO | REJECT |
| 20A gov 2.50→1.00 block@8% | YES | 2.50%/1.00% | 0 | -5,116 | +0 | N/A | -2.56% | 8.5% | 0/857 | 0/827 | 0/322 | YES | REJECT |
| 20B ungov ch@1.00% | NO | 1.00%/0.40% | 2,070 | +29,288 | -13,567 | -3,270 | -2.01% | 13.8% | 91/947 | 129/917 | 13/917 | NO | REJECT |
| 20B gov ch 1.00→0.40 block@8% | YES | 1.00%/0.40% | 0 | +18,530 | +0 | +0 | -2.01% | 8.0% | 22/946 | 77/916 | 13/536 | YES | CONDITIONAL |
| 20C ungov R15@0.75% | NO | 0.75%/0.30% | 669 | +4,531 | -721 | +602 | -1.51% | 12.0% | 0/947 | 0/917 | 0/917 | NO | REJECT |
| 20C gov R15 0.75→0.30 block@8% | YES | 0.75%/0.30% | 0 | +5,138 | +0 | +0 | -0.77% | 8.2% | 0/947 | 0/917 | 0/155 | YES | REJECT |

## 20A — ungov 2.50% (gov=OFF)

**Decision: REJECT**

- Chassis: `xag-donchian-20d-dual-1r`
- Trades: n=56 L/S=44/12 WR=53.6% reasons={'SL': 14, 'TP': 24, 'TIME': 17, 'SL_OPEN': 1} gov_entry_states={'n/a': 56}
- HO $8,486.64 (~$866.89/mo); Fit $6,369.76; Leave-out $-7,269.73 (drop ['2026-01', '2025-12']); Ext UNAVAILABLE (XAG feed ends 2026-09-01; no dukas-ext) 
- Max DD 12.36%; worst Prague day 2026-06-14 -2.70%; fail-days=0; Legal=NO
- Windows: ≤60d 34/868; ≤90d cont 77/838; seq90 reset 60/838
- Final equity $114,856.40

### ≤90d continuous pass sample
| Start | End | Start eq | Max mult | Min mult | Worst day |
|---|---|---:|---:|---:|---:|
| 2025-07-13 | 2025-10-10 | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-14 | 2025-10-11 | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-15 | 2025-10-12 | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-16 | 2025-10-13 | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-17 | 2025-10-14 | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-18 | 2025-10-15 | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-19 | 2025-10-16 | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-20 | 2025-10-17 | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-21 | 2025-10-18 | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-22 | 2025-10-19 | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-23 | 2025-10-20 | $92,944 | 1.174 | 1.015 | 0.00% |
| 2025-07-24 | 2025-10-21 | $92,944 | 1.174 | 1.015 | 0.00% |

### seq90 reset pass sample
| Start | Challenge done | Verification done | Total days |
|---|---|---|---:|
| 2025-07-13 | 2025-09-27 | 2025-10-10 | 90 |
| 2025-07-14 | 2025-09-27 | 2025-10-10 | 89 |
| 2025-07-15 | 2025-09-27 | 2025-10-10 | 88 |
| 2025-07-16 | 2025-09-27 | 2025-10-10 | 87 |
| 2025-07-17 | 2025-09-27 | 2025-10-10 | 86 |
| 2025-07-18 | 2025-09-27 | 2025-10-10 | 85 |
| 2025-07-19 | 2025-09-27 | 2025-10-10 | 84 |
| 2025-07-20 | 2025-09-27 | 2025-10-10 | 83 |
| 2025-07-21 | 2025-09-27 | 2025-10-10 | 82 |
| 2025-07-22 | 2025-09-27 | 2025-10-10 | 81 |
| 2025-07-23 | 2025-09-27 | 2025-10-10 | 80 |
| 2025-07-24 | 2025-09-27 | 2025-10-10 | 79 |

Meta: `{"funnel": {"no_break": 447, "signals": 56, "ignored_in_pos": 47}, "final_equity": 114856.40059999995, "peak_equity": 122545.82509999994, "killed_days": 0, "n_daily": 833, "unfinished": 0, "chassis": "xag-donchian-20d-dual-1r", "taken": 56, "use_gov": false, "full_risk": 0.025, "cut_risk": 0.01}`

## 20A — gov 2.50→1.00 block@8% (gov=ON)

**Decision: REJECT**

- Chassis: `xag-donchian-20d-dual-1r+gov`
- Trades: n=23 L/S=17/6 WR=43.5% reasons={'SL': 6, 'TP': 5, 'TIME': 12} gov_entry_states={'full': 20, 'cut': 3}
- HO $0.00 (~$0.00/mo); Fit $-5,116.36; Leave-out $0.00 (drop []); Ext UNAVAILABLE (XAG feed ends 2026-09-01; no dukas-ext) 
- Max DD 8.51%; worst Prague day 2024-02-29 -2.56%; fail-days=0; Legal=YES
- Windows: ≤60d 0/857; ≤90d cont 0/827; seq90 reset 0/322
- Final equity $94,883.64

Meta: `{"funnel": {"no_break": 565, "signals": 88, "gov_full": 20, "ignored_in_pos": 15, "gov_cut": 3, "gov_block": 65}, "final_equity": 94883.6408, "peak_equity": 103707.1896, "killed_days": 0, "n_daily": 833, "unfinished": 0, "chassis": "xag-donchian-20d-dual-1r+gov", "taken": 23, "use_gov": true, "full_risk": 0.025, "cut_risk": 0.01}`

## 20B — ungov ch@1.00% (gov=OFF)

**Decision: REJECT**

- Chassis: `btc-h4-break6-channel`
- Trades: n=240 L/S=240/0 WR=35.8% reasons={'channel': 164, 'stop': 75, 'gap-stop': 1} gov_entry_states={'n/a': 240}
- HO $20,265.96 (~$2,070.12/mo); Fit $29,288.43; Leave-out $-13,567.43 (drop ['2026-08', '2026-05']); Ext measured $-3,269.86
- Max DD 13.84%; worst Prague day 2025-12-26 -2.01%; fail-days=0; Legal=NO
- Windows: ≤60d 91/947; ≤90d cont 129/917; seq90 reset 13/917
- Final equity $146,284.53

### ≤90d continuous pass sample
| Start | End | Start eq | Max mult | Min mult | Worst day |
|---|---|---:|---:|---:|---:|
| 2024-08-17 | 2024-11-14 | $106,919 | 1.182 | 0.974 | -1.02% |
| 2024-08-18 | 2024-11-15 | $106,919 | 1.182 | 0.974 | -1.02% |
| 2024-08-19 | 2024-11-16 | $106,919 | 1.182 | 0.974 | -1.02% |
| 2024-08-20 | 2024-11-17 | $106,919 | 1.182 | 0.974 | -1.02% |
| 2024-08-21 | 2024-11-18 | $105,833 | 1.194 | 0.984 | -2.01% |
| 2024-08-22 | 2024-11-19 | $105,833 | 1.194 | 0.984 | -2.01% |
| 2024-08-23 | 2024-11-20 | $104,772 | 1.206 | 0.994 | -2.01% |
| 2024-08-24 | 2024-11-21 | $104,772 | 1.206 | 0.994 | -2.01% |
| 2024-08-25 | 2024-11-22 | $104,772 | 1.206 | 0.994 | -2.01% |
| 2024-08-26 | 2024-11-23 | $104,772 | 1.206 | 0.994 | -2.01% |
| 2024-08-27 | 2024-11-24 | $106,252 | 1.190 | 0.980 | -2.01% |
| 2024-08-28 | 2024-11-25 | $106,252 | 1.190 | 0.980 | -2.01% |

### seq90 reset pass sample
| Start | Challenge done | Verification done | Total days |
|---|---|---|---:|
| 2024-08-22 | 2024-11-09 | 2024-11-14 | 85 |
| 2024-08-23 | 2024-11-09 | 2024-11-14 | 84 |
| 2024-08-30 | 2024-11-09 | 2024-11-14 | 77 |
| 2024-08-31 | 2024-11-09 | 2024-11-14 | 76 |
| 2024-09-01 | 2024-11-09 | 2024-11-14 | 75 |
| 2024-09-02 | 2024-11-09 | 2024-11-14 | 74 |
| 2024-09-03 | 2024-11-09 | 2024-11-14 | 73 |
| 2024-09-04 | 2024-11-09 | 2024-11-14 | 72 |
| 2024-09-05 | 2024-11-09 | 2024-11-14 | 71 |
| 2024-09-06 | 2024-11-09 | 2024-11-14 | 70 |
| 2024-09-07 | 2024-11-09 | 2024-11-14 | 69 |
| 2024-09-08 | 2024-11-09 | 2024-11-14 | 68 |

Meta: `{"signals": 240, "taken": 240, "skip_kill": 0, "skip_lots": 0, "gov_block": 0, "gov_cut": 0, "gov_full": 0, "final_equity": 146284.5303415, "peak_equity": 151297.58471400003, "killed_days": 0, "use_gov": false, "full_risk": 0.01, "cut_risk": 0.004, "chassis": "btc-h4-break6-channel"}`

## 20B — gov ch 1.00→0.40 block@8% (gov=ON)

**Decision: CONDITIONAL**

- Chassis: `btc-h4-break6-channel+gov`
- Trades: n=152 L/S=152/0 WR=37.5% reasons={'channel': 105, 'stop': 47} gov_entry_states={'full': 66, 'cut': 86}
- HO $0.00 (~$0.00/mo); Fit $18,530.00; Leave-out $0.00 (drop []); Ext measured $0.00
- Max DD 8.00%; worst Prague day 2024-11-18 -2.01%; fail-days=0; Legal=YES
- Windows: ≤60d 22/946; ≤90d cont 77/916; seq90 reset 13/536
- Final equity $118,530.00

### ≤90d continuous pass sample
| Start | End | Start eq | Max mult | Min mult | Worst day |
|---|---|---:|---:|---:|---:|
| 2024-08-21 | 2024-11-18 | $107,155 | 1.159 | 0.994 | -2.01% |
| 2024-08-22 | 2024-11-19 | $107,155 | 1.159 | 0.994 | -2.01% |
| 2024-08-23 | 2024-11-20 | $106,731 | 1.163 | 0.998 | -2.01% |
| 2024-08-24 | 2024-11-21 | $106,731 | 1.163 | 0.998 | -2.01% |
| 2024-08-25 | 2024-11-22 | $106,731 | 1.163 | 0.998 | -2.01% |
| 2024-08-26 | 2024-11-23 | $106,731 | 1.163 | 0.998 | -2.01% |
| 2024-08-27 | 2024-11-24 | $107,335 | 1.157 | 0.992 | -2.01% |
| 2024-08-28 | 2024-11-25 | $107,335 | 1.157 | 0.992 | -2.01% |
| 2024-08-29 | 2024-11-26 | $107,335 | 1.157 | 0.992 | -2.01% |
| 2024-08-30 | 2024-11-27 | $107,335 | 1.157 | 0.992 | -2.01% |
| 2024-08-31 | 2024-11-28 | $106,908 | 1.161 | 0.996 | -2.01% |
| 2024-09-01 | 2024-11-29 | $106,908 | 1.161 | 0.996 | -2.01% |

### seq90 reset pass sample
| Start | Challenge done | Verification done | Total days |
|---|---|---|---:|
| 2024-08-22 | 2024-11-09 | 2024-11-14 | 85 |
| 2024-08-23 | 2024-11-09 | 2024-11-14 | 84 |
| 2024-08-30 | 2024-11-09 | 2024-11-14 | 77 |
| 2024-08-31 | 2024-11-09 | 2024-11-14 | 76 |
| 2024-09-01 | 2024-11-09 | 2024-11-14 | 75 |
| 2024-09-02 | 2024-11-09 | 2024-11-14 | 74 |
| 2024-09-03 | 2024-11-09 | 2024-11-14 | 73 |
| 2024-09-04 | 2024-11-09 | 2024-11-14 | 72 |
| 2024-09-05 | 2024-11-09 | 2024-11-14 | 71 |
| 2024-09-06 | 2024-11-09 | 2024-11-14 | 70 |
| 2024-09-07 | 2024-11-09 | 2024-11-14 | 69 |
| 2024-09-08 | 2024-11-09 | 2024-11-14 | 68 |

Meta: `{"signals": 240, "taken": 152, "skip_kill": 0, "skip_lots": 0, "gov_block": 88, "gov_cut": 86, "gov_full": 66, "final_equity": 118530.00457800012, "peak_equity": 128839.12567350008, "killed_days": 0, "use_gov": true, "full_risk": 0.01, "cut_risk": 0.004, "chassis": "btc-h4-break6-channel+gov"}`

## 20C — ungov R15@0.75% (gov=OFF)

**Decision: REJECT**

- Chassis: `btc-h4-break6-r15-c17`
- Trades: n=303 L/S=303/0 WR=42.6% reasons={'target': 128, 'stop': 172, 'gap-target': 1, 'gap-stop': 2} gov_entry_states={'n/a': 303}
- HO $6,553.32 (~$669.41/mo); Fit $4,530.98; Leave-out $-721.04 (drop ['2026-08', '2026-03']); Ext measured $601.71
- Max DD 12.02%; worst Prague day 2025-12-26 -1.51%; fail-days=0; Legal=NO
- Windows: ≤60d 0/947; ≤90d cont 0/917; seq90 reset 0/917
- Final equity $111,686.01

Meta: `{"signals": 303, "taken": 303, "skip_kill": 0, "skip_lots": 0, "gov_block": 0, "gov_cut": 0, "gov_full": 0, "final_equity": 111686.009661, "peak_equity": 115859.18149075001, "killed_days": 0, "use_gov": false, "full_risk": 0.0075, "cut_risk": 0.003, "chassis": "btc-h4-break6-r15-c17"}`

## 20C — gov R15 0.75→0.30 block@8% (gov=ON)

**Decision: REJECT**

- Chassis: `btc-h4-break6-r15-c17+gov`
- Trades: n=71 L/S=71/0 WR=42.3% reasons={'target': 30, 'stop': 41} gov_entry_states={'full': 35, 'cut': 36}
- HO $0.00 (~$0.00/mo); Fit $5,138.05; Leave-out $0.00 (drop []); Ext measured $0.00
- Max DD 8.17%; worst Prague day 2024-02-05 -0.77%; fail-days=0; Legal=YES
- Windows: ≤60d 0/947; ≤90d cont 0/917; seq90 reset 0/155
- Final equity $105,138.05

Meta: `{"signals": 303, "taken": 71, "skip_kill": 0, "skip_lots": 0, "gov_block": 232, "gov_cut": 36, "gov_full": 35, "final_equity": 105138.048877, "peak_equity": 114485.87281675001, "killed_days": 0, "use_gov": true, "full_risk": 0.0075, "cut_risk": 0.003, "chassis": "btc-h4-break6-r15-c17+gov"}`

## Ungoverened → governed delta (critical)

| Pair | Ungov DD | Gov DD | Ungov ≤90d | Gov ≤90d | Ungov seq | Gov seq | Ungov HO$/mo | Gov HO$/mo |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 20A XAG Donchian | 12.4% | 8.5% | 77/838 | 0/827 | 60/838 | 0/322 | 867 | 0 |
| 20B BTC channel | 13.8% | 8.0% | 129/917 | 77/916 | 13/917 | 13/536 | 2,070 | 0 |
| 20C BTC R15 C17 | 12.0% | 8.2% | 0/917 | 0/917 | 0/917 | 0/155 | 669 | 0 |


## Honesty / mandate read

- **Governor works on DD:** XAG 12.4%→8.5%, BTC channel 13.8%→8.0%, BTC R15 12.0%→8.2% (all ≤10%).
- **Window preservation:** only **20B channel+gov** keeps ≤90d passes (77 cont / 13 seq). XAG+gov and R15+gov go to **0**.
- **Fatal HO gap:** under sticky block (no new entries until dd < 5% after ≥8%), **20B gov takes zero HO and zero Ext trades** (HO=$0/mo). Challenge windows that count are **Fit-era (2024)** equity-path windows, not a HO-period vehicle you can arm tomorrow.
- **ACCEPT bar fails:** mandate needs HO>0 + leave-out remaining HO>0 for ACCEPT. Here HO=0 → **CONDITIONAL** at best.
- **XAG C19B+gov:** DD legal but governor blocks 65 signals; Fit −$5.1k; **0** windows → REJECT.
- Live C4/drip untouched. Gold not packaged. Do not deploy.

## Live

Research only — C4 / drip / FREEZE / MetaAPI / live VM **untouched**.
Gold not packaged. Do not deploy.

