# Candidate 29 Results — C15 BTC + C21B XAG soft joint residual stack

**NO — joint C15 BTC + C21B XAG soft does not clear C17 residual / deployable ~3mo path.** 29C: DD 6.6% legal=True, HO ~$1,261/mo, ≤90d HO-era 0, leave-out $+2,461.

**Measured:** 2026-10-07 12:31:28 EDT
**Live engines:** not modified. C4/drip/FREEZE/MetaAPI untouched.
**BTC data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/btcusd-m1-bid-2024-01-01-2026-09-02.csv` + dukas-ext sha256 main `437a2c36f6ac9da5684533f9cde17e029f177abacab30579cd2c30e625443829` end `2026-10-07 11:34:00+00:00`
**XAG data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c` end `2026-09-01 23:59:00+00:00`

## C17 residual check

| Item | Value |
|---|---|
| C17 BTC@0.75% solo pace | ~$1,291/mo DD 7.4% |
| C17 residual gap | ≥~$3,709/mo in ~2.6% DD headroom |
| 29C joint HO pace | $1,261/mo |
| 29C max DD (shared) | 6.56% |
| 29C ≤90d HO-era | 0 cont / 0 seq |
| Clears C17 residual to ACCEPT? | NO |

## ASSUMPTIONS

| Item | Value |
|---|---|
| Account | $100,000 2-step |
| Challenge / Verification | +10% / +5% |
| Daily / Max DD | 5% / 10% |
| Soft gov bands | **<5%** full / **5–8%** mid / **≥8%** floor (never block) |
| BTC risk shares | **0.40% / 0.20% / 0.10%** |
| XAG risk shares | **1.25% / 0.625% / 0.375%** |
| BTC costs | spread **15**, commission **0**, contract **1** |
| XAG costs | contract **5000**, spread **0.025**, commission **$3/lot** (**ASSUMPTION**) |
| Shared equity | one book, one peak DD |
| Max positions | one per sleeve (two simultaneous OK) |
| Gold packaging | Forbidden |

## Scoreboard

| Book | Symbol | Gov | Full/Mid/Floor | HO $/mo | Leave-out | Ext | Worst day | Max DD | ≤90d (HO-era) | seq90 (HO-era) | Legal | Decision |
|---|---|---|---|---:|---:|---|---:|---:|---:|---:|---|---|
| 29A soft 0.40→0.20→0.10 | BTC | SOFT | 0.40/0.20/0.10% | 672 | +1,655 | -916 | -0.82% | 4.0% | 0/879 (0) | 0/879 (0) | YES | REJECT |
| 29B soft 1.25→0.625→0.375 | XAG | SOFT | 1.25/0.62/0.38% | 501 | -3,144 | N/A | -1.37% | 5.6% | 0/838 (0) | 0/838 (0) | YES | REJECT |
| 29C soft joint BTC0.40+XAG1.25 | JOINT | SOFT | BTC 0.40/0.20/0.10 + XAG 1.25/0.625/0.375 | 1,261 | +2,461 | -970 | -1.69% | 6.6% | 0/879 (0) | 0/879 (0) | YES | REJECT |

## 29A — soft 0.40→0.20→0.10 (gov=SOFT)

**Decision: REJECT**

- Chassis: `btc-h4-bb-squeeze-0.40+softgov`
- Trades: n=114 L/S=56/58 WR=38.6% reasons={'stop': 67, 'target': 43, 'gap-stop': 3, 'gap-target': 1} gov={'full': 114} by_sym={'BTC': 114}
- HO $6,575.75 (~$671.70/mo); Fit $329.83; Leave-out $1,655.01 (drop ['2026-06', '2026-08']); Ext measured $-916.07
- Max DD 4.03%; peak eq $106,905.58; worst Prague day 2024-04-01 -0.82%; fail-days=0; Legal=YES
- Windows: ≤60d 0/909; ≤90d cont 0/879 (HO-era starts 0); seq90 reset 0/879 (HO-era 0)
- Final equity $105,989.51

Meta: `{"funnel": {"gov_full": 114, "taken": 114, "taken_BTC": 114}, "final_equity": 105989.50924700001, "peak_equity": 106905.576957, "killed_days": 0, "chassis": "btc-h4-bb-squeeze-0.40+softgov", "taken": 114, "use_gov": true, "symbol": "BTC", "n_signals_in": 114, "btc_full": 0.004, "xag_full": 0.0125, "max_dd_path": 0.09528452600837867}`

## 29B — soft 1.25→0.625→0.375 (gov=SOFT)

**Decision: REJECT**

- Chassis: `xag-donchian-20d-1.25+softgov`
- Trades: n=56 L/S=44/12 WR=53.6% reasons={'SL': 14, 'TP': 24, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 51, 'mid': 5} by_sym={'XAG': 56}
- HO $4,901.15 (~$500.64/mo); Fit $1,854.16; Leave-out $-3,143.86 (drop ['2026-01', '2025-12']); Ext UNAVAILABLE (XAG feed ends 2026-09-01; no dukas-ext) 
- Max DD 5.63%; peak eq $109,929.77; worst Prague day 2026-03-04 -1.37%; fail-days=0; Legal=YES
- Windows: ≤60d 0/868; ≤90d cont 0/838 (HO-era starts 0); seq90 reset 0/838 (HO-era 0)
- Final equity $106,755.31

Meta: `{"funnel": {"gov_full": 51, "taken": 56, "taken_XAG": 56, "gov_mid": 5}, "final_equity": 106755.31000000001, "peak_equity": 109929.76999999999, "killed_days": 0, "chassis": "xag-donchian-20d-1.25+softgov", "taken": 56, "use_gov": true, "symbol": "XAG", "n_signals_in": 56, "btc_full": 0.004, "xag_full": 0.0125, "max_dd_path": 0.12547820303817614}`

## 29C — soft joint BTC0.40+XAG1.25 (gov=SOFT)

**Decision: REJECT**

- Chassis: `btc0.40+xag1.25-joint+softgov`
- Trades: n=170 L/S=100/70 WR=43.5% reasons={'stop': 67, 'SL': 14, 'TP': 24, 'TIME': 17, 'target': 43, 'gap-stop': 3, 'gap-target': 1, 'SL_OPEN': 1} gov={'full': 138, 'mid': 32} by_sym={'BTC': 114, 'XAG': 56}
- HO $12,344.17 (~$1,260.93/mo); Fit $1,109.09; Leave-out $2,460.53 (drop ['2026-01', '2026-08']); Ext measured $-969.66
- Max DD 6.56%; peak eq $113,569.24; worst Prague day 2024-05-10 -1.69%; fail-days=0; Legal=YES
- Windows: ≤60d 0/909; ≤90d cont 0/879 (HO-era starts 0); seq90 reset 0/879 (HO-era 0)
- Final equity $112,483.60

Meta: `{"funnel": {"gov_full": 138, "taken": 170, "taken_BTC": 114, "taken_XAG": 56, "gov_mid": 32}, "final_equity": 112483.59947899998, "peak_equity": 113569.23575099997, "killed_days": 0, "chassis": "btc0.40+xag1.25-joint+softgov", "taken": 170, "use_gov": true, "symbol": "JOINT", "n_signals_in": 170, "btc_full": 0.004, "xag_full": 0.0125, "max_dd_path": 0.15526286793599986}`

## Live

Research only — C4 / drip / FREEZE / MetaAPI / live VM **untouched**.
Gold not packaged. Do not deploy.

