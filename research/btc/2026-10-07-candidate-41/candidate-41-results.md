# Candidate 41 Results — US100 NR7 @1% + BTC C15 H4 BB squeeze soft (no XAG)

**NO — US100 NR7 + BTC C15 soft joint (no XAG) does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

**Window creation (alone→joint):** 41A HO≤90d=0 | 41B HO≤90d=0 → 41D joint HO≤90d=0 (seq HO 0+0→0)

**US100 data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/usatechidxusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `5d833b201f3374797bd64ae50e2937af21affc1a52ef33a2119d316d35fdd3af` end `2026-09-01 23:58:00+00:00`
**BTC data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/btcusd-m1-bid-2024-01-01-2026-09-02.csv` + dukas-ext sha256 main `437a2c36f6ac9da5684533f9cde17e029f177abacab30579cd2c30e625443829` end `2026-10-07 11:34:00+00:00`
**Measured (ET):** 2026-10-07 12:50 ET

## ASSUMPTIONS

| Item | Value |
|---|---|
| US100 costs | spread 1 / comm 0 / contract 1 (catalogue) |
| BTC costs | spread **15** / comm 0 / contract 1 (C15 model) |
| US100 risks | **1.00% / 0.50% / 0.25%** |
| BTC risks | **0.75% / 0.40% / 0.20%** (exact C15 full) |
| Soft gov | dd<5% full; 5–8% mid; ≥8% floor; never sticky-block |
| Prague day kill | −3% both sleeves |
| Max positions | one per sleeve (two simultaneous OK) |
| XAG | **excluded** (C35/C37/C39 closed) |
| Gold | not packaged |

## Scoreboard

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Explorer out/cnt | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---|---|---|
| 41A | US100 | SOFT | 1,931 | 1.0% | 0/732 (0) | 0/732 (0) | N/A | 10,588 | YES | 0/0 best=8.20896311077519 | REJECT |
| 41B | BTC | SOFT | 1,253 | 6.8% | 0/879 (0) | 0/879 (0) | -1,775 | 2,917 | YES | 0/0 best=6.816463414954943 | REJECT |
| 41C | JOINT | OFF | 3,820 | 5.2% | 0/879 (0) | 0/879 (0) | -2,670 | 19,250 | YES | 0/0 best=12.63071552085151 | REJECT |
| 41D | JOINT | SOFT | 3,766 | 5.2% | 0/879 (0) | 0/879 (0) | -2,634 | 18,963 | YES | 0/0 best=12.63071552085151 | REJECT |

### 41A — 41A US100 NR7 @1% soft

- trades=21 WR=95.2% L/S=18/3
- reasons={'TP': 20, 'SL': 1} gov={'full': 21} by_sym={'US100': 21}
- HO net $18,903 (~$1,931/mo) | Fit $27,736 | leave-out drop ['2026-04', '2026-06'] → $10,588
- max DD 1.01% | worst Prague day 2025-02-21 @ -1.01% | fail-days 0 | legal=True
- ≤90d 0/732 (HO-era 0) | seq 0/732 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=8.20896311077519 months=['2026-04', '2026-05', '2026-06'] dd=-0.010055189436447844
- final equity $146,639 | chassis `us100-nr7-1.00+softgov`

### 41B — 41B BTC C15 @0.75% soft

- trades=114 WR=38.6% L/S=56/58
- reasons={'stop': 67, 'target': 43, 'gap-stop': 3, 'gap-target': 1} gov={'full': 103, 'mid': 11} by_sym={'BTC': 114}
- HO net $12,264 (~$1,253/mo) | Fit $-2,031 | leave-out drop ['2026-06', '2026-08'] → $2,917
- max DD 6.76% | worst Prague day 2026-09-28 @ -1.54% | fail-days 0 | legal=True
- ≤90d 0/879 (HO-era 0) | seq 0/879 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=6.816463414954943 months=['2024-06', '2024-07', '2024-08'] dd=-0.0675610628374624
- final equity $108,459 | chassis `btc-h4-bb-squeeze-0.75+softgov`

### 41C — 41C joint ungoverened

- trades=135 WR=47.4% L/S=74/61
- reasons={'stop': 67, 'TP': 20, 'target': 43, 'SL': 1, 'gap-stop': 3, 'gap-target': 1} gov={'n/a': 135} by_sym={'BTC': 114, 'US100': 21}
- HO net $37,400 (~$3,820/mo) | Fit $28,361 | leave-out drop ['2026-06', '2026-03'] → $19,250
- max DD 5.22% | worst Prague day 2026-09-28 @ -1.53% | fail-days 0 | legal=True
- ≤90d 0/879 (HO-era 0) | seq 0/879 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=12.63071552085151 months=['2024-06', '2024-07', '2024-08'] dd=-0.0522399756619007
- final equity $163,090 | chassis `us100nr7+btc-joint-ungov`

### 41D — 41D joint + soft gov (verdict)

- trades=135 WR=47.4% L/S=74/61
- reasons={'stop': 67, 'TP': 20, 'target': 43, 'SL': 1, 'gap-stop': 3, 'gap-target': 1} gov={'full': 133, 'mid': 2} by_sym={'BTC': 114, 'US100': 21}
- HO net $36,873 (~$3,766/mo) | Fit $26,599 | leave-out drop ['2026-06', '2026-03'] → $18,963
- max DD 5.22% | worst Prague day 2026-09-28 @ -1.53% | fail-days 0 | legal=True
- ≤90d 0/879 (HO-era 0) | seq 0/879 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=12.63071552085151 months=['2024-06', '2024-07', '2024-08'] dd=-0.0522399756619007
- final equity $160,838 | chassis `us100nr7+btc-joint+softgov`

## Does this open a ~3mo path?

**NO — US100 NR7 + BTC C15 soft joint (no XAG) does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

Live C4 / drip / FREEZE / MetaAPI: **untouched**. Gold not packaged. XAG excluded. No deploy.
