# Candidate 40 Results — GER40 Keltner55 (entry55) + soft DD governor

**NO — GER40 Keltner55 does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

**GER40 data:** `/workspace/strategy-explorer/pr36/dukascopy-raw/deuidxeur-m1-bid-2024-01-01-2026-09-02.csv` sha256 `f2b497a703bfcfe273896e467c25b3472ab1689d050ee74f3f0f057791d8010d` end `2026-09-01 23:59:00+00:00`
**Signal funnel:** `{'no_signal': 754, 'atr': 13, 'bands': 6, 'long': 34, 'signals': 43, 'short': 15, 'ignored': 5, 'no_next': 1}`
**Measured (ET):** 2026-10-07 12:46 ET

## ASSUMPTIONS

| Item | Value |
|---|---|
| GER40.cash contractSize | **1** (catalogue) |
| GER40.cash commission | **0** (catalogue) |
| GER40 spread | **2.0** pts (**ASSUMPTION** — feed missing; C22) |
| GER40 EUR→USD | **1:1** (**ASSUMPTION** — research) |
| Soft gov | dd<5% full; 5–8% half; ≥8% quarter; never sticky-block |
| Prague day kill | −3% |
| Chassis | entry55: EMA20 Mid ±1.5 ATR14; stop 2×ATR; TP 2R; TIME day5 |

## Scoreboard

| Book | Risk/gov | HO $/mo | Max DD | ≤90d (HO) | seq90 (HO) | Ext | Leave-out | Legal | Explorer out/cnt | Decision |
|---|---|---:|---:|---:|---:|---|---:|---|---|---|
| 40A | 2.50% OFF | -724 | 13.8% | 0/857 (0) | 0/857 (0) | N/A | -11,033 | NO | 0/0 best=9.018664390632392 | REJECT |
| 40B | SOFT 2.50→1.25→0.75 | -399 | 9.8% | 0/857 (0) | 0/857 (0) | N/A | -4,879 | YES | 0/0 best=9.018664390632392 | REJECT |

### 40A — 40A GER40 Keltner55 @2.50% OFF

- trades=43 WR=44.2% L/S=30/13
- reasons={'TIME': 31, 'SL': 10, 'TP': 2} gov={'n/a': 43}
- HO net $-7,089 (~$-724/mo) | Fit $10,634 | leave-out drop ['2026-03', '2026-08'] → $-11,033
- max DD 13.78% | worst Prague day 2026-09-01 @ -2.52% | fail-days 0 | legal=False
- ≤90d 0/857 (HO-era 0) | seq 0/857 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=9.018664390632392 months=['2024-12', '2025-01', '2025-02'] dd=-0.13784783259394548
- final equity $103,545 | chassis `ger40-keltner55-2.50`

### 40B — 40B GER40 Keltner55 + soft gov (verdict)

- trades=43 WR=44.2% L/S=30/13
- reasons={'TIME': 31, 'SL': 10, 'TP': 2} gov={'full': 28, 'mid': 9, 'floor': 6}
- HO net $-3,904 (~$-399/mo) | Fit $12,239 | leave-out drop ['2026-08', '2025-11'] → $-4,879
- max DD 9.80% | worst Prague day 2024-07-19 @ -2.51% | fail-days 0 | legal=True
- ≤90d 0/857 (HO-era 0) | seq 0/857 (HO-era 0)
- Explorer xcheck: outside_countable=0 countable=0 best_outside%=9.018664390632392 months=['2024-12', '2025-01', '2025-02'] dd=-0.09796630566953463
- final equity $108,335 | chassis `ger40-keltner55-2.50+softgov`

## Does this open a ~3mo path?

**NO — GER40 Keltner55 does not open a deployable ~3mo path.** DD illegal, HO≤0, or zero ≤90d windows.

Live C4 / drip / FREEZE / MetaAPI: **untouched**. Gold not packaged. No deploy.
