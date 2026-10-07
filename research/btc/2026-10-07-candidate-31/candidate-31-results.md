# Candidate 31 Results — US100 NR7 + JPN225 Keltner55 (Explorer re-chassis)

**NO — US100 NR7 + JPN225 Keltner55 does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

**Index sleeve ran:** `JPN225` (USE_FX=True)
**US100 data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/usatechidxusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `5d833b201f3374797bd64ae50e2937af21affc1a52ef33a2119d316d35fdd3af` end `2026-09-01 23:58:00+00:00`
**Index data end:** `2026-09-01 23:59:00+00:00` sha `b7e9a85045eba935ead5812f13d461ba919f60d8220581671bfaf0b66ab82a6e`
**USDJPY FX:** `/workspace/strategy-explorer/pr36/dukascopy-raw/usdjpy-m1-bid-2024-01-01-2026-09-02.csv` sha256 `ed7c8db716fe2e4a572dfe15d21157944427086636d1b97929bbdd49097cdcca` (mid for JPY→USD)
**Measured (ET):** 2026-10-07 12:36 ET

## ASSUMPTIONS

| Item | Value |
|---|---|
| JP225.cash contractSize | **10** (catalogue) |
| JP225.cash commission | **0** (catalogue) |
| JP225.cash spread | **8.0** pts (**ASSUMPTION** — feed missing) |
| JPY→USD | USDJPY M1 mid at entry (size) and exit (PnL) |
| US100 costs | spread 1 / comm 0 / contract 1 (catalogue) |
| Soft gov | dd<5% full; 5–8% half; ≥8% quarter; never sticky-block |
| Prague day kill | −3% both sleeves |
| Max positions | one per sleeve (two simultaneous OK) |

## Scoreboard

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Explorer out/cnt | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---|---|---|
| 31A | US100 | SOFT | 1,931 | 1.0% | 0/732 (0) | 0/732 (0) | N/A | 10,588 | YES | 0/0 best=8.20896311077519 | REJECT |
| 31B | JPN225 | SOFT | 484 | 9.3% | 0/845 (0) | 0/845 (0) | N/A | -1,438 | YES | 0/0 best=10.122251667122018 | REJECT |
| 31C | JOINT | OFF | 3,058 | 10.1% | 0/845 (0) | 0/845 (0) | N/A | 8,772 | NO | 0/0 best=14.849307386679378 | REJECT |
| 31D | JOINT | SOFT | 2,921 | 8.8% | 0/845 (0) | 0/845 (0) | N/A | 8,380 | YES | 0/0 best=14.850405972462898 | REJECT |

### 31A — 31A US100 NR7 @1% soft

- trades=21 WR=95.2% L/S=18/3
- reasons={'TP': 20, 'SL': 1} gov={'full': 21} by_sym={'US100': 21}
- HO net $18,903 (~$1,931/mo) | Fit $27,736 | leave-out drop ['2026-04', '2026-06'] → $10,588
- max DD 1.01% | worst Prague day 2025-02-21 @ -1.01% | fail-days 0 | legal=True
- ≤90d 0/732 (HO-era 0) | seq 0/732 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=8.20896311077519 months=['2026-04', '2026-05', '2026-06'] dd=-0.010055189436447844
- final equity $146,639 | chassis `us100-nr7-1.00+softgov`

### 31B — 31B JPN225 Keltner55 @2.50% soft

- trades=47 WR=53.2% L/S=34/13
- reasons={'TIME': 34, 'SL': 9, 'TP': 3, 'SL_OPEN': 1} gov={'full': 27, 'mid': 11, 'floor': 9} by_sym={'JPN225': 47}
- HO net $4,734 (~$484/mo) | Fit $7,155 | leave-out drop ['2026-01', '2026-04'] → $-1,438
- max DD 9.32% | worst Prague day 2024-10-31 @ -2.66% | fail-days 0 | legal=True
- ≤90d 0/845 (HO-era 0) | seq 0/845 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=10.122251667122018 months=['2024-06', '2024-07', '2024-08'] dd=-0.09320186527795633
- final equity $111,889 | chassis `jpn225-keltner55-2.50+softgov`

### 31C — 31C joint ungoverened

- trades=68 WR=66.2% L/S=52/16
- reasons={'TIME': 34, 'TP': 23, 'SL': 10, 'SL_OPEN': 1} gov={'n/a': 68} by_sym={'JPN225': 47, 'US100': 21}
- HO net $29,942 (~$3,058/mo) | Fit $41,047 | leave-out drop ['2026-01', '2026-04'] → $8,772
- max DD 10.13% | worst Prague day 2024-10-31 @ -2.66% | fail-days 0 | legal=False
- ≤90d 0/845 (HO-era 0) | seq 0/845 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=14.849307386679378 months=['2026-04', '2026-05', '2026-06'] dd=-0.1013134720648574
- final equity $170,989 | chassis `us100nr7+jpn225-joint-ungov`

### 31D — 31D joint + soft gov (verdict)

- trades=68 WR=66.2% L/S=52/16
- reasons={'TIME': 34, 'TP': 23, 'SL': 10, 'SL_OPEN': 1} gov={'full': 58, 'mid': 4, 'floor': 6} by_sym={'JPN225': 47, 'US100': 21}
- HO net $28,600 (~$2,921/mo) | Fit $34,720 | leave-out drop ['2026-01', '2026-04'] → $8,380
- max DD 8.76% | worst Prague day 2024-10-31 @ -2.66% | fail-days 0 | legal=True
- ≤90d 0/845 (HO-era 0) | seq 0/845 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=14.850405972462898 months=['2026-04', '2026-05', '2026-06'] dd=-0.08763890424094367
- final equity $163,320 | chassis `us100nr7+jpn225-joint+softgov`

## Does this open a ~3mo path?

**NO — US100 NR7 + JPN225 Keltner55 does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

Live C4 / drip / FREEZE / MetaAPI: **untouched**. Gold not packaged. No deploy.
