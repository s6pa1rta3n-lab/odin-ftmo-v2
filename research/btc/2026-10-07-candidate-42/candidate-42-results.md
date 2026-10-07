# Candidate 42 Results — XAG Donchian soft + JPN225 Keltner55 soft (no US100 / no Gold)

**NO — XAG Donchian soft + JPN225 Keltner soft joint does not open a deployable ~3mo path.** 42D soft joint keeps 5/8 XAG HO≤90d windows (windows_survived=Y) but max DD 11.1% illegal (>10%); leave-out still FAIL ($-9,176). 42C ungov DD 21.0%. 42A alone remains CONDITIONAL (reconfirm).

**XAG window survival (42A→42D):** 42A HO≤90d=8 → 42D joint HO≤90d=5 (seq HO 0→0) | windows_survived=Y

**XAG data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c` end `2026-09-01 23:59:00+00:00`
**JPN225 data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/jpnidxjpy-m1-bid-2024-01-01-2026-09-02.csv` sha256 `b7e9a85045eba935ead5812f13d461ba919f60d8220581671bfaf0b66ab82a6e` end `2026-09-01 23:59:00+00:00`
**USDJPY FX:** `/workspace/strategy-explorer/pr36/dukascopy-raw/usdjpy-m1-bid-2024-01-01-2026-09-02.csv` sha256 `ed7c8db716fe2e4a572dfe15d21157944427086636d1b97929bbdd49097cdcca` (mid for JPY→USD)
**Measured (ET):** 2026-10-07 12:53 ET

## ASSUMPTIONS

| Item | Value |
|---|---|
| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** (ASSUMPTION — C19B/C21B) |
| XAG risks | **2.50% / 1.25% / 0.75%** (full C21B) |
| JPN225 contract / spread / commission | **10** / **8.0 ASSUMPTION** / **0** (catalogue JP225.cash) |
| JPN225 risks | **2.50% / 1.25% / 0.625%** (exact C31) |
| JPY→USD | USDJPY M1 mid at entry (size) and exit (PnL) |
| Soft gov | dd<5% full; 5–8% mid; ≥8% floor; never sticky-block |
| Prague day kill | −3% both sleeves |
| Max positions | one per sleeve (two simultaneous OK) |
| US100 NR7 | **excluded** |
| Gold | not packaged |

## Scoreboard

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Explorer out/cnt | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---|---|---|
| 42A | XAG | SOFT | 847 | 9.4% | 48/838 (8) | 60/838 (0) | N/A | -6,976 | YES | 0/1 best=6.435126039242833 | CONDITIONAL |
| 42B | JPN225 | SOFT | 484 | 9.3% | 0/845 (0) | 0/845 (0) | N/A | -1,438 | YES | 0/0 best=10.122251667122018 | REJECT |
| 42C | JOINT | OFF | 1,604 | 21.0% | 134/857 (0) | 83/857 (0) | N/A | -6,084 | NO | 0/5 best=10.354059618018052 | REJECT |
| 42D | JOINT | SOFT | 1,224 | 11.1% | 71/857 (5) | 83/857 (0) | N/A | -9,176 | NO | 0/3 best=10.104582153797859 | REJECT |

### 42A — 42A XAG Donchian @2.50% soft

- trades=56 WR=53.6% L/S=44/12
- reasons={'SL': 14, 'TP': 24, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 37, 'mid': 13, 'floor': 6} by_sym={'XAG': 56}
- HO net $8,291 (~$847/mo) | Fit $1,664 | leave-out drop ['2026-01', '2025-12'] → $-6,976
- max DD 9.40% | worst Prague day 2026-01-31 @ -2.69% | fail-days 0 | legal=True
- ≤90d 48/838 (HO-era 8) | seq 60/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=1 best_outside%=6.435126039242833 months=['2024-03', '2024-04', '2024-05'] dd=-0.09403781654124409
- sample ≤90d starts: ['2025-11-01', '2025-11-02', '2025-11-03', '2025-11-04', '2025-11-05']
- sample seq starts: ['2025-07-13', '2025-07-14', '2025-07-15', '2025-07-16', '2025-07-17']
- final equity $109,955 | chassis `xag-donchian-20d-2.50+softgov`

