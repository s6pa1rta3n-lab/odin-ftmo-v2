# Candidate 44 Results — XAG soft PRIMARY + BTC C15 fixed satellite (no NR7 / no Gold / no JPN)

**CONDITIONAL — XAG soft + BTC fixed satellite legal/windows, not ACCEPT** via 44C: max DD 9.6%, HO≤90d 6, HO ~$1,266/mo, leave $-2,492 (Δ vs 44A +4,483). Leave-out still blocks ACCEPT.

**XAG window survival / leave Δ:** 44A HO≤90d=8 leave=-6976 → 44C HO≤90d=6 DD=9.6% leave=-2492 (Δ+4483) | 44D HO≤90d=8 DD=9.1% leave=-5271 (Δ+1705) | windows_survived=Y

**XAG data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/xagusd-m1-bid-2024-01-01-2026-09-02.csv` sha256 `6970b0a1ef4bea4fc4c4deb6f4730ab78b719bd420c47955bfee72a6aa7afe1c` end `2026-09-01 23:59:00+00:00`
**BTC data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/btcusd-m1-bid-2024-01-01-2026-09-02.csv` + dukas-ext sha256 main `437a2c36f6ac9da5684533f9cde17e029f177abacab30579cd2c30e625443829` end `2026-10-07 11:34:00+00:00`
**Measured (ET):** 2026-10-07 13:06 ET

## ASSUMPTIONS

| Item | Value |
|---|---|
| XAG contract / spread / commission | **5000** / **0.025** / **$3/lot** (ASSUMPTION — C19B/C21B) |
| XAG risks | **2.50% / 1.25% / 0.75%** soft |
| BTC costs | spread **15** / comm 0 (C15 model) |
| BTC risks | **FIXED 0.40% (44C/E) or 0.20% (44B/D)** — no soft ladder |
| Soft gov | XAG only; BTC fixed |
| Prague day kill | −3% both |
| Positions | dual-open (44C/D); MUTEX XAG priority (44E only if needed) |
| US100 / Gold / JPN | excluded |

## Scoreboard

| Book | Symbol | Mode | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Δ vs 44A | Legal | Decision |
|---|---|---|---:|---:|---:|---:|---|---:|---:|---|---|
| 44A | XAG | single | 847 | 9.4% | 48/838 (8) | 60/838 (0) | N/A | -6,976 | +0 | YES | CONDITIONAL |
| 44B | BTC | single/0.20% | 330 | 2.0% | 0/879 (0) | 0/879 (0) | -441 | 836 | +7,811 | YES | REJECT |
| 44C | JOINT | dual/0.40% | 1,266 | 9.6% | 50/879 (6) | 36/879 (6) | -943 | -2,492 | +4,483 | YES | CONDITIONAL |
| 44D | JOINT | dual/0.20% | 878 | 9.1% | 48/879 (8) | 26/879 (14) | -456 | -5,271 | +1,705 | YES | CONDITIONAL |

### 44A — 44A XAG soft

- trades=56 WR=53.6% L/S=44/12
- reasons={'SL': 14, 'TP': 24, 'TIME': 17, 'SL_OPEN': 1} gov={'full': 37, 'mid': 13, 'floor': 6} by_sym={'XAG': 56}
- HO net $8,291 (~$847/mo) | Fit $1,664 | leave-out drop ['2026-01', '2025-12'] → $-6,976
- max DD 9.40% | worst Prague day 2026-01-31 @ -2.69% | fail-days 0 | legal=True
- ≤90d 48/838 (HO-era 8) | seq 60/838 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=1 best_outside%=6.435126039242833 months=['2024-03', '2024-04', '2024-05']
- final equity $109,955 | chassis `xag-donchian-20d-2.50+softgov`

### 44B — 44B BTC C15 FIXED 0.20%

- trades=114 WR=38.6% L/S=56/58
- reasons={'stop': 67, 'target': 43, 'gap-stop': 3, 'gap-target': 1} gov={'fixed': 114} by_sym={'BTC': 114}
- HO net $3,232 (~$330/mo) | Fit $255 | leave-out drop ['2026-06', '2026-08'] → $836
- max DD 2.04% | worst Prague day 2025-02-17 @ -0.41% | fail-days 0 | legal=True
- ≤90d 0/879 (HO-era 0) | seq 0/879 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=2.1593842126018448 months=['2024-06', '2024-07', '2024-08']
- final equity $103,046 | chassis `btc-h4-bb-squeeze-fixed-0.20`

### 44C — 44C joint XAG soft + BTC 0.40%

- trades=170 WR=43.5% L/S=100/70
- reasons={'stop': 67, 'SL': 14, 'TP': 24, 'TIME': 17, 'target': 43, 'gap-stop': 3, 'gap-target': 1, 'SL_OPEN': 1} gov={'fixed': 114, 'full': 38, 'mid': 10, 'floor': 8} by_sym={'BTC': 114, 'XAG': 56}
- HO net $12,397 (~$1,266/mo) | Fit $-2,226 | leave-out drop ['2026-01', '2025-12'] → $-2,492
- max DD 9.58% | worst Prague day 2024-05-10 @ -2.93% | fail-days 0 | legal=True
- ≤90d 50/879 (HO-era 6) | seq 36/879 (HO-era 6)
- Explorer xcheck: outside_countable=0 countable=2 best_outside%=5.959280918137844 months=['2024-03', '2024-04', '2024-05']
- final equity $109,228 | chassis `xag-soft+btc-fixed-0.40`

### 44D — 44D joint XAG soft + BTC 0.20%

- trades=170 WR=43.5% L/S=100/70
- reasons={'stop': 67, 'SL': 14, 'TP': 24, 'TIME': 17, 'target': 43, 'gap-stop': 3, 'gap-target': 1, 'SL_OPEN': 1} gov={'fixed': 114, 'full': 35, 'mid': 14, 'floor': 7} by_sym={'BTC': 114, 'XAG': 56}
- HO net $8,598 (~$878/mo) | Fit $-2,479 | leave-out drop ['2026-01', '2025-12'] → $-5,271
- max DD 9.07% | worst Prague day 2026-06-14 @ -2.91% | fail-days 0 | legal=True
- ≤90d 48/879 (HO-era 8) | seq 26/879 (HO-era 14)
- Explorer xcheck: outside_countable=0 countable=2 best_outside%=6.185650400798481 months=['2024-03', '2024-04', '2024-05']
- final equity $105,663 | chassis `xag-soft+btc-fixed-0.20`

## Does this open a ~3mo path?

**CONDITIONAL — XAG soft + BTC fixed satellite legal/windows, not ACCEPT** via 44C: max DD 9.6%, HO≤90d 6, HO ~$1,266/mo, leave $-2,492 (Δ vs 44A +4,483). Leave-out still blocks ACCEPT.

Live C4 / drip / FREEZE / MetaAPI: **untouched**. Gold/NR7/JPN excluded. No deploy.
