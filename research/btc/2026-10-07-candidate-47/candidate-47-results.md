# Candidate 47 Results — XAG soft-2.00 PRIMARY + US100 NR7 FIXED tiny sat (no BTC / no Gold)

**CONDITIONAL — XAG soft-2.00 + US100 NR7 sat legal/windows incomplete** via 47E: max DD 6.9%, HO≤90d 15, HO ~$1,429/mo, leave $-1,096 (Δ vs 47A +5,314). Ext: UNAVAILABLE (feeds end 2026-09-01; no dukas-ext). Not ACCEPT.

**XAG window survival / leave Δ:** 47A HO≤90d=0 leave=-6410 → 47C HO≤90d=14 DD=7.7% leave=-5228 (Δ+1182) | 47D HO≤90d=14 DD=7.2% leave=-2807 (Δ+3603) | 47E HO≤90d=15 DD=6.9% leave=-1096 (Δ+5314) | windows_survived=Y

**Note:** Prior family drop of XAG+NR7 was for soft-**2.50** stacks (C35/C37/C39). C47 is a deliberate soft-**2.00** downshift + tiny fixed NR7 retest.

**XAG data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c` end `2026-09-01 23:59:00+00:00`
**US100 data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/usatechidxusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `5d833b201f3374797bd64ae50e2937af21affc1a52ef33a2119d316d35fdd3af` end `2026-09-01 23:58:00+00:00`
**Measured (ET):** 2026-10-07 13:15 ET

## ASSUMPTIONS

| Item | Value |
|---|---|
| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** (ASSUMPTION — C19B/C21B) |
| XAG risks | soft **2.00% → 1.00% → 0.60%** |
| US100 costs | spread **1** / comm **0** / contract **1** (C41 NR7 chassis) |
| US100 risks | FIXED **0.15% / 0.25% / 0.35%** (no soft-scale) |
| Soft gov | XAG only; US100 fixed |
| Prague day kill | −3% both |
| Positions | dual-open (47C–E); MUTEX only if 47F |
| BTC / Gold | **excluded** |
| Ext | N/A if feeds end 2026-09-01 (no dukas-ext for XAG/US100) — do not invent |

## Scoreboard

| Book | Symbol | Mode | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Δ vs 47A | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---:|---|---|
| 47A | XAG | XAG soft-2.00 | 629 | 7.8% | 0/838 (0) | 0/838 (0) | N/A | -6,410 | +0 | YES | REJECT |
| 47B | US100 | NR7 FIXED 0.15% | 224 | 0.2% | 0/732 (0) | 0/732 (0) | N/A | 1,247 | +7,657 | YES | REJECT |
| 47C | JOINT | dual/NR7 0.15% | 856 | 7.7% | 14/838 (14) | 0/838 (0) | N/A | -5,228 | +1,182 | YES | CONDITIONAL |
| 47D | JOINT | dual/NR7 0.25% | 1,186 | 7.2% | 14/838 (14) | 0/838 (0) | N/A | -2,807 | +3,603 | YES | CONDITIONAL |
| 47E | JOINT | dual/NR7 0.35% | 1,429 | 6.9% | 25/838 (15) | 0/838 (0) | N/A | -1,096 | +5,314 | YES | CONDITIONAL |

### 47A — 47A XAG soft-2.00 alone

- trades=56 WR=53.6% L/S=44/12
- reasons={'SL': 14, 'TP': 24, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 42, 'mid': 14} by_sym={'XAG': 56}
- HO net $6,154 (~$629/mo) | Fit $4,124 | leave-out drop ['2026-01', '2025-12'] → $-6,410
- max DD 7.84% | worst Prague day 2026-03-04 @ -2.17% | fail-days 0 | legal=True
- ≤90d 0/838 (HO-era 0) | seq 0/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=5.184672199292106 months=['2024-03', '2024-04', '2024-05']
- final equity $110,278 | chassis `xag-soft-2.00` | Ext N/A (UNAVAILABLE (feeds end 2026-09-01; no dukas-ext))

### 47B — 47B US100 NR7 FIXED 0.15%

- trades=21 WR=95.2% L/S=18/3
- reasons={'TP': 20, 'SL': 1} gov={'fixed': 21} by_sym={'US100': 21}
- HO net $2,190 (~$224/mo) | Fit $3,775 | leave-out drop ['2026-04', '2026-06'] → $1,247
- max DD 0.15% | worst Prague day 2025-02-21 @ -0.15% | fail-days 0 | legal=True
- ≤90d 0/732 (HO-era 0) | seq 0/732 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=1.2012419351453474 months=['2026-04', '2026-05', '2026-06']
- final equity $105,966 | chassis `us100-nr7-fixed-0.15` | Ext N/A (UNAVAILABLE (feeds end 2026-09-01; no dukas-ext))

### 47C — 47C XAG soft-2.00 + NR7 0.15%

- trades=77 WR=64.9% L/S=62/15
- reasons={'SL': 15, 'TP': 44, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 49, 'fixed': 21, 'mid': 7} by_sym={'XAG': 56, 'US100': 21}
- HO net $8,380 (~$856/mo) | Fit $7,715 | leave-out drop ['2026-01', '2025-12'] → $-5,228
- max DD 7.67% | worst Prague day 2026-06-14 @ -2.37% | fail-days 0 | legal=True
- ≤90d 14/838 (HO-era 14) | seq 0/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=5.710302888376773 months=['2024-03', '2024-04', '2024-05']
- final equity $116,095 | chassis `xag-soft-2.00+us100-nr7-0.15` | Ext N/A (UNAVAILABLE (feeds end 2026-09-01; no dukas-ext))

### 47D — 47D XAG soft-2.00 + NR7 0.25%

- trades=77 WR=64.9% L/S=62/15
- reasons={'SL': 15, 'TP': 44, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 51, 'fixed': 21, 'mid': 5} by_sym={'XAG': 56, 'US100': 21}
- HO net $11,610 (~$1,186/mo) | Fit $11,575 | leave-out drop ['2026-01', '2025-12'] → $-2,807
- max DD 7.19% | worst Prague day 2026-06-14 @ -2.26% | fail-days 0 | legal=True
- ≤90d 14/838 (HO-era 14) | seq 0/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=6.114421589652541 months=['2024-03', '2024-04', '2024-05']
- final equity $123,185 | chassis `xag-soft-2.00+us100-nr7-0.25` | Ext N/A (UNAVAILABLE (feeds end 2026-09-01; no dukas-ext))

### 47E — 47E XAG soft-2.00 + NR7 0.35%

- trades=77 WR=64.9% L/S=62/15
- reasons={'SL': 15, 'TP': 44, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 52, 'fixed': 21, 'mid': 4} by_sym={'XAG': 56, 'US100': 21}
- HO net $13,989 (~$1,429/mo) | Fit $13,161 | leave-out drop ['2026-01', '2025-12'] → $-1,096
- max DD 6.87% | worst Prague day 2026-06-14 @ -2.19% | fail-days 0 | legal=True
- ≤90d 25/838 (HO-era 15) | seq 0/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=6.518252682332482 months=['2024-03', '2024-04', '2024-05']
- final equity $127,150 | chassis `xag-soft-2.00+us100-nr7-0.35` | Ext N/A (UNAVAILABLE (feeds end 2026-09-01; no dukas-ext))

## Does this open a ~3mo path?

**CONDITIONAL — XAG soft-2.00 + US100 NR7 sat legal/windows incomplete** via 47E: max DD 6.9%, HO≤90d 15, HO ~$1,429/mo, leave $-1,096 (Δ vs 47A +5,314). Ext: UNAVAILABLE (feeds end 2026-09-01; no dukas-ext). Not ACCEPT.

Live C4 / drip / FREEZE / MetaAPI: **untouched**. BTC/Gold excluded. No deploy.
