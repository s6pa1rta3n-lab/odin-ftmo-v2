# Candidate 46 Results — XAG soft-2.00 + BTC Ext-repair (around 45E)

**CONDITIONAL — Ext repair incomplete; no ACCEPT** via 46C: max DD 8.1%, HO≤90d 6, HO ~$1,434/mo, leave $151 (Δ vs 46A -2,218), Ext $-1,232. Ext $-1,232 still blocks ACCEPT (leave green). Lowering BTC improves Ext but leave dies before Ext≥0; soft BTC best Ext still red.

**XAG window survival / leave Δ:** 46A HO≤90d=6 leave=2370 → 46A HO≤90d=6 DD=9.9% leave=2370 (Δ+0) | 46B HO≤90d=6 DD=9.5% leave=691 (Δ-1678) | 46C HO≤90d=6 DD=8.1% leave=151 (Δ-2218) | 46D HO≤90d=8 DD=7.9% leave=-572 (Δ-2942) | 46E HO≤90d=8 DD=7.6% leave=-1267 (Δ-3637) | 46F HO≤90d=6 DD=8.3% leave=-3170 (Δ-5539) | windows_survived=Y

**XAG data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c` end `2026-09-01 23:59:00+00:00`
**BTC data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/btcusd-m1-bid-2024-01-01-2026-09-02.csv` + dukas-ext sha256 main `437a2c36f6ac9da5684533f9cde17e029f177abacab30579cd2c30e625443829` end `2026-10-07 11:34:00+00:00`
**Measured (ET):** 2026-10-07 13:11 ET

## ASSUMPTIONS

| Item | Value |
|---|---|
| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** (ASSUMPTION — C19B/C21B) |
| XAG risks | soft **2.00% → 1.00% → 0.60%** (46A–F); 46G optional **1.75→0.90→0.50** |
| BTC costs | spread **15** / comm 0 (C15 model) |
| BTC risks | FIXED **0.60 / 0.55 / 0.50 / 0.45 / 0.40%**; 46F soft **0.60→0.30→0.15** |
| Soft gov | XAG soft ladder; BTC fixed except 46F soft on BTC too |
| Prague day kill | −3% both |
| Positions | dual-open; no Gold / NR7 / JPN |
| US100 / Gold / JPN | excluded |

## Scoreboard

| Book | Symbol | Mode | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Δ vs 46A | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---:|---|---|
| 46A | JOINT | dual/0.60% | 1,663 | 9.9% | 37/879 (6) | 7/879 (4) | -1,489 | 2,370 | +0 | YES | CONDITIONAL |
| 46B | JOINT | dual/0.55% | 1,455 | 9.5% | 37/879 (6) | 7/879 (4) | -1,345 | 691 | -1,678 | YES | CONDITIONAL |
| 46C | JOINT | dual/0.50% | 1,434 | 8.1% | 37/879 (6) | 4/879 (4) | -1,232 | 151 | -2,218 | YES | CONDITIONAL |
| 46D | JOINT | dual/0.45% | 1,344 | 7.9% | 35/879 (8) | 4/879 (4) | -1,098 | -572 | -2,942 | YES | CONDITIONAL |
| 46E | JOINT | dual/0.40% | 1,279 | 7.6% | 35/879 (8) | 0/879 (0) | -985 | -1,267 | -3,637 | YES | CONDITIONAL |
| 46F | JOINT | dual | 1,146 | 8.3% | 42/879 (6) | 7/879 (4) | -722 | -3,170 | -5,539 | YES | CONDITIONAL |

### 46A — 46A XAG soft-2.00 + BTC 0.60%

- trades=170 WR=43.5% L/S=100/70
- reasons={'stop': 67, 'SL': 14, 'TP': 24, 'TIME': 17, 'target': 43, 'gap-stop': 3, 'gap-target': 1, 'SL_OPEN': 1} gov={'fixed': 114, 'full': 42, 'mid': 9, 'floor': 5} by_sym={'BTC': 114, 'XAG': 56}
- HO net $16,283 (~$1,663/mo) | Fit $-766 | leave-out drop ['2026-01', '2026-08'] → $2,370
- max DD 9.89% | worst Prague day 2024-05-10 @ -2.60% | fail-days 0 | legal=True
- ≤90d 37/879 (HO-era 6) | seq 7/879 (HO-era 4)
- Explorer xcheck: outside_countable=0 countable=2 best_outside%=6.742212916364276 months=['2024-06', '2024-07', '2024-08']
- final equity $114,028 | chassis `xag-soft-2.00+btc-fixed-0.60`

### 46B — 46B XAG soft-2.00 + BTC 0.55%

