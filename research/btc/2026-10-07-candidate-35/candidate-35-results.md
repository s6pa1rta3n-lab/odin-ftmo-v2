# Candidate 35 Results — US100 NR7 @1% + XAG Donchian soft (full C21B tiers)

**CONDITIONAL — US100 NR7 + XAG Donchian soft legal DD + windows, not ACCEPT** via 35D (35D joint + soft gov (verdict)): max DD 6.6%, ≤90d 107/838 (HO-era 0), seq HO-era 0, HO ~$3,011/mo.

**XAG window survival (35B→35D):** 35B HO≤90d=8 → 35D joint HO≤90d=0 (seq HO 0→0)

**US100 data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/usatechidxusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `5d833b201f3374797bd64ae50e2937af21affc1a52ef33a2119d316d35fdd3af` end `2026-09-01 23:58:00+00:00`
**XAG data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c` end `2026-09-01 23:59:00+00:00`
**Measured (ET):** 2026-10-07 12:41 ET

## ASSUMPTIONS

| Item | Value |
|---|---|
| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** (ASSUMPTION — C19B/C21B) |
| US100 costs | spread 1 / comm 0 / contract 1 (catalogue) |
| XAG risks | **2.50% / 1.25% / 0.75%** (full C21B — NOT C29 halved) |
| US100 risks | **1.00% / 0.50% / 0.25%** |
| Soft gov | dd<5% full; 5–8% mid; ≥8% floor; never sticky-block |
| Prague day kill | −3% both sleeves |
| Max positions | one per sleeve (two simultaneous OK) |

## Scoreboard

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Explorer out/cnt | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---|---|---|
| 35A | US100 | SOFT | 1,931 | 1.0% | 0/732 (0) | 0/732 (0) | N/A | 10,588 | YES | 0/0 best=8.20896311077519 | REJECT |
| 35B | XAG | SOFT | 847 | 9.4% | 48/838 (8) | 60/838 (0) | N/A | -6,976 | YES | 0/1 best=6.435126039242833 | CONDITIONAL |
| 35C | JOINT | OFF | 3,372 | 7.1% | 120/838 (0) | 68/838 (0) | N/A | 8,793 | YES | 0/2 best=10.529687677038812 | CONDITIONAL |
| 35D | JOINT | SOFT | 3,011 | 6.6% | 107/838 (0) | 68/838 (0) | N/A | 5,783 | YES | 0/2 best=10.529687677038812 | CONDITIONAL |

### 35A — 35A US100 NR7 @1% soft

- trades=21 WR=95.2% L/S=18/3
- reasons={'TP': 20, 'SL': 1} gov={'full': 21} by_sym={'US100': 21}
- HO net $18,903 (~$1,931/mo) | Fit $27,736 | leave-out drop ['2026-04', '2026-06'] → $10,588
- max DD 1.01% | worst Prague day 2025-02-21 @ -1.01% | fail-days 0 | legal=True
- ≤90d 0/732 (HO-era 0) | seq 0/732 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=8.20896311077519 months=['2026-04', '2026-05', '2026-06'] dd=-0.010055189436447844
- final equity $146,639 | chassis `us100-nr7-1.00+softgov`

### 35B — 35B XAG Donchian @2.50% soft

- trades=56 WR=53.6% L/S=44/12
- reasons={'SL': 14, 'TP': 24, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 37, 'mid': 13, 'floor': 6} by_sym={'XAG': 56}
- HO net $8,291 (~$847/mo) | Fit $1,664 | leave-out drop ['2026-01', '2025-12'] → $-6,976
- max DD 9.40% | worst Prague day 2026-01-31 @ -2.69% | fail-days 0 | legal=True
- ≤90d 48/838 (HO-era 8) | seq 60/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=1 best_outside%=6.435126039242833 months=['2024-03', '2024-04', '2024-05'] dd=-0.09403781654124409
- sample ≤90d starts: ['2025-11-01', '2025-11-02', '2025-11-03', '2025-11-04', '2025-11-05']
- sample seq starts: ['2025-07-13', '2025-07-14', '2025-07-15', '2025-07-16', '2025-07-17']
- final equity $109,955 | chassis `xag-donchian-20d-2.50+softgov`

### 35C — 35C joint ungoverened

- trades=77 WR=64.9% L/S=62/15
- reasons={'SL': 15, 'TP': 44, 'TIME': 17, 'SL_OPEN': 1} gov={'n/a': 77} by_sym={'XAG': 56, 'US100': 21}
- HO net $33,011 (~$3,372/mo) | Fit $36,109 | leave-out drop ['2026-01', '2025-12'] → $8,793
- max DD 7.09% | worst Prague day 2026-06-14 @ -2.70% | fail-days 0 | legal=True
- ≤90d 120/838 (HO-era 0) | seq 68/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=2 best_outside%=10.529687677038812 months=['2024-03', '2024-04', '2024-05'] dd=-0.07086974082300783
- sample ≤90d starts: ['2025-06-30', '2025-07-01', '2025-07-02', '2025-07-03', '2025-07-04']
- sample seq starts: ['2025-06-30', '2025-07-01', '2025-07-02', '2025-07-03', '2025-07-04']
- final equity $169,120 | chassis `us100nr7+xag-joint-ungov`

### 35D — 35D joint + soft gov (verdict)

- trades=77 WR=64.9% L/S=62/15
- reasons={'SL': 15, 'TP': 44, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 69, 'mid': 8} by_sym={'XAG': 56, 'US100': 21}
- HO net $29,477 (~$3,011/mo) | Fit $30,986 | leave-out drop ['2026-01', '2025-12'] → $5,783
- max DD 6.59% | worst Prague day 2026-06-14 @ -2.85% | fail-days 0 | legal=True
- ≤90d 107/838 (HO-era 0) | seq 68/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=2 best_outside%=10.529687677038812 months=['2024-03', '2024-04', '2024-05'] dd=-0.0659146100717234
- sample ≤90d starts: ['2025-07-07', '2025-07-08', '2025-07-09', '2025-07-10', '2025-07-11']
- sample seq starts: ['2025-06-30', '2025-07-01', '2025-07-02', '2025-07-03', '2025-07-04']
- final equity $160,463 | chassis `us100nr7+xag-joint+softgov`

## Does this open a ~3mo path?

**CONDITIONAL — US100 NR7 + XAG Donchian soft legal DD + windows, not ACCEPT** via 35D (35D joint + soft gov (verdict)): max DD 6.6%, ≤90d 107/838 (HO-era 0), seq HO-era 0, HO ~$3,011/mo.

Live C4 / drip / FREEZE / MetaAPI: **untouched**. Gold not packaged. No deploy.
