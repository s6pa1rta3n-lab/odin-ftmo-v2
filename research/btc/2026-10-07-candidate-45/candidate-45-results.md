# Candidate 45 Results — XAG soft PRIMARY + BTC C15 FIXED higher satellite (leave flip attempt)

**CONDITIONAL — leave-out PASS + legal DD + HO windows, Ext red** via 45E: max DD 9.9%, HO≤90d 6, leave $2,370 (Δ vs 45A +9,345), HO ~$1,663/mo, Ext $-1,489. Not ACCEPT until Ext ≥0 (or waived). 45B–D DD-illegal or HO&lt;5. No deploy.

**XAG window survival / leave Δ:** 45A HO≤90d=8 leave=-6976 → 45B HO≤90d=6 DD=10.3% leave=-2166 (Δ+4810) | 45C HO≤90d=4 DD=11.1% leave=-493 (Δ+6483) | 45D HO≤90d=0 DD=11.9% leave=2051 (Δ+9026) | 45E HO≤90d=6 DD=9.9% leave=2370 (Δ+9345) | windows_survived=Y

**XAG data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c` end `2026-09-01 23:59:00+00:00`
**BTC data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/btcusd-m1-bid-2024-01-01-2026-09-02.csv` + dukas-ext sha256 main `437a2c36f6ac9da5684533f9cde17e029f177abacab30579cd2c30e625443829` end `2026-10-07 11:34:00+00:00`
**Measured (ET):** 2026-10-07 13:08 ET

## ASSUMPTIONS

| Item | Value |
|---|---|
| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** (ASSUMPTION — C19B/C21B) |
| XAG risks | **2.50% / 1.25% / 0.75%** soft |
| BTC costs | spread **15** / comm 0 (C15 model) |
| BTC risks | **FIXED 0.50% / 0.60% / 0.75%** (+ optional XAG soft 2.00 ladder on E/F) |
| Soft gov | XAG only; BTC fixed |
| Prague day kill | −3% both |
| Positions | dual-open; optional XAG soft 2.00 ladder on 45E/F |
| US100 / Gold / JPN | excluded |

## Scoreboard

| Book | Symbol | Mode | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Δ vs 45A | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---:|---|---|
| 45A | XAG | single | 847 | 9.4% | 48/838 (8) | 60/838 (0) | N/A | -6,976 | +0 | YES | CONDITIONAL |
| 45B | JOINT | dual/0.50% | 1,330 | 10.3% | 50/879 (6) | 37/879 (5) | -1,190 | -2,166 | +4,810 | NO | REJECT |
| 45C | JOINT | dual/0.60% | 1,530 | 11.1% | 52/879 (4) | 40/879 (6) | -1,456 | -493 | +6,483 | NO | REJECT |
| 45D | JOINT | dual/0.75% | 1,880 | 11.9% | 58/879 (0) | 53/879 (0) | -1,885 | 2,051 | +9,026 | NO | REJECT |
| 45E | JOINT | dual/0.60% | 1,663 | 9.9% | 37/879 (6) | 7/879 (4) | -1,489 | 2,370 | +9,345 | YES | CONDITIONAL |

### 45A — 45A XAG soft 2.50

- trades=56 WR=53.6% L/S=44/12
- reasons={'SL': 14, 'TP': 24, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 37, 'mid': 13, 'floor': 6} by_sym={'XAG': 56}
- HO net $8,291 (~$847/mo) | Fit $1,664 | leave-out drop ['2026-01', '2025-12'] → $-6,976
- max DD 9.40% | worst Prague day 2026-01-31 @ -2.69% | fail-days 0 | legal=True
- ≤90d 48/838 (HO-era 8) | seq 60/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=1 best_outside%=6.435126039242833 months=['2024-03', '2024-04', '2024-05']
- final equity $109,955 | chassis `xag-donchian-20d-2.50+softgov`

### 45B — 45B joint XAG soft + BTC 0.50%