### 42B — 42B JPN225 Keltner55 @2.50% soft

- trades=47 WR=53.2% L/S=34/13
- reasons={'TIME': 34, 'SL': 9, 'TP': 3, 'SL_OPEN': 1} gov={'full': 27, 'mid': 11, 'floor': 9} by_sym={'JPN225': 47}
- HO net $4,734 (~$484/mo) | Fit $7,155 | leave-out drop ['2026-01', '2026-04'] → $-1,438
- max DD 9.32% | worst Prague day 2024-10-31 @ -2.66% | fail-days 0 | legal=True
- ≤90d 0/845 (HO-era 0) | seq 0/845 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=10.122251667122018 months=['2024-06', '2024-07', '2024-08'] dd=-0.09320186527795633
- final equity $111,889 | chassis `jpn225-keltner55-2.50+softgov`

### 42C — 42C joint ungoverened

- trades=103 WR=53.4% L/S=78/25
- reasons={'TIME': 51, 'SL': 23, 'TP': 27, 'SL_OPEN': 2} gov={'n/a': 103} by_sym={'JPN225': 47, 'XAG': 56}
- HO net $15,707 (~$1,604/mo) | Fit $17,314 | leave-out drop ['2026-01', '2025-12'] → $-6,084
- max DD 21.04% | worst Prague day 2024-05-24 @ -4.97% | fail-days 0 | legal=False
- ≤90d 134/857 (HO-era 0) | seq 83/857 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=5 best_outside%=10.354059618018052 months=['2024-06', '2024-07', '2024-08'] dd=-0.21038369190431871
- sample ≤90d starts: ['2025-07-13', '2025-07-14', '2025-07-15', '2025-07-16', '2025-07-17']
- sample seq starts: ['2025-07-13', '2025-07-14', '2025-07-15', '2025-07-16', '2025-07-17']
- final equity $133,021 | chassis `xag+jpn-joint-ungov`

### 42D — 42D joint + soft gov (verdict)

- trades=103 WR=53.4% L/S=78/25
- reasons={'TIME': 51, 'SL': 23, 'TP': 27, 'SL_OPEN': 2} gov={'full': 52, 'mid': 26, 'floor': 25} by_sym={'JPN225': 47, 'XAG': 56}
- HO net $11,978 (~$1,224/mo) | Fit $12,241 | leave-out drop ['2026-01', '2025-12'] → $-9,176
- max DD 11.15% | worst Prague day 2024-05-24 @ -4.97% | fail-days 0 | legal=False
- ≤90d 71/857 (HO-era 5) | seq 83/857 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=3 best_outside%=10.104582153797859 months=['2024-02', '2024-03', '2024-04'] dd=-0.11146746064655498
- sample ≤90d starts: ['2025-10-29', '2025-10-30', '2025-10-31', '2025-11-01', '2025-11-02']
- sample seq starts: ['2025-07-13', '2025-07-14', '2025-07-15', '2025-07-16', '2025-07-17']
- final equity $124,219 | chassis `xag+jpn-joint+softgov`

## Does this open a ~3mo path?

**NO — XAG Donchian soft + JPN225 Keltner soft joint does not open a deployable ~3mo path.** 42D soft joint keeps 5/8 XAG HO≤90d windows (windows_survived=Y) but max DD 11.1% illegal (>10%); leave-out still FAIL ($-9,176). 42C ungov DD 21.0%. 42A alone remains CONDITIONAL (reconfirm).

Live C4 / drip / FREEZE / MetaAPI: **untouched**. Gold not packaged. US100 NR7 excluded. No deploy.
