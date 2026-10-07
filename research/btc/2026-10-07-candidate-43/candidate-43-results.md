# Candidate 43 Results — XAG soft PRIMARY + JPN225 fixed satellite (no US100 / no Gold)

**CONDITIONAL — XAG soft + JPN fixed satellite legal DD + windows, not ACCEPT** via 43D (43D joint XAG soft + JPN 0.25%): max DD 9.2%, ≤90d HO-era 8 (windows_survived=Y vs C42 wipe-risk), HO ~$938/mo, leave-out still FAIL ($-6,937 vs 43A $-6,976). 43C leave worse ($-9,019); 43D leave ≈43A ($-6,937). No deploy.

**XAG window survival (43A→joint):** 43A HO≤90d=8 leave=-6976 → 43C HO≤90d=8 DD=9.1% leave=-9019 | 43D HO≤90d=8 DD=9.2% leave=-6937 | windows_survived=Y

**XAG data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c` end `2026-09-01 23:59:00+00:00`
**JPN225 data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/jpnidxjpy-m1-bid-2024-01-01-2026-09-02.csv` sha256 `b7e9a85045eba935ead5812f13d461ba919f60d8220581671bfaf0b66ab82a6e` end `2026-09-01 23:59:00+00:00`
**USDJPY FX:** `/workspace/strategy-explorer/pr36/dukascopy-raw/usdjpy-m1-bid-2024-01-01-2026-09-02.csv` sha256 `ed7c8db716fe2e4a572dfe15d21157944427086636d1b97929bbdd49097cdcca` (mid for JPY→USD)
**Measured (ET):** 2026-10-07 13:03 ET

## ASSUMPTIONS

| Item | Value |
|---|---|
| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** (ASSUMPTION — C19B/C21B) |
| XAG risks | **2.50% / 1.25% / 0.75%** (full C21B) |
| JPN225 contract / spread / commission | **10** / **8.0 ASSUMPTION** / **0** (catalogue JP225.cash) |
| JPN225 risks | **FIXED 0.50% (43B/C) or 0.25% (43D/E)** — no soft ladder |
| JPY→USD | USDJPY M1 mid at entry (size) and exit (PnL) |
| Soft gov | dd<5% full; 5–8% mid; ≥8% floor; never sticky-block |
| Prague day kill | −3% both sleeves |
| Max positions | one per sleeve (two simultaneous OK) |
| US100 NR7 | **excluded** |
| Gold | not packaged |

## Scoreboard

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Explorer out/cnt | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---|---|---|
| 43A | XAG | SOFT | 847 | 9.4% | 48/838 (8) | 60/838 (0) | N/A | -6,976 | YES | 0/1 best=6.435126039242833 | CONDITIONAL |
| 43B | JPN225 | OFF | 119 | 3.0% | 0/845 (0) | 0/845 (0) | N/A | -511 | YES | 0/0 best=1.9771132286865 | REJECT |
| 43C | JOINT | SOFT | 907 | 9.1% | 48/857 (8) | 60/857 (0) | N/A | -9,019 | YES | 0/2 best=6.91615863532522 | CONDITIONAL |
| 43D | JOINT | SOFT | 938 | 9.2% | 48/857 (8) | 60/857 (0) | N/A | -6,937 | YES | 0/2 best=6.69592698242496 | CONDITIONAL |

### 43A — 43A XAG Donchian @2.50% soft

- trades=56 WR=53.6% L/S=44/12
- reasons={'SL': 14, 'TP': 24, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 37, 'mid': 13, 'floor': 6} by_sym={'XAG': 56}
- HO net $8,291 (~$847/mo) | Fit $1,664 | leave-out drop ['2026-01', '2025-12'] → $-6,976
- max DD 9.40% | worst Prague day 2026-01-31 @ -2.69% | fail-days 0 | legal=True
- ≤90d 48/838 (HO-era 8) | seq 60/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=1 best_outside%=6.435126039242833 months=['2024-03', '2024-04', '2024-05'] dd=-0.09403781654124409
- sample ≤90d starts: ['2025-11-01', '2025-11-02', '2025-11-03', '2025-11-04', '2025-11-05']
- sample seq starts: ['2025-07-13', '2025-07-14', '2025-07-15', '2025-07-16', '2025-07-17']
- final equity $109,955 | chassis `xag-donchian-20d-2.50+softgov`