- trades=170 WR=43.5% L/S=100/70
- reasons={'stop': 67, 'SL': 14, 'TP': 24, 'TIME': 17, 'target': 43, 'gap-stop': 3, 'gap-target': 1, 'SL_OPEN': 1} gov={'fixed': 114, 'full': 41, 'mid': 11, 'floor': 4} by_sym={'BTC': 114, 'XAG': 56}
- HO net $14,249 (~$1,455/mo) | Fit $-391 | leave-out drop ['2026-01', '2025-12'] → $691
- max DD 9.53% | worst Prague day 2024-05-10 @ -2.55% | fail-days 0 | legal=True
- ≤90d 37/879 (HO-era 6) | seq 7/879 (HO-era 4)
- Explorer xcheck: outside_countable=0 countable=2 best_outside%=6.182908958839883 months=['2024-06', '2024-07', '2024-08']
- final equity $112,513 | chassis `xag-soft-2.00+btc-fixed-0.55`

### 46C — 46C XAG soft-2.00 + BTC 0.50%

- trades=170 WR=43.5% L/S=100/70
- reasons={'stop': 67, 'SL': 14, 'TP': 24, 'TIME': 17, 'target': 43, 'gap-stop': 3, 'gap-target': 1, 'SL_OPEN': 1} gov={'fixed': 114, 'full': 43, 'mid': 13} by_sym={'BTC': 114, 'XAG': 56}
- HO net $14,040 (~$1,434/mo) | Fit $1,421 | leave-out drop ['2026-01', '2025-12'] → $151
- max DD 8.14% | worst Prague day 2024-05-10 @ -2.57% | fail-days 0 | legal=True
- ≤90d 37/879 (HO-era 6) | seq 4/879 (HO-era 4)
- Explorer xcheck: outside_countable=0 countable=2 best_outside%=5.631738285684884 months=['2024-06', '2024-07', '2024-08']
- final equity $114,230 | chassis `xag-soft-2.00+btc-fixed-0.50`

### 46D — 46D XAG soft-2.00 + BTC 0.45%

- trades=170 WR=43.5% L/S=100/70
- reasons={'stop': 67, 'SL': 14, 'TP': 24, 'TIME': 17, 'target': 43, 'gap-stop': 3, 'gap-target': 1, 'SL_OPEN': 1} gov={'fixed': 114, 'full': 43, 'mid': 13} by_sym={'BTC': 114, 'XAG': 56}
- HO net $13,157 (~$1,344/mo) | Fit $1,468 | leave-out drop ['2026-01', '2025-12'] → $-572
- max DD 7.86% | worst Prague day 2024-05-10 @ -2.51% | fail-days 0 | legal=True
- ≤90d 35/879 (HO-era 8) | seq 4/879 (HO-era 4)
- Explorer xcheck: outside_countable=0 countable=2 best_outside%=5.084243821604262 months=['2024-06', '2024-07', '2024-08']
- final equity $113,527 | chassis `xag-soft-2.00+btc-fixed-0.45`

### 46E — 46E XAG soft-2.00 + BTC 0.40%

- trades=170 WR=43.5% L/S=100/70
- reasons={'stop': 67, 'SL': 14, 'TP': 24, 'TIME': 17, 'target': 43, 'gap-stop': 3, 'gap-target': 1, 'SL_OPEN': 1} gov={'fixed': 114, 'full': 44, 'mid': 12} by_sym={'BTC': 114, 'XAG': 56}
- HO net $12,521 (~$1,279/mo) | Fit $2,394 | leave-out drop ['2026-01', '2025-12'] → $-1,267
- max DD 7.59% | worst Prague day 2024-05-10 @ -2.46% | fail-days 0 | legal=True
- ≤90d 35/879 (HO-era 8) | seq 0/879 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=2 best_outside%=4.638400982416302 months=['2024-03', '2024-04', '2024-05']
- final equity $113,930 | chassis `xag-soft-2.00+btc-fixed-0.40`

### 46F — 46F XAG soft-2.00 + BTC soft 0.60

- trades=170 WR=43.5% L/S=100/70
- reasons={'stop': 67, 'SL': 14, 'TP': 24, 'TIME': 17, 'target': 43, 'gap-stop': 3, 'gap-target': 1, 'SL_OPEN': 1} gov={'full': 99, 'mid': 66, 'floor': 5} by_sym={'BTC': 114, 'XAG': 56}
- HO net $11,215 (~$1,146/mo) | Fit $1,589 | leave-out drop ['2026-01', '2025-12'] → $-3,170
- max DD 8.28% | worst Prague day 2024-05-10 @ -2.60% | fail-days 0 | legal=True
- ≤90d 42/879 (HO-era 6) | seq 7/879 (HO-era 4)
- Explorer xcheck: outside_countable=0 countable=2 best_outside%=6.136447413116963 months=['2024-06', '2024-07', '2024-08']
- final equity $112,082 | chassis `xag-soft-2.00+btc-soft-0.60`

## Does this open a ~3mo path?

**CONDITIONAL — Ext repair incomplete; no ACCEPT** via 46C: max DD 8.1%, HO≤90d 6, HO ~$1,434/mo, leave $151 (Δ vs 46A -2,218), Ext $-1,232. Ext $-1,232 still blocks ACCEPT (leave green). Lowering BTC improves Ext but leave dies before Ext≥0; soft BTC best Ext still red.

Live C4 / drip / FREEZE / MetaAPI: **untouched**. Gold/NR7/JPN excluded. No deploy.
