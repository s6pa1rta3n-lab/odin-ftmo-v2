# Candidate 48 Results — XAG soft-2.00 + US100 NR7 higher sat (leave flip; no BTC/Gold)

**YES — ACCEPT pass-path** via 48E: max DD 6.7%, HO≤90d 15, leave $2,422, HO ~$1,926/mo. Ext: UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) (N/A OK). **Still no live deploy from this research pack.**

**XAG window survival / leave Δ:** 48A HO≤90d=15 leave=-1096 → 48A HO≤90d=15 DD=6.9% leave=-1096 (Δ+0) | 48B HO≤90d=15 DD=6.6% leave=-269 (Δ+827) | 48C HO≤90d=15 DD=6.4% leave=814 (Δ+1910) | 48D HO≤90d=15 DD=6.2% leave=1036 (Δ+2131) | 48E HO≤90d=15 DD=6.7% leave=2422 (Δ+3518) | windows_survived=Y

**Note:** Around 47E (leave −1096 / HO=15). Scale NR7 FIXED above 0.35%. Ext N/A is NOT an ACCEPT blocker when dukas-ext missing.

**XAG data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c` end `2026-09-01 23:59:00+00:00`
**US100 data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/usatechidxusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `5d833b201f3374797bd64ae50e2937af21affc1a52ef33a2119d316d35fdd3af` end `2026-09-01 23:58:00+00:00`
**Measured (ET):** 2026-10-07 13:17 ET

## ASSUMPTIONS

| Item | Value |
|---|---|
| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** |
| XAG risks | soft **2.00→1.00→0.60** (48A–E); 48F optional **1.75→0.90→0.50** |
| US100 costs | spread **1** / comm **0** / contract **1** |
| US100 risks | FIXED **0.35 / 0.40 / 0.45 / 0.50 / 0.60%** |
| Soft gov | XAG only; US100 fixed |
| Prague day kill | −3% both |
| Positions | dual-open |
| BTC / Gold | **excluded** |
| Ext | N/A OK for ACCEPT when feed missing — do not invent |

## Scoreboard

| Book | Symbol | Mode | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Δ vs 48A | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---:|---|---|
| 48A | JOINT | dual/NR7 0.35% | 1,429 | 6.9% | 25/838 (15) | 0/838 (0) | N/A | -1,096 | +0 | YES | CONDITIONAL |
| 48B | JOINT | dual/NR7 0.40% | 1,545 | 6.6% | 25/838 (15) | 0/838 (0) | N/A | -269 | +827 | YES | CONDITIONAL |
| 48C | JOINT | dual/NR7 0.45% | 1,670 | 6.4% | 25/838 (15) | 0/838 (0) | N/A | 814 | +1,910 | YES | ACCEPT |
| 48D | JOINT | dual/NR7 0.50% | 1,756 | 6.2% | 25/838 (15) | 0/838 (0) | N/A | 1,036 | +2,131 | YES | ACCEPT |
| 48E | JOINT | dual/NR7 0.60% | 1,926 | 6.7% | 25/838 (15) | 0/838 (0) | N/A | 2,422 | +3,518 | YES | ACCEPT |

### 48A — 48A reconfirm 47E NR7 0.35%

- trades=77 WR=64.9% L/S=62/15
- reasons={'SL': 15, 'TP': 44, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 52, 'fixed': 21, 'mid': 4} by_sym={'XAG': 56, 'US100': 21}
- HO net $13,989 (~$1,429/mo) | Fit $13,161 | leave-out drop ['2026-01', '2025-12'] → $-1,096
- max DD 6.87% | worst Prague day 2026-06-14 @ -2.19% | fail-days 0 | legal=True
- ≤90d 25/838 (HO-era 15) | seq 0/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=6.518252682332482 months=['2024-03', '2024-04', '2024-05']
- final equity $127,150 | chassis `xag-soft-2.00+us100-nr7-0.35` | Ext N/A (UNAVAILABLE (feeds end 2026-09-01; no dukas-ext))

### 48B — 48B XAG soft-2.00 + NR7 0.40%

- trades=77 WR=64.9% L/S=62/15
- reasons={'SL': 15, 'TP': 44, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 52, 'fixed': 21, 'mid': 4} by_sym={'XAG': 56, 'US100': 21}
- HO net $15,124 (~$1,545/mo) | Fit $14,504 | leave-out drop ['2026-01', '2025-12'] → $-269
- max DD 6.63% | worst Prague day 2026-06-14 @ -2.15% | fail-days 0 | legal=True
- ≤90d 25/838 (HO-era 15) | seq 0/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=1 best_outside%=6.7206788885858515 months=['2024-03', '2024-04', '2024-05']
- final equity $129,628 | chassis `xag-soft-2.00+us100-nr7-0.40` | Ext N/A (UNAVAILABLE (feeds end 2026-09-01; no dukas-ext))

### 48C — 48C XAG soft-2.00 + NR7 0.45%

- trades=77 WR=64.9% L/S=62/15
- reasons={'SL': 15, 'TP': 44, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 53, 'fixed': 21, 'mid': 3} by_sym={'XAG': 56, 'US100': 21}
- HO net $16,352 (~$1,670/mo) | Fit $16,448 | leave-out drop ['2026-01', '2025-12'] → $814
- max DD 6.44% | worst Prague day 2026-06-14 @ -2.11% | fail-days 0 | legal=True
- ≤90d 25/838 (HO-era 15) | seq 0/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=6.923105094839221 months=['2024-03', '2024-04', '2024-05']
- final equity $132,800 | chassis `xag-soft-2.00+us100-nr7-0.45` | Ext N/A (UNAVAILABLE (feeds end 2026-09-01; no dukas-ext))

### 48D — 48D XAG soft-2.00 + NR7 0.50%

- trades=77 WR=64.9% L/S=62/15
- reasons={'SL': 15, 'TP': 44, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 53, 'fixed': 21, 'mid': 3} by_sym={'XAG': 56, 'US100': 21}
- HO net $17,187 (~$1,756/mo) | Fit $17,867 | leave-out drop ['2026-01', '2025-12'] → $1,036
- max DD 6.18% | worst Prague day 2026-06-14 @ -2.33% | fail-days 0 | legal=True
- ≤90d 25/838 (HO-era 15) | seq 0/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=1 best_outside%=7.126041961005991 months=['2024-03', '2024-04', '2024-05']
- final equity $135,053 | chassis `xag-soft-2.00+us100-nr7-0.50` | Ext N/A (UNAVAILABLE (feeds end 2026-09-01; no dukas-ext))

### 48E — 48E XAG soft-2.00 + NR7 0.60%

- trades=77 WR=64.9% L/S=62/15
- reasons={'SL': 15, 'TP': 44, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 54, 'fixed': 21, 'mid': 2} by_sym={'XAG': 56, 'US100': 21}
- HO net $18,859 (~$1,926/mo) | Fit $19,554 | leave-out drop ['2026-01', '2025-12'] → $2,422
- max DD 6.70% | worst Prague day 2026-06-14 @ -2.28% | fail-days 0 | legal=True
- ≤90d 25/838 (HO-era 15) | seq 0/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=1 best_outside%=7.457557958634409 months=['2024-03', '2024-04', '2024-05']
- final equity $138,413 | chassis `xag-soft-2.00+us100-nr7-0.60` | Ext N/A (UNAVAILABLE (feeds end 2026-09-01; no dukas-ext))

## Does this open a ~3mo path?

**YES — ACCEPT pass-path** via 48E: max DD 6.7%, HO≤90d 15, leave $2,422, HO ~$1,926/mo. Ext: UNAVAILABLE (feeds end 2026-09-01; no dukas-ext) (N/A OK). **Still no live deploy from this research pack.**

Live C4 / drip / FREEZE / MetaAPI: **untouched**. BTC/Gold excluded. No deploy.