### 43B — 43B JPN225 Keltner FIXED 0.50%

- trades=47 WR=53.2% L/S=34/13
- reasons={'TIME': 34, 'SL': 9, 'TP': 3, 'SL_OPEN': 1} gov={'fixed': 47} by_sym={'JPN225': 47}
- HO net $1,167 (~$119/mo) | Fit $2,125 | leave-out drop ['2026-01', '2026-04'] → $-511
- max DD 3.02% | worst Prague day 2024-10-31 @ -0.53% | fail-days 0 | legal=True
- ≤90d 0/845 (HO-era 0) | seq 0/845 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=1.9771132286865 months=['2024-06', '2024-07', '2024-08'] dd=-0.03021181579572821
- final equity $103,292 | chassis `jpn225-keltner55-fixed-0.50`

### 43C — 43C joint XAG soft + JPN 0.50%

- trades=103 WR=53.4% L/S=78/25
- reasons={'TIME': 51, 'SL': 23, 'TP': 27, 'SL_OPEN': 2} gov={'fixed': 47, 'full': 39, 'mid': 15, 'floor': 2} by_sym={'JPN225': 47, 'XAG': 56}
- HO net $8,879 (~$907/mo) | Fit $8,589 | leave-out drop ['2026-01', '2025-12'] → $-9,019
- max DD 9.11% | worst Prague day 2026-05-16 @ -3.11% | fail-days 0 | legal=True
- ≤90d 48/857 (HO-era 8) | seq 60/857 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=2 best_outside%=6.91615863532522 months=['2024-03', '2024-04', '2024-05'] dd=-0.09091870422659168
- sample ≤90d starts: ['2025-11-01', '2025-11-02', '2025-11-03', '2025-11-04', '2025-11-05']
- sample seq starts: ['2025-07-13', '2025-07-14', '2025-07-15', '2025-07-16', '2025-07-17']
- final equity $117,469 | chassis `xag-soft+jpn-fixed-0.50`

### 43D — 43D joint XAG soft + JPN 0.25%

- trades=103 WR=53.4% L/S=78/25
- reasons={'TIME': 51, 'SL': 23, 'TP': 27, 'SL_OPEN': 2} gov={'fixed': 47, 'full': 36, 'mid': 16, 'floor': 4} by_sym={'JPN225': 47, 'XAG': 56}
- HO net $9,179 (~$938/mo) | Fit $2,985 | leave-out drop ['2026-01', '2025-12'] → $-6,937
- max DD 9.16% | worst Prague day 2024-05-24 @ -2.82% | fail-days 0 | legal=True
- ≤90d 48/857 (HO-era 8) | seq 60/857 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=2 best_outside%=6.69592698242496 months=['2024-03', '2024-04', '2024-05'] dd=-0.09164889843208711
- sample ≤90d starts: ['2025-11-01', '2025-11-02', '2025-11-03', '2025-11-04', '2025-11-05']
- sample seq starts: ['2025-07-13', '2025-07-14', '2025-07-15', '2025-07-16', '2025-07-17']
- final equity $112,165 | chassis `xag-soft+jpn-fixed-0.25`

## Does this open a ~3mo path?

**CONDITIONAL — XAG soft + JPN fixed satellite legal DD + windows, not ACCEPT** via 43D (43D joint XAG soft + JPN 0.25%): max DD 9.2%, ≤90d HO-era 8 (windows_survived=Y vs C42 wipe-risk), HO ~$938/mo, leave-out still FAIL ($-6,937 vs 43A $-6,976). 43C leave worse ($-9,019); 43D leave ≈43A ($-6,937). No deploy.


Live C4 / drip / FREEZE / MetaAPI: **untouched**. Gold not packaged. US100 NR7 excluded. No deploy.