- trades=170 WR=43.5% L/S=100/70
- reasons={'stop': 67, 'SL': 14, 'TP': 24, 'TIME': 17, 'target': 43, 'gap-stop': 3, 'gap-target': 1, 'SL_OPEN': 1} gov={'fixed': 114, 'full': 39, 'mid': 9, 'floor': 8} by_sym={'BTC': 114, 'XAG': 56}
- HO net $13,022 (~$1,330/mo) | Fit $-1,354 | leave-out drop ['2026-01', '2025-12'] → $-2,166
- max DD 10.28% | worst Prague day 2024-05-10 @ -3.04% | fail-days 0 | legal=False
- ≤90d 50/879 (HO-era 6) | seq 37/879 (HO-era 5)
- Explorer xcheck: outside_countable=0 countable=2 best_outside%=5.846554080183486 months=['2024-03', '2024-04', '2024-05']
- final equity $110,479 | chassis `xag-soft+btc-fixed-0.50`

### 45C — 45C joint XAG soft + BTC 0.60%

- trades=170 WR=43.5% L/S=100/70
- reasons={'stop': 67, 'SL': 14, 'TP': 24, 'TIME': 17, 'target': 43, 'gap-stop': 3, 'gap-target': 1, 'SL_OPEN': 1} gov={'fixed': 114, 'full': 39, 'mid': 8, 'floor': 9} by_sym={'BTC': 114, 'XAG': 56}
- HO net $14,977 (~$1,530/mo) | Fit $-1,644 | leave-out drop ['2026-01', '2025-12'] → $-493
- max DD 11.09% | worst Prague day 2024-05-10 @ -3.15% | fail-days 0 | legal=False
- ≤90d 52/879 (HO-era 4) | seq 40/879 (HO-era 6)
- Explorer xcheck: outside_countable=0 countable=2 best_outside%=6.765206353781328 months=['2024-06', '2024-07', '2024-08']
- final equity $111,876 | chassis `xag-soft+btc-fixed-0.60`

### 45D — 45D joint XAG soft + BTC 0.75%

- trades=170 WR=43.5% L/S=100/70
- reasons={'stop': 67, 'SL': 14, 'TP': 24, 'TIME': 17, 'target': 43, 'gap-stop': 3, 'gap-target': 1, 'SL_OPEN': 1} gov={'fixed': 114, 'full': 39, 'mid': 7, 'floor': 10} by_sym={'BTC': 114, 'XAG': 56}
- HO net $18,402 (~$1,880/mo) | Fit $-1,282 | leave-out drop ['2026-01', '2026-08'] → $2,051
- max DD 11.91% | worst Prague day 2024-05-10 @ -3.32% | fail-days 0 | legal=False
- ≤90d 58/879 (HO-era 0) | seq 53/879 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=2 best_outside%=8.455703460107976 months=['2024-06', '2024-07', '2024-08']
- final equity $115,235 | chassis `xag-soft+btc-fixed-0.75`

### 45E — 45E joint XAG soft-2.00 + BTC 0.60%

- trades=170 WR=43.5% L/S=100/70
- reasons={'stop': 67, 'SL': 14, 'TP': 24, 'TIME': 17, 'target': 43, 'gap-stop': 3, 'gap-target': 1, 'SL_OPEN': 1} gov={'fixed': 114, 'full': 42, 'mid': 9, 'floor': 5} by_sym={'BTC': 114, 'XAG': 56}
- HO net $16,283 (~$1,663/mo) | Fit $-766 | leave-out drop ['2026-01', '2026-08'] → $2,370
- max DD 9.89% | worst Prague day 2024-05-10 @ -2.60% | fail-days 0 | legal=True
- ≤90d 37/879 (HO-era 6) | seq 7/879 (HO-era 4)
- Explorer xcheck: outside_countable=0 countable=2 best_outside%=6.742212916364276 months=['2024-06', '2024-07', '2024-08']
- final equity $114,028 | chassis `xag-soft-2.00+btc-fixed-0.60`

## Does this open a ~3mo path?


Live C4 / drip / FREEZE / MetaAPI: **untouched**. Gold/NR7/JPN excluded. No deploy.
