# Candidate 34 Results — US100 NR7 + USA30 Keltner55 (Explorer re-chassis)

**NO — US100 NR7 + USA30 Keltner55 does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

**Index sleeve ran:** `USA30` (USE_FX=False)
**US100 data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/usatechidxusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `5d833b201f3374797bd64ae50e2937af21affc1a52ef33a2119d316d35fdd3af` end `2026-09-01 23:58:00+00:00`
**Index data end:** `2026-09-01 23:59:00+00:00` sha `968d27f1eb1ea5e8df4fb138a077ec73be4d478238c4ad938cb021ec3b84746a`
**Measured (ET):** 2026-10-07 12:40 ET

## ASSUMPTIONS

| Item | Value |
|---|---|
| USA30.cash contractSize | **1** (C22 / catalogue path) |
| USA30.cash commission | **0** |
| USA30.cash spread | **2.5** pts (**ASSUMPTION** from C22) |
| FX | N/A (USA30 USD-quoted; no JPY conversion) |
| US100 costs | spread 1 / comm 0 / contract 1 (catalogue) |
| Soft gov | dd<5% full; 5–8% half; ≥8% quarter; never sticky-block |
| Prague day kill | −3% both sleeves |
| Max positions | one per sleeve (two simultaneous OK) |

## Scoreboard

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Explorer out/cnt | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---|---|---|
| 34A | US100 | SOFT | 1,931 | 1.0% | 0/732 (0) | 0/732 (0) | N/A | 10,588 | YES | 0/0 best=8.20896311077519 | REJECT |
| 34B | USA30 | SOFT | -272 | 9.2% | 0/836 (0) | 0/836 (0) | N/A | -3,856 | YES | 0/0 best=8.161644290260185 | REJECT |
| 34C | JOINT | OFF | 972 | 8.9% | 0/836 (0) | 0/836 (0) | N/A | -2,658 | YES | 0/0 best=12.5106192327324 | REJECT |
| 34D | JOINT | SOFT | 675 | 7.4% | 0/836 (0) | 0/836 (0) | N/A | -1,517 | YES | 0/0 best=12.5106192327324 | REJECT |

### 34A — 34A US100 NR7 @1% soft

- trades=21 WR=95.2% L/S=18/3
- reasons={'TP': 20, 'SL': 1} gov={'full': 21} by_sym={'US100': 21}
- HO net $18,903 (~$1,931/mo) | Fit $27,736 | leave-out drop ['2026-04', '2026-06'] → $10,588
- max DD 1.01% | worst Prague day 2025-02-21 @ -1.01% | fail-days 0 | legal=True
- ≤90d 0/732 (HO-era 0) | seq 0/732 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=8.20896311077519 months=['2026-04', '2026-05', '2026-06'] dd=-0.010055189436447844
- final equity $146,639 | chassis `us100-nr7-1.00+softgov`

### 34B — 34B USA30 Keltner55 @2.50% soft

- trades=59 WR=50.8% L/S=39/20
- reasons={'TIME': 45, 'SL': 11, 'TP': 3} gov={'full': 31, 'mid': 11, 'floor': 17} by_sym={'USA30': 59}
- HO net $-2,663 (~$-272/mo) | Fit $8,184 | leave-out drop ['2026-03', '2026-01'] → $-3,856
- max DD 9.20% | worst Prague day 2024-04-03 @ -2.51% | fail-days 0 | legal=True
- ≤90d 0/836 (HO-era 0) | seq 0/836 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=8.161644290260185 months=['2025-03', '2025-04', '2025-05'] dd=-0.09202197774613667
- final equity $105,521 | chassis `usa30-keltner55-2.50+softgov`

### 34C — 34C joint ungoverened

- trades=80 WR=62.5% L/S=57/23
- reasons={'TIME': 45, 'SL': 12, 'TP': 23} gov={'n/a': 80} by_sym={'USA30': 59, 'US100': 21}
- HO net $9,511 (~$972/mo) | Fit $38,389 | leave-out drop ['2026-03', '2026-01'] → $-2,658
- max DD 8.89% | worst Prague day 2024-11-07 @ -2.51% | fail-days 0 | legal=True
- ≤90d 0/836 (HO-era 0) | seq 0/836 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=12.5106192327324 months=['2025-03', '2025-04', '2025-05'] dd=-0.08886495210292308
- final equity $147,900 | chassis `us100nr7+usa30-joint-ungov`

### 34D — 34D joint + soft gov (verdict)

- trades=80 WR=62.5% L/S=57/23
- reasons={'TIME': 45, 'SL': 12, 'TP': 23} gov={'full': 63, 'mid': 17} by_sym={'USA30': 59, 'US100': 21}
- HO net $6,608 (~$675/mo) | Fit $37,964 | leave-out drop ['2026-03', '2026-05'] → $-1,517
- max DD 7.43% | worst Prague day 2024-11-07 @ -2.51% | fail-days 0 | legal=True
- ≤90d 0/836 (HO-era 0) | seq 0/836 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=12.5106192327324 months=['2025-03', '2025-04', '2025-05'] dd=-0.07432528314700199
- final equity $144,571 | chassis `us100nr7+usa30-joint+softgov`

## Does this open a ~3mo path?

**NO — US100 NR7 + USA30 Keltner55 does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

Live C4 / drip / FREEZE / MetaAPI: **untouched**. Gold not packaged. No deploy.
