# Candidate 18 Results — ETHUSD denser-pace hunt

**NO — ETH Candidate 18 does not open a 1–3mo pass path** on the two locked books.

**Measured:** 2026-10-07 12:01:01 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**ETH data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/ethusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `bc3bf16554976b31350b5449503da50f24565c08b73bf12d035c0df21215d770`
**Data range:** 2024-01-01 → 2026-09-01 23:59:00+00:00 (no ETH dukas-ext)

## ASSUMPTIONS

| Item | Value |
|---|---|
| Account | $100,000 2-step |
| Challenge / Verification | +10% / +5% (1.10 then 1.155 continuous; seq reset 1.10 then 1.05) |
| Daily / Max DD | 5% / 10% |
| ETH contract_size | **10** (FTMO catalogue) |
| ETH spread | **1.50** price units × units (ASSUMPTION — feed has no typical_spread; C15 HF analog; BTC uses 15 @ contract 1) |
| Commission / swap | **0** / **0** (ASSUMPTION — C15 HF parity; catalogue percent commission not applied) |
| Ext | UNAVAILABLE if feed ends before 2026-09-02 |
| Books | Two locked a-priori only — not a grid |
| Gold packaging | Forbidden (Gold Strategy veto) |

## Scoreboard

| Book | Risk | HO $/mo | Fit | Leave-out | Ext | Worst day | Max DD | ≤60d | ≤90d cont | seq90 | Legal | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 18A 0.75% locked | 0.75% | -1,505 | +8,749 | -16,872 | N/A | -0.86% | 13.7% | 0/874 | 0/844 | 0/844 | NO | REJECT |
| 18A 0.50% | 0.50% | -998 | +5,845 | -11,167 | N/A | -0.57% | 9.3% | 0/874 | 0/844 | 0/844 | YES | REJECT |
| 18A 1.00% | 1.00% | -2,020 | +11,660 | -22,644 | N/A | -1.15% | 17.9% | 0/874 | 0/844 | 0/844 | NO | REJECT |
| 18B 2.60% locked | 2.60% | 667 | +6,795 | -3,985 | N/A | -2.63% | 14.5% | 0/871 | 0/841 | 0/841 | NO | REJECT |

## 18A — 0.75% locked

**Decision: REJECT**

- Chassis: `eth-h4-bb-squeeze`
- Trades: n=102 L/S=56/46 WR=32.4% reasons={'target': 33, 'stop': 69}
- HO $-14,736.29 (~$-1,505.28/mo); Fit $8,749.14; Leave-out $-16,871.70 (drop ['2026-03', '2025-12']); Ext UNAVAILABLE (ETH feed ends 2026-09-01; no dukas-ext) 
- Max DD 13.69%; worst Prague day 2026-08-18 -0.86%; fail-days=0; Legal=NO
- Windows: ≤60d 0/874; ≤90d cont 0/844; seq90 reset 0/844
- Final equity $94,012.85 (net $-5,987.15)

Meta: `{"signals": 131, "taken": 102, "skip": {"atr": 13, "bb": 105, "in_trade": 29}, "final_equity": 94012.8478349, "killed_days": 0, "n_h4": 5646, "n_squeeze": 690, "chassis": "eth-h4-bb-squeeze"}`

## 18A — 0.50%

**Decision: REJECT**

- Chassis: `eth-h4-bb-squeeze`
- Trades: n=102 L/S=56/46 WR=32.4% reasons={'target': 33, 'stop': 69}
- HO $-9,767.52 (~$-997.73/mo); Fit $5,844.59; Leave-out $-11,167.06 (drop ['2026-03', '2025-12']); Ext UNAVAILABLE (ETH feed ends 2026-09-01; no dukas-ext) 
- Max DD 9.31%; worst Prague day 2026-08-18 -0.57%; fail-days=0; Legal=YES
- Windows: ≤60d 0/874; ≤90d cont 0/844; seq90 reset 0/844
- Final equity $96,077.07 (net $-3,922.93)
- **Joint residual vs BTC C15@0.75% ($1,291/mo, DD 7.4%):** still need **$4,707/mo** from ETH (or other) to hit ~$5k/mo combined; ETH alone DD headroom 0.7%; rough joint leftover after stacking C15+ETH DDs (uncorrelated ASSUMPTION) = 0.0%

Meta: `{"signals": 131, "taken": 102, "skip": {"atr": 13, "bb": 105, "in_trade": 29}, "final_equity": 96077.07427050002, "killed_days": 0, "n_h4": 5646, "n_squeeze": 690, "chassis": "eth-h4-bb-squeeze"}`

## 18A — 1.00%

**Decision: REJECT**

- Chassis: `eth-h4-bb-squeeze`
- Trades: n=102 L/S=56/46 WR=32.4% reasons={'target': 33, 'stop': 69}
- HO $-19,771.37 (~$-2,019.60/mo); Fit $11,660.44; Leave-out $-22,643.71 (drop ['2026-03', '2025-12']); Ext UNAVAILABLE (ETH feed ends 2026-09-01; no dukas-ext) 
- Max DD 17.89%; worst Prague day 2026-08-18 -1.15%; fail-days=0; Legal=NO
- Windows: ≤60d 0/874; ≤90d cont 0/844; seq90 reset 0/844
- Final equity $91,889.07 (net $-8,110.93)

Meta: `{"signals": 131, "taken": 102, "skip": {"atr": 13, "bb": 105, "in_trade": 29}, "final_equity": 91889.07068529997, "killed_days": 0, "n_h4": 5646, "n_squeeze": 690, "chassis": "eth-h4-bb-squeeze"}`

## 18B — 2.60% locked

**Decision: REJECT**

- Chassis: `eth-donchian-20d-dual`
- Trades: n=46 L/S=24/22 WR=43.5% reasons={'TIME': 28, 'TP': 3, 'SL': 15}
- HO $6,532.32 (~$667.26/mo); Fit $6,795.40; Leave-out $-3,984.57 (drop ['2026-02', '2026-06']); Ext UNAVAILABLE (ETH feed ends 2026-09-01; no dukas-ext) 
- Max DD 14.49%; worst Prague day 2026-01-09 -2.63%; fail-days=0; Legal=NO
- Windows: ≤60d 0/871; ≤90d cont 0/841; seq90 reset 0/841
- Final equity $113,327.72 (net $13,327.72)

Meta: `{"funnel": {"no_break": 541, "signals": 46, "ignored_in_pos": 49}, "final_equity": 113327.72008400002, "killed_days": 0, "n_daily": 943, "unfinished": 0, "chassis": "eth-donchian-20d-dual", "taken": 46}`

## Joint residual (mandate math)

BTC C15@0.75% contributes ~$1,291/mo at 7.4% DD. Need ~$5,000/mo for +$15k/90d → residual ≥$3,709/mo from a second book inside leftover ~2.6% DD.

- 18A@0.75%: illegal or unusable for residual (DD 13.7%, pace $-1,505/mo).
- 18A@0.50%: DD-legal (9.3%) but **HO negative** ($-998/mo) — unusable as residual filler; leave-out also fails.
- 18A@1.00%: illegal or unusable for residual (DD 17.9%, pace $-2,020/mo).
- 18B@2.60%: HO +$667/mo but DD **14.5% illegal** — cannot sit beside C15; leave-out fails; 0 ≤90d windows.

## Live

Research only — C4 / drip / FREEZE / MetaAPI / live VM **untouched**.
Gold not packaged as primary. US100 not invented.

