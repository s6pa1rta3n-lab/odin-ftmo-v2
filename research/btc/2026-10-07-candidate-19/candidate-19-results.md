# Candidate 19 Results — XAGUSD denser-pace hunt

**NO cleared ACCEPT — XAG 19A is DD-legal at ~$766/mo but too slow / no ≤90d windows (Ext UNAVAILABLE — XAG feed ends 2026-09-01; no dukas-ext).**

**Measured:** 2026-10-07 12:03:22 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**XAG data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c`
**Data range:** 2024-01-01 → 2026-09-01 23:59:00+00:00 (no XAG dukas-ext)

## ASSUMPTIONS

| Item | Value |
|---|---|
| Account | $100,000 2-step |
| Challenge / Verification | +10% / +5% (1.10 then 1.155 continuous; seq reset 1.10 then 1.05) |
| Daily / Max DD | 5% / 10% |
| XAG contract_size | **5000** (FTMO catalogue XAG/USD) |
| XAG spread | **0.025** price units × units (ASSUMPTION — feed has no typical_spread; industry mid for XAG CFD) |
| Commission / swap | **$3/lot** / **0** (ASSUMPTION — Gold metals harness parity; catalogue percent 0.0014 not applied; swap ignored) |
| Ext | UNAVAILABLE if feed ends before 2026-09-02 |
| Books | Two locked a-priori only — not a grid |
| Gold packaging | Forbidden (Gold Strategy veto) |

## Scoreboard

| Book | Risk | HO $/mo | Fit | Leave-out | Ext | Worst day | Max DD | ≤60d | ≤90d cont | seq90 | Legal | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 19A 0.75% locked | 0.75% | 564 | +1,447 | -1,315 | N/A | -0.89% | 5.8% | 0/873 | 0/843 | 0/843 | YES | REJECT |
| 19A 0.50% | 0.50% | 374 | +1,079 | -965 | N/A | -0.60% | 3.9% | 0/873 | 0/843 | 0/843 | YES | REJECT |
| 19A 1.00% | 1.00% | 766 | +1,766 | -1,599 | N/A | -1.18% | 7.7% | 0/873 | 0/843 | 0/843 | YES | REJECT |
| 19B 2.50% TP1R locked | 2.50% | 867 | +6,370 | -7,270 | N/A | -2.70% | 12.4% | 34/868 | 77/838 | 60/838 | NO | REJECT |

## 19A — 0.75% locked

**Decision: REJECT**

- Chassis: `xag-h4-bb-squeeze`
- Trades: n=83 L/S=47/36 WR=39.8% reasons={'stop': 49, 'target': 33, 'gap-stop': 1}
- HO $5,522.53 (~$564.11/mo); Fit $1,447.19; Leave-out $-1,315.30 (drop ['2026-07', '2025-12']); Ext UNAVAILABLE (XAG feed ends 2026-09-01; no dukas-ext) 
- Max DD 5.81%; worst Prague day 2024-10-17 -0.89%; fail-days=0; Legal=YES
- Windows: ≤60d 0/873; ≤90d cont 0/843; seq90 reset 0/843
- Final equity $106,969.73 (net $6,969.73)
- **Joint residual vs BTC C15@0.75% ($1,291/mo, DD 7.4%):** still need **$3,145/mo** from XAG (or other) to hit ~$5k/mo combined; XAG alone DD headroom 4.2%; rough joint leftover after stacking C15+XAG DDs (uncorrelated ASSUMPTION) = 0.0%

Meta: `{"signals": 119, "taken": 83, "skip": {"atr": 13, "bb": 105, "in_trade": 36}, "final_equity": 106969.72669999996, "killed_days": 0, "n_h4": 4414, "n_squeeze": 583, "chassis": "xag-h4-bb-squeeze"}`

## 19A — 0.50%

**Decision: REJECT**

- Chassis: `xag-h4-bb-squeeze`
- Trades: n=83 L/S=47/36 WR=39.8% reasons={'stop': 49, 'target': 33, 'gap-stop': 1}
- HO $3,659.70 (~$373.83/mo); Fit $1,078.86; Leave-out $-965.12 (drop ['2026-07', '2025-12']); Ext UNAVAILABLE (XAG feed ends 2026-09-01; no dukas-ext) 
- Max DD 3.91%; worst Prague day 2024-10-17 -0.60%; fail-days=0; Legal=YES
- Windows: ≤60d 0/873; ≤90d cont 0/843; seq90 reset 0/843
- Final equity $104,738.56 (net $4,738.56)
- **Joint residual vs BTC C15@0.75% ($1,291/mo, DD 7.4%):** still need **$3,335/mo** from XAG (or other) to hit ~$5k/mo combined; XAG alone DD headroom 6.1%; rough joint leftover after stacking C15+XAG DDs (uncorrelated ASSUMPTION) = 0.0%

Meta: `{"signals": 119, "taken": 83, "skip": {"atr": 13, "bb": 105, "in_trade": 36}, "final_equity": 104738.56174999992, "killed_days": 0, "n_h4": 4414, "n_squeeze": 583, "chassis": "xag-h4-bb-squeeze"}`

## 19A — 1.00%

**Decision: REJECT**

- Chassis: `xag-h4-bb-squeeze`
- Trades: n=83 L/S=47/36 WR=39.8% reasons={'stop': 49, 'target': 33, 'gap-stop': 1}
- HO $7,499.47 (~$766.05/mo); Fit $1,766.20; Leave-out $-1,598.64 (drop ['2026-07', '2025-12']); Ext UNAVAILABLE (XAG feed ends 2026-09-01; no dukas-ext) 
- Max DD 7.70%; worst Prague day 2024-10-17 -1.18%; fail-days=0; Legal=YES
- Windows: ≤60d 0/873; ≤90d cont 0/843; seq90 reset 0/843
- Final equity $109,265.67 (net $9,265.67)
- **Joint residual vs BTC C15@0.75% ($1,291/mo, DD 7.4%):** still need **$2,943/mo** from XAG (or other) to hit ~$5k/mo combined; XAG alone DD headroom 2.3%; rough joint leftover after stacking C15+XAG DDs (uncorrelated ASSUMPTION) = 0.0%

Meta: `{"signals": 119, "taken": 83, "skip": {"atr": 13, "bb": 105, "in_trade": 36}, "final_equity": 109265.66729999991, "killed_days": 0, "n_h4": 4414, "n_squeeze": 583, "chassis": "xag-h4-bb-squeeze"}`

## 19B — 2.50% TP1R locked

**Decision: REJECT**

- Chassis: `xag-donchian-20d-dual-1r`
- Trades: n=56 L/S=44/12 WR=53.6% reasons={'SL': 14, 'TP': 24, 'TIME': 17, 'SL_OPEN': 1}
- HO $8,486.64 (~$866.89/mo); Fit $6,369.76; Leave-out $-7,269.73 (drop ['2026-01', '2025-12']); Ext UNAVAILABLE (XAG feed ends 2026-09-01; no dukas-ext) 
- Max DD 12.36%; worst Prague day 2026-06-14 -2.70%; fail-days=0; Legal=NO
- Windows: ≤60d 34/868; ≤90d cont 77/838; seq90 reset 60/838
- Final equity $114,856.40 (net $14,856.40)

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
| 2025-07-25 | 2025-10-22 | $94,309 | 1.157 | 1.025 | -2.52% |
| 2025-07-26 | 2025-10-23 | $94,309 | 1.157 | 1.025 | -2.52% |
| 2025-07-27 | 2025-10-24 | $94,309 | 1.157 | 1.025 | -2.52% |

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
| 2025-07-25 | 2025-09-27 | 2025-10-10 | 78 |
| 2025-07-26 | 2025-09-27 | 2025-10-10 | 77 |
| 2025-07-27 | 2025-09-27 | 2025-10-10 | 76 |

Meta: `{"funnel": {"no_break": 447, "signals": 56, "ignored_in_pos": 47}, "final_equity": 114856.40059999995, "killed_days": 0, "n_daily": 833, "unfinished": 0, "chassis": "xag-donchian-20d-dual-1r", "taken": 56}`

## Joint residual (mandate math)

BTC C15@0.75% contributes ~$1,291/mo at 7.4% DD. Need ~$5,000/mo for +$15k/90d → residual ≥$3,709/mo from a second book inside leftover ~2.6% DD. XAG is that candidate sleeve.

- 19A@0.75%: $564/mo, DD 5.8%, still-need $3,145/mo, does NOT fill residual alone.
- 19A@0.50%: $374/mo, DD 3.9%, still-need $3,335/mo, does NOT fill residual alone.
- 19A@1.00%: $766/mo, DD 7.7%, still-need $2,943/mo, does NOT fill residual alone.
- 19B@2.50%: illegal or unusable for residual (DD 12.4%, pace $867/mo).

## Live

Research only — C4 / drip / FREEZE / MetaAPI / live VM **untouched**.
Gold not packaged as primary. US100 not invented. Do not package Gold.

