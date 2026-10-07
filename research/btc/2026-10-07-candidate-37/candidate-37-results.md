# Candidate 37 Results — XAG soft PRIMARY + US100 NR7 @0.25% fixed satellite

**NO — XAG soft primary + US100 0.25% fixed satellite does not open a deployable ~3mo path.** HO≤90d windows still 0 (did not survive satellite), DD illegal, or no ≤90d path.

**XAG window survival (37A→37C):** 37A HO≤90d=8 → 37C joint HO≤90d=0 (seq HO 0→0) | windows_survived=N

**Leave-out vs 37A:** 37A leave-out $-6,976 → 37C leave-out $-6,569 (delta $407)

**Success vs C35:** HO≤90d on 37C > 0? **N** (C35D had 0)

**US100 data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/usatechidxusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `5d833b201f3374797bd64ae50e2937af21affc1a52ef33a2119d316d35fdd3af` end `2026-09-01 23:58:00+00:00`
**XAG data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c` end `2026-09-01 23:59:00+00:00`
**Measured (ET):** 2026-10-07 12:43 ET

## ASSUMPTIONS

| Item | Value |
|---|---|
| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** (ASSUMPTION — C19B/C21B) |
| US100 costs | spread 1 / comm 0 / contract 1 (catalogue) |
| XAG risks (PRIMARY) | **2.50% / 1.25% / 0.75%** soft on shared peak |
| US100 risk (SATELLITE) | **fixed 0.25%** always — does NOT soft-scale |
| Soft gov | dd<5% full; 5–8% mid; ≥8% floor — **XAG only**; never sticky-block |
| Prague day kill | −3% both sleeves |
| Max positions | one per sleeve (two simultaneous OK) |
| Thesis lock | XAG-primary + tiny US100 satellite — NOT a post-hoc C35 retune |

## Scoreboard

| Book | Symbol | Gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Explorer out/cnt | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---|---|---|
| 37A | XAG | SOFT-XAG | 847 | 9.4% | 48/838 (8) | 60/838 (0) | N/A | -6,976 | YES | 0/1 best=6.435126039242833 | CONDITIONAL |
| 37B | US100 | FIXED0.25 | 385 | 0.3% | 0/732 (0) | 0/732 (0) | N/A | 2,142 | YES | 0/0 best=2.0096146424077865 | REJECT |
| 37C | JOINT | SOFT-XAG+US100fix | 1,186 | 7.7% | 100/838 (0) | 60/838 (0) | N/A | -6,569 | YES | 0/2 best=7.276223404167981 | REJECT |

### 37A — 37A XAG Donchian @2.50% soft (control)

- trades=56 WR=53.6% L/S=44/12
- reasons={'SL': 14, 'TP': 24, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 37, 'mid': 13, 'floor': 6} by_sym={'XAG': 56}
- HO net $8,291 (~$847/mo) | Fit $1,664 | leave-out drop ['2026-01', '2025-12'] → $-6,976
- max DD 9.40% | worst Prague day 2026-01-31 @ -2.69% | fail-days 0 | legal=True
- ≤90d 48/838 (HO-era 8) | seq 60/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=1 best_outside%=6.435126039242833 months=['2024-03', '2024-04', '2024-05'] dd=-0.09403781654124409
- sample ≤90d starts: ['2025-11-01', '2025-11-02', '2025-11-03', '2025-11-04', '2025-11-05']
- sample seq starts: ['2025-07-13', '2025-07-14', '2025-07-15', '2025-07-16', '2025-07-17']
- final equity $109,955 | chassis `xag-donchian-20d-2.50+softgov`

### 37B — 37B US100 NR7 @0.25% fixed

- trades=21 WR=95.2% L/S=18/3
- reasons={'TP': 20, 'SL': 1} gov={'fixed': 21} by_sym={'US100': 21}
- HO net $3,766 (~$385/mo) | Fit $6,360 | leave-out drop ['2026-04', '2026-06'] → $2,142
- max DD 0.25% | worst Prague day 2025-02-21 @ -0.25% | fail-days 0 | legal=True
- ≤90d 0/732 (HO-era 0) | seq 0/732 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=2.0096146424077865 months=['2026-03', '2026-04', '2026-05'] dd=-0.002510327574787932
- final equity $110,126 | chassis `us100-nr7-0.25-fixed`

### 37C — 37C XAG soft primary + US100 0.25% sat (verdict)

- trades=77 WR=64.9% L/S=62/15
- reasons={'SL': 15, 'TP': 44, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 43, 'fixed': 21, 'mid': 13} by_sym={'XAG': 56, 'US100': 21}
- HO net $11,615 (~$1,186/mo) | Fit $14,431 | leave-out drop ['2026-01', '2025-12'] → $-6,569
- max DD 7.70% | worst Prague day 2026-03-04 @ -2.67% | fail-days 0 | legal=True
- ≤90d 100/838 (HO-era 0) | seq 60/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=2 best_outside%=7.276223404167981 months=['2024-03', '2024-04', '2024-05'] dd=-0.07696923505980803
- sample ≤90d starts: ['2025-07-13', '2025-07-14', '2025-07-15', '2025-07-16', '2025-07-17']
- sample seq starts: ['2025-07-13', '2025-07-14', '2025-07-15', '2025-07-16', '2025-07-17']
- final equity $126,045 | chassis `xag-primary+us100-0.25-sat+softgov-xag-only`

## Does this open a ~3mo path?

**NO — XAG soft primary + US100 0.25% fixed satellite does not open a deployable ~3mo path.** HO≤90d windows still 0 (did not survive satellite), DD illegal, or no ≤90d path.

**Windows survived (37C HO≤90d > 0)? N**

Live C4 / drip / FREEZE / MetaAPI: **untouched**. Gold not packaged. No deploy.
