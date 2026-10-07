# Candidate 39 Results — MUTEX XAG Donchian soft primary + US100 NR7

**NO — MUTEX XAG soft primary + US100 NR7 does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows (mutex did not restore HO windows).

**XAG window survival (39A→39C mutex):** 39A HO≤90d=8 → 39C mutex HO≤90d=0 (seq HO 0→0) | windows_survived=N

**US100 data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/usatechidxusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `5d833b201f3374797bd64ae50e2937af21affc1a52ef33a2119d316d35fdd3af` end `2026-09-01 23:58:00+00:00`
**XAG data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c` end `2026-09-01 23:59:00+00:00`
**Measured (ET):** 2026-10-07 12:46 ET

## ASSUMPTIONS

| Item | Value |
|---|---|
| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** (ASSUMPTION — C19B/C21B) |
| US100 costs | spread 1 / comm 0 / contract 1 (catalogue) |
| XAG risks | **2.50% / 1.25% / 0.75%** (full C21B) |
| US100 risks | **1.00% / 0.50% / 0.25%** (when allowed to enter) |
| Soft gov | dd<5% full; 5–8% mid; ≥8% floor; never sticky-block |
| Prague day kill | −3% both sleeves |
| Max positions | **MUTEX: at most ONE account-wide** |
| Conflict | same-ts → take XAG, ignore US100; US100 open + XAG signal → wait (no force-flat) |

## Scoreboard

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Explorer out/cnt | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---|---|---|
| 39A | XAG | SOFT | 847 | 9.4% | 48/838 (8) | 60/838 (0) | N/A | -6,976 | YES | 0/1 best=6.435126039242833 | CONDITIONAL |
| 39B | US100 | SOFT | 1,931 | 1.0% | 0/732 (0) | 0/732 (0) | N/A | 10,588 | YES | 0/0 best=8.20896311077519 | REJECT |
| 39C | JOINT-MUTEX | SOFT | 2,554 | 8.0% | 100/838 (0) | 60/838 (0) | N/A | 6,131 | YES | 0/2 best=8.369220676643142 | REJECT |

### 39A — 39A XAG Donchian @2.50% soft

- trades=56 WR=53.6% L/S=44/12
- reasons={'SL': 14, 'TP': 24, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 37, 'mid': 13, 'floor': 6} by_sym={'XAG': 56}
- funnel={'gov_full': 37, 'taken': 56, 'taken_XAG': 56, 'gov_mid': 13, 'gov_floor': 6}
- HO net $8,291 (~$847/mo) | Fit $1,664 | leave-out drop ['2026-01', '2025-12'] → $-6,976
- max DD 9.40% | worst Prague day 2026-01-31 @ -2.69% | fail-days 0 | legal=True
- ≤90d 48/838 (HO-era 8) | seq 60/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=1 best_outside%=6.435126039242833 months=['2024-03', '2024-04', '2024-05'] dd=-0.09403781654124409
- sample ≤90d starts: ['2025-11-01', '2025-11-02', '2025-11-03', '2025-11-04', '2025-11-05']
- sample seq starts: ['2025-07-13', '2025-07-14', '2025-07-15', '2025-07-16', '2025-07-17']
- final equity $109,955 | chassis `xag-donchian-20d-2.50+softgov`

### 39B — 39B US100 NR7 @1% soft

- trades=21 WR=95.2% L/S=18/3
- reasons={'TP': 20, 'SL': 1} gov={'full': 21} by_sym={'US100': 21}
- funnel={'gov_full': 21, 'taken': 21, 'taken_US100': 21}
- HO net $18,903 (~$1,931/mo) | Fit $27,736 | leave-out drop ['2026-04', '2026-06'] → $10,588
- max DD 1.01% | worst Prague day 2025-02-21 @ -1.01% | fail-days 0 | legal=True
- ≤90d 0/732 (HO-era 0) | seq 0/732 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=8.20896311077519 months=['2026-04', '2026-05', '2026-06'] dd=-0.010055189436447844
- final equity $146,639 | chassis `us100-nr7-1.00+softgov`

### 39C — 39C MUTEX XAG primary + US100 NR7 soft

- trades=71 WR=62.0% L/S=57/14
- reasons={'SL': 15, 'TP': 38, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 61, 'mid': 10} by_sym={'XAG': 56, 'US100': 15}
- funnel={'gov_full': 61, 'taken': 71, 'taken_XAG': 56, 'skip_mutex_us100': 6, 'taken_US100': 15, 'gov_mid': 10}
- HO net $25,000 (~$2,554/mo) | Fit $22,192 | leave-out drop ['2026-01', '2025-12'] → $6,131
- max DD 8.00% | worst Prague day 2026-06-14 @ -2.87% | fail-days 0 | legal=True
- ≤90d 100/838 (HO-era 0) | seq 60/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=2 best_outside%=8.369220676643142 months=['2024-03', '2024-04', '2024-05'] dd=-0.0799798137151211
- sample ≤90d starts: ['2025-07-13', '2025-07-14', '2025-07-15', '2025-07-16', '2025-07-17']
- sample seq starts: ['2025-07-13', '2025-07-14', '2025-07-15', '2025-07-16', '2025-07-17']
- final equity $147,192 | chassis `xag-primary+us100nr7-MUTEX+softgov`

## Does this open a ~3mo path?

**NO — MUTEX XAG soft primary + US100 NR7 does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows (mutex did not restore HO windows).

Live C4 / drip / FREEZE / MetaAPI: **untouched**. Gold not packaged. No deploy.
